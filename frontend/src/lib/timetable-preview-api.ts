export type CardChoice = { id: string; title: string; grade: number; module: number; quick_demo_available: boolean };
export type TimetableSlot = { subject: string; title: string; start_ms: number; end_ms: number; content_available: boolean };
export type DemoSchedule = {
  id: string; concept_id: string; mode: "fresh" | "reuse"; start_ms: number; prepare_at_ms: number;
  preparation: "waiting" | "preparing" | "ready" | "failed"; percent: number; completed: number; total: number | null;
  message: string; slots: TimetableSlot[]; borrowed_minutes: number;
  class_phase: "waiting" | "ringing" | "started" | "completed" | "cancelled"; server_now_ms: number;
};
export type ScheduleResponse = { schedule: DemoSchedule | null; server_now_ms: number };

async function request<T>(action: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/voice-preview-api/${action}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store", signal,
    headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "The local timetable is unavailable.");
  return data;
}
export const getCardChoices = (signal: AbortSignal) => request<{ cards: CardChoice[] }>("catalog", undefined, signal);
export const getDemoSchedule = (signal?: AbortSignal) => request<ScheduleResponse>("schedule", undefined, signal);
export const createDemoSchedule = (concept_id: string, start_ms: number, lead_seconds: number, mode: "fresh" | "reuse") => request<ScheduleResponse>("schedule", { concept_id, start_ms, lead_seconds, mode });
export const actOnDemoSchedule = (schedule_id: string, action: "start" | "borrow" | "cancel" | "finish") => request<ScheduleResponse>("schedule-action", { schedule_id, action });
