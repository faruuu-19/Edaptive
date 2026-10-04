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
 * One node of the curriculum graph (unit or lesson). Produced by the Curriculum Compiler (Track C); read by every module that needs to know where a student is.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "CurriculumNode".
 */
export interface CurriculumNode {
  /**
   * Stable dotted id: <subject>.g<grade>[.<segment>]*, e.g. math.g3.m5.l12. Never reuse or renumber once published.
   */
  id: string;
  subject: "math" | "english" | "science";
  grade: number;
  level: "unit" | "lesson";
  title: string;
  parent_id: string | null;
  /**
   * Position among siblings, starting at 1.
   */
  order: number;
  prerequisites: string[];
  objectives?: string[];
  source: {
    name: string;
    url?: string;
    license: string;
  };
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
   * Stable dotted id: <subject>.g<grade>[.<segment>]*, e.g. math.g3.m5.l12. Never reuse or renumber once published.
   */
  node_id?: string;
}
/**
 * A lesson is data, not code: the engine interprets this file. Authoring a lesson means editing JSON only. Widget content belongs to Track B's widget schema; check specs belong to Track A's verifiers.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Lesson".
 */
export interface Lesson {
  schema_version: 1;
  /**
   * Stable dotted id: <subject>.g<grade>[.<segment>]*, e.g. math.g3.m5.l12. Never reuse or renumber once published.
   */
  node_id: string;
  title: string;
  subject: "math" | "english" | "science";
  grade: number;
  objectives?: string[];
  /**
   * @minItems 1
   */
  steps: [Step, ...Step[]];
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "Step".
 */
export interface Step {
  step_id: string;
  kind: "explain" | "practice" | "check";
  prompt?: string;
  widget?: WidgetRef;
  check?: Check;
}
/**
 * PLACEHOLDER owned by Track B (Widget Schema, Mid-1). Only the outer shape is fixed here so lessons can reference widgets; Track B tightens props per widget_type.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "WidgetRef".
 */
export interface WidgetRef {
  widget_type: string;
  props: {};
}
/**
 * Which deterministic verifier judges the answer, and its input. The shape of spec is owned by Track A.
 *
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "Check".
 */
export interface Check {
  verifier: "sympy" | "grammar" | "concept_card";
  spec: {};
}
