# Data model (proposal for team review)

Status: **proposal**, owned by Track C. Every track builds on this, so all three of us sign
it off. Tables marked ✅ already exist on `main`; everything else is the plan.

Requirements here are taken from the handoff, the README modules (A–F), `docs/ROADMAP.md`
and the curriculum data already in the repo. **Check them against the accepted proposal**:
if the proposal promises something not listed, add it here before we build.

## 1. Requirements that shape the database

| # | Requirement | Source | What it means for the DB |
|---|---|---|---|
| R1 | Offline, local only; no cloud | Handoff §2 | One local Postgres 16 (+ pgvector). No external warehouse; analytics live in the same DB. |
| R2 | Session log is event-sourced: every student action, verdict, tutor action and attention signal is appended | Handoff §4 | One append-only `event` table is the source of truth for **activity**. ✅ |
| R3 | Dashboard, replay and evaluation all read from the log | Handoff §4 | Read models (projections) built from the log in a separate `analytics` schema, rebuildable at any time. |
| R4 | Lessons are data, not code | Handoff §4 | Content is stored as validated JSON documents (concept cards, assessment cards), with key fields extracted for queries. |
| R5 | Verification-first; the model never decides truth | Handoff §1–2 | Every tutor claim and its verifier verdict is logged, so the hallucination audit can be computed. |
| R6 | Maths → SymPy, English → grammar tools, Science → RAG over approved concept cards | Handoff §2 | Science needs searchable concept-card chunks with embeddings (pgvector), Final-2. |
| R7 | Mastery tracking; misconception classification; adaptive engine | README A/B, roadmap | Mastery per student per concept as a projection; misconception ids on verdict events. |
| R8 | Daily timetable, pre-class ready-check, scheduled quizzes with immediate feedback | README E | Schedule templates → daily slots; quiz runs with live state; answers and feedback as events. |
| R9 | 24-hour replay library | README E | Replay is a view over a session's events, available for 24 h. No media stored. |
| R10 | Parent dashboard: progress, weak topics, homework/quiz monitoring, schedule controls | README F | Projections per student/day/concept; parent-only schedule rules. |
| R11 | Camera/mic consent; attention processed on device; no video stored | Handoff §2, README D/F | Consent history table; only numeric engagement scores reach the server, and only with consent. |
| R12 | Minimise minors' data; privacy controls | Handoff §2, roadmap Final-2 | Minimal profile fields ✅; retention and erasure rules (see §7). |
| R13 | Each iteration demoable; maths first | Handoff §3 | Build tables in iteration order (§8); Mid-1 needs only content + sessions + Mid-1 events. |

## 2. Shape: four layers

```
            ┌──────────────── content ────────────────┐   read-only at runtime;
            │ curriculum modules, concept cards,       │   loaded by the Curriculum
            │ assessment cards, prerequisites, chunks  │   Compiler from /ciriculam
            └──────────────────────────────────────────┘
┌──────── operational (public) ────────┐   ┌──────── log (public.event) ────────┐
│ household, profiles, auth, sessions, │──▶│ append-only events: what happened  │
│ schedules, quiz runs, consent, rules │   │ (single source of truth for        │
│ = current state needed to run        │   │  activity)                         │
└──────────────────────────────────────┘   └──────────────────┬─────────────────┘
                                                              │ projectors replay in seq order
                                           ┌──────────────────▼─────────────────┐
                                           │ analytics: the local "warehouse"   │
                                           │ facts + summaries for dashboards,  │
                                           │ mastery, replay, FYP evaluation    │
                                           └────────────────────────────────────┘
```

Rules:
- **Content** is versioned and never edited in place: a changed card is a new `card_version`.
  Events always record which version a child saw.
- **Operational tables** hold only the state needed to run *right now* (what's scheduled,
  which quiz attempt is open, who consented). They are not the history.
- **The log** is the history. Modules append; nothing updates or deletes (DB triggers ✅),
  except the privacy erasure job in §7.
- **Analytics** is derived. Any table there can be dropped and rebuilt by replaying the log.
  Only that table's projector writes to it.

Postgres schemas: `content`, `public` (operational + log, as today) and `analytics`.

## 3. Content (`content` schema): written only by the Curriculum Compiler (Track C)

Formats are owned by their authors: concept card by Track A (Faryal), assessment card by
Track B (Amna). The compiler validates each file against its schema and loads it. Whole
documents are kept in `body` (JSONB, "lessons are data"); fields we filter or join on are
extracted into columns.

