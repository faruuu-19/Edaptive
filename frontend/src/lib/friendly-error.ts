import { ApiError } from "./api";

// Plain sentences the backend writes for a child (class rules). Everything else is technical.
const CHILD_SAFE = /^(Listen to the current part|Complete the current part|Complete the lesson|You can snooze|You are not in a class|This class has finished|Wait for class time)/;

/** What a child sees when something goes wrong: never a status code or a service name. */
export function childMessage(error: unknown): string {
  const detail = error instanceof ApiError ? error.detail : error instanceof Error ? error.message : null;
  if (typeof detail === "string" && CHILD_SAFE.test(detail)) return detail;
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please choose your profile again to carry on.";
  }
  return "Your teacher isn’t ready yet. Please wait a moment and try again. If it keeps happening, tell a grown-up.";
}
