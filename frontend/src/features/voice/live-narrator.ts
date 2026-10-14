import type { DeliveryContext } from "@/lib/lesson-delivery-api";
import { streamPreviewSpeech, type SpeechFrame } from "@/lib/voice-preview-api";

type Callbacks = { onPlaying: () => void; onCaption: (index: number) => void; onComplete: () => void };

/** Audio stays in memory. A segment is generated sentence by sentence while earlier audio plays. */
export class LiveNarrator {
  private controller = new AbortController();
  private context = new AudioContext();
  private sources = new Set<AudioBufferSourceNode>();
  private captions: { starts: number; index: number }[] = [];
  private cursor = 0;
  private frameId = 0;
  private receivedDone = false;
  private playing = false;
  private stopped = false;
  private caption = -1;

  async speak(segmentId: string, voice: string, callbacks: Callbacks, delivery?: DeliveryContext) {
    await this.context.resume();
    const tick = () => {
      if (this.stopped) return;
      for (const cue of this.captions) {
        if (cue.starts <= this.context.currentTime && cue.index !== this.caption) {
          this.caption = cue.index; callbacks.onCaption(cue.index);
        }
      }
      this.captions = this.captions.filter(c => c.starts > this.context.currentTime);
      this.frameId = requestAnimationFrame(tick);
    };
    this.frameId = requestAnimationFrame(tick);
    const complete = () => {
      if (this.receivedDone && !this.sources.size && !this.stopped) {
        this.cancel(); callbacks.onComplete();
      }
    };
    try {
      await streamPreviewSpeech(segmentId, voice, this.controller.signal, (frame: SpeechFrame) => {
        if (this.stopped) return;
        if (frame.type === "done") { this.receivedDone = true; complete(); return; }
        if (frame.type !== "audio") return;
        if (!Number.isInteger(frame.sample_rate) || frame.sample_rate < 8000 || frame.sample_rate > 48000) {
          throw new Error("The teacher returned an invalid audio format.");
        }
        const bytes = atob(frame.pcm_s16le);
        if (!bytes.length || bytes.length % 2) throw new Error("The narration audio was interrupted.");
        const buffer = this.context.createBuffer(1, bytes.length / 2, frame.sample_rate);
        const channel = buffer.getChannelData(0);
        for (let i = 0; i < channel.length; i++) {
          let sample = bytes.charCodeAt(i * 2) | (bytes.charCodeAt(i * 2 + 1) << 8);
          if (sample >= 32768) sample -= 65536;
          channel[i] = sample / 32768;
        }
        const source = this.context.createBufferSource();
        source.buffer = buffer; source.connect(this.context.destination);
        const starts = Math.max(this.cursor, this.context.currentTime + 0.04);
        this.cursor = starts + buffer.duration;
        this.captions.push({ starts, index: frame.utterance });
        this.sources.add(source);
        source.onended = () => { this.sources.delete(source); source.disconnect(); complete(); };
        source.start(starts);
        if (!this.playing) { this.playing = true; callbacks.onPlaying(); }
      }, delivery);
    } catch (error) {
      const cancelled = this.stopped;
      this.cancel();
      if (!cancelled) throw error;
    }
  }

  async pause() { if (!this.stopped) await this.context.suspend(); }
  async resume() { if (!this.stopped) await this.context.resume(); }
  cancel() {
    if (this.stopped) return;
    this.stopped = true; this.controller.abort(); cancelAnimationFrame(this.frameId);
    for (const source of this.sources) { source.onended = null; source.stop(); source.disconnect(); }
    this.sources.clear();
    void this.context.close();
  }
}
