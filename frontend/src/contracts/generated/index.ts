/* GENERATED from /contracts by tools/gen_contracts.sh. Do not edit. */

export interface Contracts {
  [k: string]: unknown;
}
/**
 * Who is acting on a request, as established by the auth module (Track C). Identity hierarchy: household -> parent -> students. Every module reads this; none of them establish identity themselves.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Actor".
 */
export interface Actor {
  household_id: string;
  /**
   * student: a child using their own profile. parent: the guardian, unlocked for parent-only areas (dashboard, consent, schedule and privacy controls).
   */
  role: "student" | "parent";
  /**
   * The active student profile. Required for role student; null for parent unless the parent is viewing a specific child.
   */
  student_id: string | null;
}
/**
 * One append-only entry in the session log. Every module writes and reads events in this shape. Payload shape is defined per event_type in registry.json.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "EventEnvelope".
 */
export interface EventEnvelope {
  event_id: string;
  /**
   * <namespace>.<name>. The namespace decides which track owns the type (see registry.json).
   */
  event_type: string;
  /**
   * Version of the payload schema for this event_type.
   */
  event_version: number;
  occurred_at: string;
  /**
   * Module that emitted the event, e.g. curriculum, socratic_engine, lesson_player.
   */
  source: string;
  /**
   * Learning session this belongs to; null for events outside a session (e.g. profile.selected).
   */
  session_id: string | null;
  /**
   * Student profile; null only for household-level events (e.g. parent actions).
   */
  student_id: string | null;
  /**
   * Shape depends on event_type; validated against the payload schema listed in registry.json.
   */
  payload: {
    [k: string]: unknown;
  };
}
/**
 * One attendance record per class attempt: present when the child stayed for at least 70% of the lesson.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "LessonAttendanceRecordedV1".
 */
export interface LessonAttendanceRecordedV1 {
  timetable_id: string;
  slot_id: string;
  /**
   * One lesson's concept card: <subject>_g<grade>_m<module>_l<lesson>_<short_name>, e.g. math_g1_m1_l1_embedded_numbers
   */
  concept_id: string;
  /**
   * Version of a concept or assessment card. Events record the exact version a child saw.
   */
  card_version: number;
  /**
   * The school day (Pakistan time) the attendance is for.
   */
  school_date: string;
  status: "present" | "absent";
  /**
   * completed: finished the lesson. left_after_threshold: left after staying for 70% or more. left_early: left before 70%. did_not_join: never joined that day.
   */
  reason: "completed" | "left_after_threshold" | "left_early" | "did_not_join";
  attended_percent: number;
  lesson_title?: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "LessonDeliveryChangedV1".
 */
export interface LessonDeliveryChangedV1 {
  timetable_id: string;
  slot_id: string;
  action: "start" | "borrow" | "position" | "finish" | "cancel" | "exit" | "rejoin";
  /**
   * One lesson's concept card: <subject>_g<grade>_m<module>_l<lesson>_<short_name>, e.g. math_g1_m1_l1_embedded_numbers
   */
  concept_id: string;
  /**
   * Version of a concept or assessment card. Events record the exact version a child saw.
   */
  card_version: number;
  position: number;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProfileSelectedV1".
 */
export interface ProfileSelectedV1 {}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "SessionEndedV1".
 */
export interface SessionEndedV1 {
  reason: "completed" | "exited" | "timeout";
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "SessionStartedV1".
 */
export interface SessionStartedV1 {
  /**
   * How the session began: from the timetable or as free practice.
   */
  entry: "scheduled" | "free_practice";
  /**
   * One lesson's concept card: <subject>_g<grade>_m<module>_l<lesson>_<short_name>, e.g. math_g1_m1_l1_embedded_numbers
   */
  concept_id?: string;
  /**
   * Version of a concept or assessment card. Events record the exact version a child saw.
   */
  card_version?: number;
}
