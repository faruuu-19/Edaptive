import type { DeliveryContext } from "@/lib/lesson-delivery-api";
import { streamPreviewSpeech, type SpeechFrame } from "@/lib/voice-preview-api";

type Callbacks = { onPlaying: () => void; onCaption: (index: number) => void; onComplete: () => void };

/** Silence between one sentence and the next, so the teacher breathes and the avatar's mouth is shut. */
export const SENTENCE_GAP_MS = 1000;

/**
 * A part compiled ahead of time (voice_service/lecture.py): where she really speaks inside each sentence, the pause
 * between sentences, and the gestures, all on one clock in ms from the start of the part's audio. When the server
 * sends one, the avatar plays it as saved instead of working these out live.
 */
export type LecturePlan = {
  gapMs: number;
  /** By sentence number (`utterance`): when speech starts and ends inside that sentence's audio. */
  speech: Record<number, { startMs: number; endMs: number }>;
  /** Null when the compiler had no gesture planner; the avatar then plans gestures live. */
  gestures: { atMs: number; name: string; seconds: number; mirror: boolean }[] | null;
};

/**
 * Optional second consumer of the narration, for a talking avatar that plays the sound itself.
 * When a sink is given, this narrator stays silent but keeps its clock for captions and completion.
 * Audio is signed 16-bit mono PCM, one call per sentence, in order.
 */
export type NarrationSink = {
  /** A new part is starting; `kind` is its lesson role (hook, lecture, question, recap...), for gestures. */
  part?(kind: string): void;
  /** The part was compiled ahead of time; this arrives before its first sentence. */
  lecture?(plan: LecturePlan): void;
  /**
   * `gapBeforeMs` is the silence that must precede this sentence (0 for the first of a part). A voice may split one
   * sentence into several chunks: later chunks repeat `utterance`, have an empty caption and no gap.
   */
  audio(pcm: Int16Array, sampleRate: number, caption: string, gapBeforeMs: number, utterance: number): void;
  /** No more audio is coming for this part; playback finishes by itself. */
  end(): void;
  /** Cancelled (replay, navigation, new message): drop everything queued. */
  stop(): void;
  pause(): void;
  resume(): void;
};

const finite = (value: unknown, low: number, high: number): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= low && value <= high;

/** The compiled timeline from the server, checked field by field: a damaged one is ignored, never half-used. */
function readPlan(frame: Extract<SpeechFrame, { type: "lecture" }>): LecturePlan | null {
  if (!finite(frame.gap_ms, 0, 5000) || !Array.isArray(frame.sentences)) return null;
  const speech: LecturePlan["speech"] = {};
  for (const sentence of frame.sentences) {
    if (!Number.isInteger(sentence.utterance) || !finite(sentence.speech_start_ms, 0, 600_000)
      || !finite(sentence.speech_end_ms, sentence.speech_start_ms, 600_000)) return null;
    speech[sentence.utterance] = { startMs: sentence.speech_start_ms, endMs: sentence.speech_end_ms };
  }
  let gestures: LecturePlan["gestures"] = null;
  if (Array.isArray(frame.gestures)) {
    gestures = [];
    for (const g of frame.gestures) {
      if (typeof g.name !== "string" || !g.name || g.name.length > 16 || !finite(g.at_ms, 0, 3_600_000)
        || !finite(g.seconds, 0.1, 10) || typeof g.mirror !== "boolean") { gestures = null; break; }
      gestures.push({ atMs: g.at_ms, name: g.name, seconds: g.seconds, mirror: g.mirror });
    }
  }
  return { gapMs: frame.gap_ms, speech, gestures };
}

/** Audio stays in memory. A segment is generated sentence by sentence while earlier audio plays. */
export class LiveNarrator {
  private controller = new AbortController();
  private context = new AudioContext();
  /** Level and spectrum of what is playing, for the avatar's mouth. Read-only; adds no audio of its own. */
  readonly analyser = this.context.createAnalyser();
  private output = this.context.createGain();
  private sources = new Set<AudioBufferSourceNode>();
  private captions: { starts: number; index: number }[] = [];
  private cursor = 0;
  private frameId = 0;
  private receivedDone = false;
  private playing = false;
  private stopped = false;
  private caption = -1;
  private utterance = -1; // the sentence being delivered, so chunks of one sentence are not mistaken for new sentences
  private gapMs = SENTENCE_GAP_MS;

  constructor(private sink?: NarrationSink) {
    this.analyser.fftSize = 1024;
    this.analyser.smoothingTimeConstant = 0.4;
    this.output.gain.value = sink ? 0 : 1; // the sink plays the sound; this narrator only keeps time
    this.analyser.connect(this.output);
    this.output.connect(this.context.destination);
  }

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
        this.cancel(false); callbacks.onComplete();
      }
    };
    try {
      await streamPreviewSpeech(segmentId, voice, this.controller.signal, (frame: SpeechFrame) => {
        if (this.stopped) return;
        if (frame.type === "done") { this.receivedDone = true; this.sink?.end(); complete(); return; }
        if (frame.type === "lecture") {
          const plan = readPlan(frame);
          if (plan) { this.gapMs = plan.gapMs; this.sink?.lecture?.(plan); }
          return;
        }
        if (frame.type !== "audio") return;
        if (!Number.isInteger(frame.sample_rate) || frame.sample_rate < 8000 || frame.sample_rate > 48000) {
          throw new Error("The teacher returned an invalid audio format.");
        }
        const bytes = atob(frame.pcm_s16le);
        if (!bytes.length || bytes.length % 2) throw new Error("The narration audio was interrupted.");
        const buffer = this.context.createBuffer(1, bytes.length / 2, frame.sample_rate);
        const channel = buffer.getChannelData(0);
        const pcm = new Int16Array(channel.length);
        for (let i = 0; i < channel.length; i++) {
          let sample = bytes.charCodeAt(i * 2) | (bytes.charCodeAt(i * 2 + 1) << 8);
          if (sample >= 32768) sample -= 65536;
          pcm[i] = sample;
          channel[i] = sample / 32768;
        }
        const continuing = frame.utterance === this.utterance;
        const gapMs = !continuing && this.utterance >= 0 ? this.gapMs : 0;
        this.utterance = frame.utterance;
        this.sink?.audio(pcm, frame.sample_rate, continuing ? "" : frame.caption, gapMs, frame.utterance);
        const source = this.context.createBufferSource();
        source.buffer = buffer; source.connect(this.analyser);
        // Never closer than the gap to the sentence before, however fast the sentences arrive.
        const starts = Math.max(this.cursor + gapMs / 1000, this.context.currentTime + 0.04);
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

  async pause() { if (!this.stopped) { this.sink?.pause(); await this.context.suspend(); } }
  async resume() { if (!this.stopped) { this.sink?.resume(); await this.context.resume(); } }
  /** `interrupt` is false only when the part finished by itself, so the sink can play its last sound out. */
  cancel(interrupt = true) {
    if (this.stopped) return;
    if (interrupt) this.sink?.stop();
    this.stopped = true; this.controller.abort(); cancelAnimationFrame(this.frameId);
    for (const source of this.sources) { source.onended = null; source.stop(); source.disconnect(); }
    this.sources.clear();
    this.analyser.disconnect();
    void this.context.close();
  }
}
