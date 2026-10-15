export type Gesture = { name: string; seconds: number; mirror: boolean };
export type Planned = { atMs: number; gesture: Gesture };
/** One gesture of a compiled plan; `atMs` counts from the start of the part's audio, gaps included. */
export type PlannedGesture = { atMs: number; name: string; seconds: number; mirror: boolean };

export const MIN_SPACING_MS: number;
export const MIN_SENTENCE_MS: number;
export const LONG_SENTENCE_MS: number;

export class GesturePlanner {
  constructor(seed?: number);
  reset(): void;
  plan(kind: string, caption: string, startMs: number, speechMs: number): Planned[];
}

export function planPart(
  kind: string,
  sentences: { caption: string; startMs: number; speechMs: number }[],
  seed?: number,
): PlannedGesture[];
