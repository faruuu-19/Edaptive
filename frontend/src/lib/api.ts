import type { Actor, EventEnvelope } from "@/contracts/generated";

// Shared client for the local backend. Feature code calls these helpers instead of fetch()
// so every request goes through one place. The browser holds an HTTP-only session cookie
// set by the auth endpoints; features never see or attach tokens themselves.
const base = typeof window === "undefined" ? (process.env.EDAPTIVE_API_URL ?? "http://localhost:8000") : "";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
    public retryAfter?: number,
  ) {
    super(typeof detail === "string" ? detail : `API ${status}`);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    cache: "no-store",
    credentials: "same-origin",
    ...init,
    headers: init.body ? { "Content-Type": "application/json", ...init.headers } : init.headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const retry = res.headers.get("Retry-After");
    throw new ApiError(res.status, body?.detail ?? null, retry ? Number(retry) : undefined);
  }
  return res.status === 204 || res.headers.get("content-length") === "0"
    ? (undefined as T)
    : ((await res.json().catch(() => undefined)) as T);
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export async function checkHealth(): Promise<boolean> {
  try {
    await request("/api/health");
    return true;
  } catch {
    return false;
  }
}

// --- auth ---------------------------------------------------------------------------

export type AuthStatus = { setup_complete: boolean; actor: Actor | null };

export const getAuthStatus = () => request<AuthStatus>("/api/auth/status");
export const setupHousehold = (pin: string) => post<void>("/api/auth/setup", { pin });
export const unlockParent = (pin: string) => post<void>("/api/auth/parent", { pin });
export const pickProfile = (studentId: string) => post<void>("/api/auth/student", { student_id: studentId });
export const signOut = () => post<void>("/api/auth/logout");

// --- profiles -----------------------------------------------------------------------

export type Profile = { id: string; display_name: string; grade: number; avatar_key: string };
export type ProfileInput = Omit<Profile, "id">;

export const listProfiles = () => request<Profile[]>("/api/profiles");
export const getProfile = (id: string) => request<Profile>(`/api/profiles/${id}`);
export const createProfile = (input: ProfileInput) => post<Profile>("/api/profiles", input);
export const updateProfile = (id: string, input: Partial<ProfileInput>) =>
  request<Profile>(`/api/profiles/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const archiveProfile = (id: string) => request<void>(`/api/profiles/${id}`, { method: "DELETE" });

// --- session log --------------------------------------------------------------------

/** Append one event to the shared session log. Safe to retry: the same event_id is stored once. */
export async function appendEvent(event: EventEnvelope): Promise<number> {
  return (await post<{ seq: number }>("/api/events", event)).seq;
}
