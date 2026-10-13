import { request } from './api';
import type { PreviewLesson } from './voice-preview-api';

export type DeliveryContext = { timetableId: string; slotId: string };
export type PreparedSlot = {
  id: string; kind: 'lesson' | 'break'; subject: string; title: string;
  concept_id?: string; start_ms: number; end_ms: number; class_phase: string; position?: number;
  borrowed_minutes?: number;
  preparation?: { status: string; percent: number; message: string; completed?: number; total?: number };
  timing?: { minutes: number; basis: string; spoken_words?: number; buffer_seconds: number };
};
export type SavedTimetable = { id: string; student_id: string; status: string; current_slot_id: string | null; server_now_ms: number; slots: PreparedSlot[] };
export type DeliveryCard = { id: string; title: string; grade: number; module: number; ready_for_delivery: boolean; recommended_prepare_minutes: number };
export const getDeliveryCatalog = (studentId: string) => request<{ cards: DeliveryCard[] }>(`/api/lesson_delivery/catalog/${studentId}`);
export const getTimetables = (studentId: string) => request<{ timetables: SavedTimetable[] }>(`/api/lesson_delivery/student/${studentId}`);
export const planTimetable = (body: { student_id: string; starts_at: string; concept_ids: string[]; break_minutes: number; prepare_minutes: number | null; allow_drafts: boolean }) => request<SavedTimetable>('/api/lesson_delivery', { method: 'POST', body: JSON.stringify(body) });
export const deliveryAction = (context: DeliveryContext, action: string, position?: number) => request<SavedTimetable>(`/api/lesson_delivery/${context.timetableId}/action`, { method: 'POST', body: JSON.stringify({ slot_id: context.slotId, action, ...(position === undefined ? {} : { position }) }) });
export const getDeliveryLesson = (context: DeliveryContext, signal: AbortSignal) => request<PreviewLesson & { position: number; voice: string }>(`/api/lesson_delivery/${context.timetableId}/lesson/${context.slotId}`, { signal });
