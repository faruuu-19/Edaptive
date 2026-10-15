import { request } from './api';

export type PermissionKind = 'camera' | 'microphone' | 'lesson_alarm';
export type Permission = { kind: PermissionKind; granted: boolean; decided_at: string | null; policy_version: string };
export type Permissions = { student_id: string; permissions: Permission[]; input_available: false };
export const getPermissions = (studentId: string) => request<Permissions>(`/api/consent/${studentId}`);
export const setPermission = (studentId: string, kind: PermissionKind, granted: boolean) => request<Permissions>(`/api/consent/${studentId}/${kind}`, { method: 'PUT', body: JSON.stringify({ granted }) });

export type AttendanceRecord = {
  school_date: string; lesson_title: string; concept_id: string; subject: 'math' | 'english' | 'science' | 'other'; status: 'present' | 'absent';
  reason: 'completed' | 'left_after_threshold' | 'left_early' | 'did_not_join'; attended_percent: number; recorded_at: string;
};
export type Attendance = { student_id: string; threshold_percent: number; summary: { present: number; absent: number }; records: AttendanceRecord[] };
export const getAttendance = (studentId: string) => request<Attendance>(`/api/attendance/${studentId}`);
