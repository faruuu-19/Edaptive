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
   * Concept card the session opens on, if known.
   */
  concept_id?: string;
  /**
   * Version of a concept or assessment card. Events record the exact version a child saw.
   */
  card_version?: number;
}
