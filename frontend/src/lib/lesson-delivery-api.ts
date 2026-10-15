import { request } from './api';
import type { PreviewLesson } from './voice-preview-api';

export type DeliveryContext = { timetableId: string; slotId: string };
export type PreparedSlot = {
  id: string; kind: 'lesson' | 'break' | 'unavailable'; subject: string; title: string;
  module?: number; lesson?: number; concept_id?: string; start_ms: number; end_ms: number; class_phase: string; position?: number;
  borrowed_minutes?: number; prepare_at_ms?: number;
  exit_count?: number; exit_reason?: 'child' | 'timeout'; exited_at_ms?: number; segment_count?: number;
  preparation?: { status: string; percent: number; message: string; completed?: number; total?: number };
  timing?: { minutes: number; basis: string; spoken_words?: number; buffer_seconds: number };
};
export type SavedTimetable = { id: string; student_id: string; status: string; school_date?: string; current_slot_id: string | null; server_now_ms: number; slots: PreparedSlot[] };
export type DeliveryCard = { id: string; title: string; grade: number; module: number; ready_for_delivery: boolean; recommended_prepare_minutes: number };
export type SchoolRoutine = { student_id: string; start_time: string; timezone: string; status: string; message: string };
export const getDeliveryCatalog = (studentId: string) => request<{ cards: DeliveryCard[] }>(`/api/lesson_delivery/catalog/${studentId}`);
export type LearningProgress = { grade: number; mastery_assessed: false; modules: { module: number; expected_lessons: number | null; delivered_lessons: number; status: string }[] };
export const getTimetables = (studentId: string) => request<{ timetables: SavedTimetable[]; routine: SchoolRoutine | null; learning_progress: LearningProgress | null }>(`/api/lesson_delivery/student/${studentId}`);
export const getSchoolRoutine = (studentId: string) => request<{ routine: SchoolRoutine | null }>(`/api/lesson_delivery/routine/${studentId}`);
export const saveSchoolStartTime = (studentId: string, start_time: string) => request<{ routine: SchoolRoutine; timetable: SavedTimetable | null }>(`/api/lesson_delivery/routine/${studentId}`, { method: 'PUT', body: JSON.stringify({ start_time }) });
export const deliveryAction = (context: DeliveryContext, action: string, position?: number) => request<SavedTimetable>(`/api/lesson_delivery/${context.timetableId}/action`, { method: 'POST', body: JSON.stringify({ slot_id: context.slotId, action, ...(position === undefined ? {} : { position }) }) });
export const getDeliveryLesson = (context: DeliveryContext, signal: AbortSignal) => request<PreviewLesson & { position: number; voice: string }>(`/api/lesson_delivery/${context.timetableId}/lesson/${context.slotId}`, { signal });
export const getLessonAlarmSetting = (studentId: string) => request<{ granted: boolean }>(`/api/consent/${studentId}/lesson-alarm`);
