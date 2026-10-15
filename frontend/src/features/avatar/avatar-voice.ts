import type { TalkingHead } from "@met4citizen/talkinghead";
import { GesturePlanner, type Planned } from "./gestures.mjs";

/** Structurally the same as `NarrationSink` in the voice feature; features only meet through their `index.ts`. */
export type AvatarLecturePlan = {
  gapMs: number;
  speech: Record<number, { startMs: number; endMs: number }>;
  gestures: { atMs: number; name: string; seconds: number; mirror: boolean }[] | null;
};

export type AvatarVoiceSink = {
  part?(kind: string): void;
  lecture?(plan: AvatarLecturePlan): void;
  audio(pcm: Int16Array, sampleRate: number, caption: string, gapBeforeMs: number, utterance: number): void;
  end(): void;
  stop(): void;
  pause(): void;
  resume(): void;
};

/** Samples quieter than this (about 2% of full scale) count as silence when finding where speech starts and ends. */
const SILENCE_LEVEL = 700;
/** A gesture starts this long before its sentence, so the hand is already moving when she begins to speak. */
const GESTURE_LEAD_MS = 250;
const GESTURE_BLEND_MS = 600;

/** Where speech actually starts and ends inside a sentence's audio; TTS pads both ends with silence. */
export function speechBounds(pcm: Int16Array, sampleRate: number) {
  const totalMs = (pcm.length / sampleRate) * 1000;
  let first = 0;
  while (first < pcm.length && Math.abs(pcm[first]) < SILENCE_LEVEL) first++;
  let last = pcm.length - 1;
  while (last > first && Math.abs(pcm[last]) < SILENCE_LEVEL) last--;
  if (first >= last) return { startMs: 0, endMs: totalMs };
  return { startMs: (first / sampleRate) * 1000, endMs: ((last + 1) / sampleRate) * 1000 };
}

/** Word start times and durations (ms) spread across the spoken part only, longer words taking longer. */
export function wordTimings(caption: string, startMs: number, endMs: number) {
  const words = caption.split(/\s+/).filter(Boolean);
  const weights = words.map(word => word.length + 2);
  const total = weights.reduce((sum, weight) => sum + weight, 0) || 1;
  const span = Math.max(endMs - startMs, 1);
  let cursor = startMs;
  const wtimes: number[] = [];
  const wdurations: number[] = [];
  weights.forEach(weight => {
    const duration = (weight / total) * span;
    wtimes.push(cursor);
    wdurations.push(duration);
    cursor += duration;
  });
  return { words, wtimes, wdurations };
}

/**
 * Plays the narration through the 3D teacher. Sentences arrive as PCM, one at a time. Each goes to
 * TalkingHead's streaming mode with word timings that cover only the part where she is actually speaking, so
 * the mouth is shut in the 1 s gaps (sent as real silence) and in the padding around each sentence.
 * Timings are relative to the start of the stream, so a running offset is kept. Gestures are fired on the audio
 * clock, which stops while paused. A part compiled ahead of time (`lecture`) brings its own speech timings and
 * gesture plan, which are played as saved; otherwise both are worked out live here (see `gestures.mjs`).
 */
export class AvatarVoice implements AvatarVoiceSink {
  private session: Promise<void> | null = null;
  private generation = 0;
  private offsetMs = 0;
  private ended = false;
  private kind = "";
  private planner = new GesturePlanner();
  private timeline: Planned[] = [];
  private plan: AvatarLecturePlan | null = null; // the compiled timeline for the part being played, if there is one
  private planLoaded = false;
  private startedAt: number | null = null; // performance.now() when the audio really began
  private pausedAt: number | null = null;
  private pausedMs = 0;
  private ticker: ReturnType<typeof setInterval> | null = null;

  constructor(private head: TalkingHead) {}

  part(kind: string) {
    this.kind = kind;
    this.plan = null; // a new part: whatever was compiled for the last one no longer applies
  }

  lecture(plan: AvatarLecturePlan) {
    this.plan = plan;
  }

