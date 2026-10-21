import { request } from './api';
import type { PreviewLesson } from './voice-preview-api';

export type DeliveryContext = { timetableId: string; slotId: string };
export type PreparedSlot = {
  id: string; kind: 'lesson' | 'break' | 'unavailable'; subject: string; title: string;
  module?: number; lesson?: number; concept_id?: string; start_ms: number; end_ms: number; class_phase: string; position?: number;
  borrowed_minutes?: number; prepare_at_ms?: number;
  delay_minutes?: number; delayed_from_ms?: number; delay_notice?: string;
  exit_count?: number; exit_reason?: 'child' | 'timeout'; exited_at_ms?: number; segment_count?: number;
  preparation?: { status: string; percent: number; message: string; completed?: number; total?: number; failure_kind?: string };
  timing?: { minutes: number; basis: string; spoken_words?: number; buffer_seconds: number };
};
export type SavedTimetable = { id: string; student_id: string; status: string; school_date?: string; current_slot_id: string | null; server_now_ms: number; slots: PreparedSlot[] };
export type DeliveryCard = { id: string; title: string; grade: number; module: number; ready_for_delivery: boolean; recommended_prepare_minutes: number };
export type SchoolRoutine = { student_id: string; start_time: string; timezone: string; status: string; message: string };
export const getDeliveryCatalog = (studentId: string) => request<{ cards: DeliveryCard[] }>(`/api/lesson_delivery/catalog/${studentId}`);
export type MathsModule = { module: number; title: string };
export type MathsModulesByGrade = Record<number, MathsModule[]>;
export type LearningProgress = { grade: number; mastery_assessed: false; next_required?: { module: number; lesson: number; matched: boolean } | null; modules: { module: number; expected_lessons: number | null; delivered_lessons: number; unfinished_lessons?: number; status: string }[] };
type StudentDelivery = { timetables: SavedTimetable[]; routine: SchoolRoutine | null; learning_progress: LearningProgress | null };
const pendingTimetables = new Map<string, Promise<StudentDelivery>>();
export function getTimetables(studentId: string): Promise<StudentDelivery> {
  const pending = pendingTimetables.get(studentId);
  if (pending) return pending;
  const loading = request<StudentDelivery>(`/api/lesson_delivery/student/${studentId}`).then(result => {
    if (result.timetables.some(day => day.student_id !== studentId) || (result.routine && result.routine.student_id !== studentId)) {
      throw new Error('Lesson data does not match the selected profile.');
    }
    return result;
  }).finally(() => { if (pendingTimetables.get(studentId) === loading) pendingTimetables.delete(studentId); });
  pendingTimetables.set(studentId, loading);
  return loading;
}
export const getSchoolRoutine = (studentId: string) => request<{ routine: SchoolRoutine | null }>(`/api/lesson_delivery/routine/${studentId}`);
export const saveSchoolStartTime = (studentId: string, start_time: string) => request<{ routine: SchoolRoutine; timetable: SavedTimetable | null }>(`/api/lesson_delivery/routine/${studentId}`, { method: 'PUT', body: JSON.stringify({ start_time }) });
export const deliveryAction = (context: DeliveryContext, action: string, position?: number) => request<SavedTimetable>(`/api/lesson_delivery/${context.timetableId}/action`, { method: 'POST', body: JSON.stringify({ slot_id: context.slotId, action, ...(position === undefined ? {} : { position }) }) });
export const getDeliveryLesson = (context: DeliveryContext, signal: AbortSignal) => request<PreviewLesson & { position: number; voice: string }>(`/api/lesson_delivery/${context.timetableId}/lesson/${context.slotId}`, { signal });
export const getLessonAlarmSetting = (studentId: string) => request<{ granted: boolean }>(`/api/consent/${studentId}/lesson-alarm`);