| Table | Key columns | Notes |
|---|---|---|
| `curriculum_module` | `module_id` PK (`math_g3_m5`), subject, grade, module_no, title, lessons_expected | One row per module file. |
| `concept_card` | PK (`concept_id`, `card_version`), module_id, lesson_no, schema_version, review_status, objective_text, standards text[], `body` jsonb, content_hash, is_current | `concept_id` is Faryal's id (`math_g3_m5_l1_<name>`). Questions, rubrics and hints stay inside `body`. |
| `concept_prerequisite` | concept_id, prerequisite_id, is_external | 136 prerequisites point at Kindergarten or not-yet-built cards, so they're kept but flagged, not foreign keys. |
| `assessment_card` | PK (`assessment_card_id`, `card_version`), concept_id + concept_version (FK), review_status, ready_for_delivery, `body` jsonb | Amna's lesson-level assessments. |
| `module_assessment` | PK (`assessment_id`, `card_version`), module_id, review_status, `body` jsonb | End-of-module assessments. |
| `concept_chunk` | chunk_id, concept_id, card_version, kind (explanation / example / misconception), text, embedding vector | Final-2: Science RAG and citations. Dimension set by the chosen local embedding model. |
| `load_run` | run_id, git_sha, started_at, files, loaded, rejected, errors jsonb | Audit of every compiler run. |

Delivery rule: the runtime serves only `review_status = 'reviewed'` content, unless the
setting `allow_draft_content` is on (dev and demo). All 471 cards are `draft` today.

## 4. Operational (`public` schema)

| Table | Owner | Ships | Key columns |
|---|---|---|---|
| `household` ✅ | C | Mid-1 | id |
| `student_profile` ✅ | C | Mid-1 | id, household_id, display_name, grade, avatar_key, archived_at |
| `parent_pin` ✅ | C | Mid-1 | household_id, pin_hash, failed_attempts, locked_until |
| `auth_session` ✅ | C | Mid-1 | token_hash, role, student_id, expires_at |
| `event` ✅ | C (infra) | Mid-1 | seq, event_id, event_type, event_version, occurred_at, source, session_id, student_id, payload |
| `learning_session` | C | Mid-1 | session_id, student_id, kind (scheduled / free_practice / quiz), slot_id, concept_id + card_version, started_at, ended_at, end_reason |
| `schedule_template` | C | Final-1 | id, student_id, weekday, start_time, minutes, subject |
| `schedule_slot` | C | Final-1 | slot_id, student_id, date, starts_at, ends_at, subject, planned concept_id, status (planned / ready / in_progress / done / missed) |
| `assessment_run` | C (runtime), A (grading) | Final-1 | run_id, student_id, session_id, assessment_card_id + version, status, `state` jsonb (attempt counters, hints used, current question), opened_at, closed_at |
| `consent` | C | Mid-2 | id, student_id, kind (camera / microphone / attention_monitoring), granted, decided_at, decided_by, policy_version. One row per decision, so history is kept. |
| `schedule_rule` | C | Final-2 | household or student scope, allowed hours, max minutes per day, break rules |
| `privacy_setting` | C | Final-2 | household_id, replay_hours (default 24), retention_days, transcripts_kept |

`learning_session` and `assessment_run` hold live state. Everything that happens inside
them is also an event.

## 5. The event catalog (the contract between tracks)

Envelope ✅: `event_id, event_type, event_version, occurred_at, source, session_id,
student_id, payload`. Every event about content carries `concept_id` and `card_version`.
Each track owns its namespace and confirms its list.

| Namespace | Owner | Proposed types (payload essentials) | Ships |
|---|---|---|---|
| `profile` ✅ | C | `profile.selected` | Mid-1 |
| `session` ✅ | C | `session.started` (entry, concept_id), `session.ended` (reason) | Mid-1 |
| `tutor` | A | `tutor.turn` (turn_id, action type, text shown, widget/avatar directive, llm_calls, latency_ms) | Mid-1 |
| `verifier` | A | `verifier.verdict` (turn_id, verifier: sympy / grammar / concept_card, claim, result: pass / fail / unclear, misconception_id, latency_ms) | Mid-1 |
| `student` | A + B | `student.answered` (question_id, response text or structured, input mode: touch / voice / keyboard) | Mid-1 |
| `widget` | B | `widget.mounted`, `widget.interacted` (widget_type, action, value) | Mid-1 |
| `avatar` | B | `avatar.state_changed` (state) | Mid-1 |
| `mastery` | A | `mastery.updated` (concept_id, from, to, evidence) | Final-1 |
| `misconception` | A | `misconception.detected` (concept_id, misconception_id, question_id) | Final-1 |
| `remediation` | A | `remediation.started` / `remediation.completed` | Final-1 |
| `assessment` | C | `assessment.started`, `assessment.answer_graded` (question_id, outcome: correct / partial / incorrect / unclear / incomplete, attempt_no, hint_level), `assessment.hint_given`, `assessment.answer_revealed`, `assessment.completed` (score) | Final-1 |
| `schedule` | C | `schedule.slot_ready_check` (passed, checks), `schedule.slot_missed` | Final-1 |
| `voice` | B | `voice.transcribed` (text, confidence; never audio) | Final-1 |
| `replay` | B | `replay.opened` | Final-1 |
| `reward` / `nudge` | B | `reward.earned` (kind), `nudge.shown` (reason) | Mid-2 |
| `attention` | C | `attention.sampled` (window_s, engagement 0–1, face_present). Only when consent is on; never images. | Mid-2 |
| `consent` | C | `consent.granted` / `consent.revoked` (kind) | Mid-2 |
| `parent` | C | `parent.schedule_changed`, `parent.privacy_changed` | Final-2 |
| `privacy` | C | `privacy.erased` (scope, counts): a tombstone left by erasure | Final-2 |