  audio(pcm: Int16Array, sampleRate: number, caption: string, gapBeforeMs = 0, utterance = 0) {
    const session = !this.session || this.ended ? this.begin(sampleRate) : this.session;
    const token = this.generation;
    if (this.plan?.gestures && !this.planLoaded) {
      this.planLoaded = true; // after begin(), which clears the timeline
      this.timeline.push(...this.plan.gestures.map(g => ({ atMs: g.atMs, gesture: { name: g.name, seconds: g.seconds, mirror: g.mirror } })));
    }
    const gap = gapBeforeMs > 0 ? new Int16Array(Math.round((sampleRate * gapBeforeMs) / 1000)) : null;
    if (gap) this.offsetMs += gapBeforeMs;
    const sentenceStart = this.offsetMs;
    const bounds = this.plan?.speech[utterance] ?? (() => { const found = speechBounds(pcm, sampleRate); return { startMs: found.startMs, endMs: found.endMs }; })();
    const timing = wordTimings(caption, sentenceStart + bounds.startMs, sentenceStart + bounds.endMs);
    this.offsetMs += (pcm.length / sampleRate) * 1000;

    (window as { __audio?: unknown[] }).__audio?.push({ caption: caption.slice(0, 40), gapBeforeMs, sentenceStart: Math.round(sentenceStart), ended: this.ended, kind: this.kind, compiled: Boolean(this.plan), at: Math.round(performance.now()) }); // test hook
    if (!this.plan?.gestures && caption) {
      this.timeline.push(...this.planner.plan(this.kind, caption, sentenceStart + bounds.startMs, bounds.endMs - bounds.startMs));
    }

    // Copies: the audio worklet takes ownership of each buffer it is given.
    const silence = gap?.buffer;
    const audio = pcm.slice().buffer;
    void session.then(() => {
      if (token !== this.generation) return;
      if (silence) this.head.streamAudio({ audio: silence }); // no words: no mouth movement
      this.head.streamAudio({ audio, ...timing });
    });
  }

  end() {
    const token = this.generation;
    void this.session?.then(() => {
      if (token === this.generation) this.head.streamNotifyEnd();
    });
    this.ended = true;
  }

  stop() {
    this.generation++; // anything still waiting to be sent is dropped
    this.session = null;
    this.ended = false;
    this.offsetMs = 0;
    this.plan = null;
    this.clearGestures();
    try { this.head.streamInterrupt(); } catch { /* not streaming */ }
    this.head.stopSpeaking();
    this.head.stopGesture(300);
  }

  // TalkingHead's stop() suspends its audio clock and animation together; start() resumes both.
  pause() {
    this.pausedAt = performance.now();
    this.head.stop();
  }

  resume() {
    if (this.pausedAt !== null) this.pausedMs += performance.now() - this.pausedAt;
    this.pausedAt = null;
    this.head.start();
  }

  private begin(sampleRate: number): Promise<void> {
    this.ended = false;
    this.offsetMs = 0;
    this.generation++;
    this.clearGestures();
    const token = this.generation;
    this.session = this.head.streamStart({ sampleRate, lipsyncType: "words", lipsyncLang: "en", gain: 1 }, () => {
      if (token === this.generation) this.audioStarted();
    });
    return this.session;
  }

  private audioStarted() {
    this.startedAt = performance.now();
    this.pausedMs = 0;
    this.pausedAt = null;
    this.ticker = setInterval(() => this.fireDueGestures(), 100);
  }

  private fireDueGestures() {
    if (this.startedAt === null || this.pausedAt !== null) return; // the audio clock is stopped while paused
    const playedMs = performance.now() - this.startedAt - this.pausedMs;
    while (this.timeline.length && this.timeline[0].atMs - GESTURE_LEAD_MS <= playedMs) {
      const { gesture, atMs } = this.timeline.shift()!;
      this.head.playGesture(gesture.name, gesture.seconds, gesture.mirror, GESTURE_BLEND_MS);
      (window as { __gestures?: unknown[] }).__gestures?.push({ ...gesture, plannedMs: Math.round(atMs), playedMs: Math.round(playedMs) }); // test hook
    }
  }

  private clearGestures() {
    if (this.ticker) clearInterval(this.ticker);
    this.ticker = null;
    this.timeline = [];
    this.startedAt = null;
    this.pausedAt = null;
    this.pausedMs = 0;
    this.planLoaded = false;
    this.planner.reset();
  }
}
