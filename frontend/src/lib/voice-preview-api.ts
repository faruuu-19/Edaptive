import type { DeliveryContext } from "./lesson-delivery-api";
// Provisional, local draft-preview API. It does not send events or learner data.
export type LessonSegment = {
  id: string; kind: string; checkpoint: boolean;
  utterances: { caption: string; spoken: string }[];
  cues: string[]; review_flags: string[];
};
export type PreviewLesson = {
  title: string; concept_id: string; grade: number; subject: string;
  preview_only: true; ready_for_delivery: false;
  segments: LessonSegment[]; voices: { id: string; label: string }[];
};
export type SpeechFrame =
  | { type: "start"; segment_id: string }
  | { type: "audio"; utterance: number; caption: string; sample_rate: number; pcm_s16le: string; ready_after_s: number }
  | {
      type: "lecture"; version: number; gap_ms: number; kind: string;
      sentences: { utterance: number; speech_start_ms: number; speech_end_ms: number }[];
      gestures: { at_ms: number; name: string; seconds: number; mirror: boolean }[] | null;
    } // sent when the part was compiled ahead of time
  | { type: "done"; segment_id: string }
  | { type: "error"; detail: string };

export async function getPreviewLesson(signal: AbortSignal): Promise<PreviewLesson> {
  const response = await fetch("/voice-preview-api/lesson", { cache: "no-store", signal });
  if (!response.ok) throw new Error("The local teacher is unavailable. Start the voice preview service, then retry.");
  return response.json();
}

export async function streamPreviewSpeech(segmentId: string, voice: string, signal: AbortSignal, onFrame: (frame: SpeechFrame) => void, delivery?: DeliveryContext) {
  const response = await fetch(delivery ? `/api/lesson_delivery/${delivery.timetableId}/narrate` : "/voice-preview-api/narrate", {
    method: "POST", body: JSON.stringify({ segment_id: segmentId, voice, ...(delivery ? { slot_id: delivery.slotId } : {}) }),
    headers: { "Content-Type": "application/json" }, cache: "no-store", signal,
  });
  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? "The teacher could not start. Please retry.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let finished = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let newline: number;
      while ((newline = pending.indexOf("\n")) >= 0) {
        const line = pending.slice(0, newline); pending = pending.slice(newline + 1);
        if (!line.trim()) continue;
        const frame: SpeechFrame = JSON.parse(line);
        if (frame.type === "error") throw new Error(frame.detail);
        if (frame.type === "done") finished = true;
        onFrame(frame);
      }
      if (pending.length > 4_000_000) throw new Error("The narration response is too large.");
      if (done) break;
    }
    if (pending.trim() || !finished) throw new Error("Narration was interrupted. Please replay this part.");
  } finally { reader.releaseLock(); }
}
