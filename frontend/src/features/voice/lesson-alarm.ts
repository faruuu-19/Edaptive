import { LocalAlarm } from "./local-alarm";

let shared: LocalAlarm | null = null;
/** One alarm for the whole page, so a parent's click can unlock the sound the child's device later plays. */
export function lessonAlarm(): LocalAlarm {
  shared ??= new LocalAlarm();
  return shared;
}
