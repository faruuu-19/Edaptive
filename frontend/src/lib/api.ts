import type { EventEnvelope } from "@/contracts/generated";

// Shared client for the local backend. Feature code calls these helpers instead of fetch()
// so every request goes through one place.
const base = typeof window === "undefined" ? (process.env.EDAPTIVE_API_URL ?? "http://localhost:8000") : "";

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${base}/api/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`API ${status}`);
  }
}

/** Append one event to the shared session log. Safe to retry: the same event_id is stored once. */
export async function appendEvent(event: EventEnvelope): Promise<number> {
  const res = await fetch(`${base}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
  });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  return (await res.json()).seq;
}
