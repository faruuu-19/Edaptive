import type { PreparedSlot } from '@/lib/lesson-delivery-api';

/** A lesson that is waiting for its start time is not being prepared yet. */
export const isWaitingToPrepare = (preparation: PreparedSlot['preparation']): boolean => preparation?.status === 'waiting';

const schoolDay = (ms: number) => new Date(ms + 5 * 3600000).toISOString().slice(0, 10); // Pakistan time, UTC+5

/** "at 4:28 pm", "tomorrow at 4:28 pm" or "on Mon 19 Oct at 4:28 pm". */
export function prepareTimeText(atMs: number | undefined, nowMs: number): string {
  if (!atMs) return 'before class';
  const clock = new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' }).format(atMs);
  const day = schoolDay(atMs);
  if (day === schoolDay(nowMs)) return `at ${clock}`;
  if (day === schoolDay(nowMs + 86400000)) return `tomorrow at ${clock}`;
  const date = new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', weekday: 'short', day: 'numeric', month: 'short' }).format(atMs);
  return `on ${date} at ${clock}`;
}
