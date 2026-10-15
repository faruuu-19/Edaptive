// The TalkingHead package ships no types. Only what this feature calls is declared, from the
// signatures in @met4citizen/talkinghead 1.7.0 (modules/talkinghead.mjs).
declare module "@met4citizen/talkinghead" {
  export type StreamAudio = {
    audio: ArrayBuffer | Int16Array | Float32Array;
    words?: string[];
    wtimes?: number[]; // start of each word, ms from the start of the stream
    wdurations?: number[]; // ms
  };
  export class TalkingHead {
    constructor(node: HTMLElement, options?: Record<string, unknown>);
    audioCtx: AudioContext;
    lipsync: Record<string, unknown>;
    showAvatar(avatar: { url: string; body?: "F" | "M"; avatarMood?: string; lipsyncLang?: string }, onprogress?: ((e: ProgressEvent) => void) | null): Promise<void>;
    streamStart(options?: Record<string, unknown>, onAudioStart?: (() => void) | null, onAudioEnd?: (() => void) | null, onSubtitles?: ((text: string) => void) | null, onMetrics?: ((m: unknown) => void) | null): Promise<void>;
    streamAudio(r: StreamAudio): void;
    streamNotifyEnd(): void;
    streamInterrupt(): void;
    stopSpeaking(): void;
    playPose(name: string, onprogress?: null, seconds?: number): Promise<void>;
    playGesture(name: string, seconds?: number, mirror?: boolean, transitionMs?: number): void;
    stopGesture(transitionMs?: number): void;
    start(): void;
    stop(): void;
    dispose(): void;
  }
}

declare module "@met4citizen/talkinghead/modules/lipsync-en.mjs" {
  export class LipsyncEn {}
}
