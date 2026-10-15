import { request } from './api';

export type PermissionKind = 'camera' | 'microphone' | 'lesson_alarm';
export type Permission = { kind: PermissionKind; granted: boolean; decided_at: string | null; policy_version: string };
export type Permissions = { student_id: string; permissions: Permission[]; input_available: false };
export const getPermissions = (studentId: string) => request<Permissions>(`/api/consent/${studentId}`);
export const setPermission = (studentId: string, kind: PermissionKind, granted: boolean) => request<Permissions>(`/api/consent/${studentId}/${kind}`, { method: 'PUT', body: JSON.stringify({ granted }) });
