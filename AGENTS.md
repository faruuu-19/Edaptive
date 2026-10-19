# Edaptive: notes for coding agents

Edaptive is an offline, local-model homeschool tutor for Grades 1–5 (FAST NUCES FYP, team
of 3). The AI proposes and a deterministic tool verifies: the model never decides truth.
Read `README.md`, then `docs/CONTRIBUTING.md` and `docs/ARCHITECTURE.md` before changing code.

## Hard rules

- **Offline only.** No paid APIs, cloud services, CDNs or remote fonts at runtime.
- **Scope is frozen** to the accepted proposal. Don't add features nobody agreed.
- **Verification first.** No unverified LLM output reaches the UI. The LLM is called only
  from the Socratic Engine (Track A), 1–2 calls per turn, with schema-constrained output.
- **Children's data stays minimal** and consent-gated. Attention processing stays in the
  browser; no video is stored.

## How the code fits together

- Shared shapes live in `contracts/` (JSON Schema). Build against them, not other modules'
  internals. After changing a contract, run `make gen` and commit the output.
- Modules share data only through contracts and the append-only session log
  (`/api/events`), and the log rejects unregistered event types. Backend modules never
  import each other; frontend features import each other only via their `index.ts`.
  Tooling enforces both.
- Identity comes from `app/core/identity.py` (`CurrentActor`, `ParentActor`,
  `ensure_student_access`). Never read cookies, PINs or tokens in feature code.
- Each folder's owning track is in `.github/CODEOWNERS`. Only change your own track's
  folders; propose contract changes in a separate PR.
- Tables, the full event catalog and the analytics layer are in **`docs/DATA-MODEL.md`**.

## Where code goes

| Track | Backend (`backend/app/modules/<name>/`) | Frontend (`frontend/src/features/<name>/`) |
|---|---|---|
| A: AI & verification (Faryal) | `socratic`, `verification`; later `misconception`, `adaptive`, `remediation`, `grammar`, `science_rag` | `verification-badge`, `citation-overlay` |
| B: front-end, avatar & voice (Amna) | `lesson_delivery` ✅, `attendance` ✅ (Track C reviews storage and scheduling changes); repo root: `voice_service/`, `script_agent/` | `voice` ✅, `lesson-player` ✅, `widgets`, `avatar`, `replay`, `rewards` |
| C: data, scheduling & parent (Ibrahim) | `auth` ✅, `profiles` ✅, `consent` ✅ (built by B), `curriculum`, `scheduling`, `assessment`, `attention`, `parent` | `auth` ✅, `home-profile` ✅, `parent` ✅ (shared with B), `timetable`, `progress`, `attention` |

- New module: create its folder, add `router.py` exposing `router` (mounted automatically at
  `/api/<name>`), give it a README naming its owner, and add the path to `.github/CODEOWNERS`.
- Curriculum content goes in `ciriculam/grade<N>/<module_id>_Lessons.json`, one `cards`
  collection per file; assessment cards sit beside their concept file.
- New tables: follow `docs/DATA-MODEL.md` and add an Alembic migration in
  `backend/migrations/versions/`. Track C reviews every migration.

## Content ids (official format)

Ids come from the curriculum data and are defined in `contracts/common/ids.schema.json`.
They never carry a version: the version is a separate `card_version` integer.

| Thing | Format | Example |
|---|---|---|
| Module | `<subject>_g<grade>_m<module>` | `math_g3_m5` |
| Concept card (one lesson) | `<subject>_g<grade>_m<module>_l<lesson>_<short_name>` | `math_g1_m1_l1_embedded_numbers` |
| Lesson assessment card | `assess_<concept_id>` | `assess_math_g1_m1_l1_embedded_numbers` |
| End-of-module assessment | `<module_id>_end_of_module_assessment` | `math_g1_m1_end_of_module_assessment` |

Subjects are `math`, `english`, `science`; grades 1–5; all lower case. Question, rubric and
hint ids (e.g. `aq_easy_01`) are only unique inside their card, so always send them together
with the card id.

## Writing to the session log (or it will be rejected)

Every event uses this envelope (`contracts/events/envelope.schema.json`), with no extra fields:

```json
{
  "event_id": "<new uuid4 per event; resending the same id is a safe no-op>",
  "event_type": "<namespace>.<name>, e.g. verifier.verdict",
  "event_version": 1,
  "occurred_at": "<ISO 8601 with timezone, e.g. 2026-10-12T09:00:00+05:00>",
  "source": "<your module name, lower_snake, e.g. socratic>",
  "session_id": "<learning session uuid, or null outside a session>",
  "student_id": "<student profile uuid; null only for household-level events>",
  "payload": { "...exactly the fields in that event's payload schema..." }
}
```

Any event about content puts `concept_id` and `card_version` (and `assessment_card_id` +
`question_id` where relevant) in its payload.

**Emitting:** in the backend call `append(db, event)` from `app.session_log` with the request's
`DbSession`; in the frontend call `appendEvent(event)` from `@/lib/api`. The caller must be
signed in, and a student can only log events with their own `student_id`. Never write to the
`event` table with SQL, and never update or delete events.

**Rejected (HTTP 422) when:** a field is missing or extra; the type isn't registered;
`event_version` doesn't match the registry; the payload doesn't match its schema; or an id
doesn't match the formats above. You get 401 if not signed in and 403 for another child's
`student_id`.

**Adding a new event type** (only in your own track's namespace):
1. Use the name and fields proposed in `docs/DATA-MODEL.md` §5, unless the team agreed otherwise.
2. Write `contracts/events/payloads/<event_type>.v1.schema.json` with `"additionalProperties": false`.
   Reference ids from `../../common/ids.schema.json#/$defs/...`; don't redefine them.
3. Register it in `contracts/events/registry.json`: `"<event_type>": {"version": 1, "payload": "payloads/<event_type>.v1.schema.json"}`.
4. Add a valid example at `contracts/examples/events/<event_type>.json`. Tests validate it.
5. Run `make gen` and `make check`, then open a `contracts/…` PR for all three tracks to review.
6. Changing a payload later: add fields as optional, or create `.v2` and bump `version`.
   Never edit a released schema in a breaking way.

| Namespace | Owner |
|---|---|
| `tutor`, `verifier`, `misconception`, `mastery`, `remediation` | Track A |
| `student`, `widget`, `avatar`, `voice`, `lesson`, `replay`, `reward`, `nudge` | Track B |
| `session`, `profile`, `auth`, `curriculum`, `schedule`, `assessment`, `attention`, `consent`, `parent`, `privacy` | Track C |

## UI: follow the Storybook theme

All UI uses the theme in **`docs/DESIGN.md`**: paper background, navy ink outlines, tomato
and mustard accents, flat offset shadows, Fraunces headings and Andika body text, inline SVG
icons and no emoji, light theme only. Use the tokens and classes in
`frontend/src/app/globals.css`; don't hard-code colours or add another look.
Subject colours: Maths = tomato, English = mustard, Science = teal.

## Before every PR

```bash
make check
```

It runs codegen, lint, module boundaries, backend tests against Postgres and the frontend
build. Fill in the PR template's checklist.