A student event with no session (e.g. `profile.selected`) has `session_id = null` ✅.

## 6. Analytics (`analytics` schema): the local warehouse

Projectors read `event` in `seq` order and record a checkpoint, so they resume where they
stopped and can be rebuilt from zero. Laid out as a small star schema so the parent
dashboard and the FYP evaluation query the same facts.

**Dimensions** (views over content and operational tables): `dim_student`, `dim_concept`
(concept → module → grade → subject), `dim_date`, `dim_verifier`.

| Table | Grain | Built from | Used by | Owner | Ships |
|---|---|---|---|---|---|
| `projector_checkpoint` | one row per projector | — | all projectors | C | Mid-1 |
| `fact_session` | one row per session | session.*, tutor.*, student.* | parent dashboard, replay list | C | Mid-1 |
| `fact_verification` | one row per verifier verdict | verifier.verdict, tutor.turn | **hallucination audit, FYP evaluation** | A | Mid-1 |
| `fact_answer` | one row per graded answer | assessment.*, student.answered, verifier.verdict | progress, weak topics, quiz monitoring | C | Final-1 |
| `mastery` | student × concept | mastery.updated | adaptive engine, dashboard | A | Final-1 |
| `concept_progress` | student × concept | fact_answer | progress dashboard, weak topics | C | Final-1 |
| `daily_activity` | student × day | sessions, answers, attention | parent dashboard | C | Final-1 |
| `replay_index` | session, available until +24 h | session.*, privacy_setting | replay library | B | Final-1 |
| `engagement_summary` | student × session | attention.sampled | engagement indicator | C | Mid-2 |
| `schedule_adherence` | slot | schedule.*, session.* | parent dashboard | C | Final-2 |

The evaluation numbers the FYP report will need (verification pass rate, rejected claims
per subject, latency, accuracy and mastery over time) are plain SQL over these facts.
`make export` can dump them to CSV for notebooks, all offline.

## 7. Privacy and retention: decisions needed

1. **What is stored from the child?** Proposal: text transcripts only, never audio; numeric
   engagement scores only, never camera frames.
2. **Replay "24 hours":** the replay *list* hides sessions after 24 h, but their events stay
   for mastery and progress. Or should the events themselves be deleted?
3. **Erasure vs append-only:** a parent must be able to delete a child's data. Proposal: one
   privileged job (Track C) erases a student's rows from `event` and projections through a
   guarded DB function, then appends a `privacy.erased` tombstone. No other code can delete.
4. **Retention period** for events (e.g. keep 1 school year), set in `privacy_setting`.

## 8. Build order

| Iteration | Tables / projections |
|---|---|
| Mid-1 | `content.*` (maths), `learning_session`, `analytics.projector_checkpoint`, `fact_session`, `fact_verification`, and the Mid-1 events (`tutor`, `verifier`, `student`, `widget`, `avatar`) |
| Final-1 | `schedule_template`, `schedule_slot`, `assessment_run`, `fact_answer`, `mastery`, `concept_progress`, `daily_activity`, `replay_index` |
| Mid-2 | `consent`, `engagement_summary`, attention and consent events |
| Final-2 | `concept_chunk` + embeddings, `schedule_rule`, `privacy_setting`, erasure job, `schedule_adherence` |

## 9. Open decisions (blocking marked ●)

| | Decision | Proposed default | Who |
|---|---|---|---|
| ● | Concept card + assessment card are the official content formats; schemas move into `contracts/` | Yes | A, B, C |
| ● | Content ids are Faryal's `math_g<g>_m<m>_l<l>_<name>` | Yes | A, C |
| ● | One file layout per content file (one collection shape) | One `cards` collection | A, B |
| ● | Each track confirms its event types in §5 for Mid-1 | — | A, B |
| | Draft content allowed in dev and demo (`allow_draft_content`) | Yes | All |
| | Assessment runtime in Track C's module, grading by Track A's verifiers, routing spec from Amna's controller | Yes | All |
| | Privacy items in §7 | As proposed | All |
| | Local embedding model (sets the vector size) | Decide by Final-2 | A |
