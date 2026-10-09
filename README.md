# Edaptive (SchoolOS)

Final Year Project — a local-model homeschool "operating system" combining a
Socratic AI tutor, interactive lesson widgets, live scheduled classes, mastery
tracking, and a parent dashboard. Scope: Grades 1–5, across Math, English,
and Science. Built on local/open-source models only — no paid APIs.

## Why

Homeschooled students move forward through a curriculum without the
continuous correction a classroom teacher provides. Edaptive pairs an
open-ended LLM tutor with deterministic answer verification, so a student
never advances on a reasoning error the system failed to catch.

## Modules

| Module | What it does |
|---|---|
| **A — LLM Orchestration** | Socratic prompting: speech/text in → curriculum node + student mastery → LLM → structured JSON (dialogue, widget trigger, avatar state) |
| **B — Deterministic Verification** | Intercepts the LLM's reasoning before it reaches the student; checks it against SymPy (Math) / spaCy + LanguageTool + WordNet (English) / concept-card retrieval (Science); classifies misconceptions, not just right/wrong |
| **C — Declarative UI & Avatar** | Mounts interactive widgets (fraction bars, number lines, base-ten blocks, science sims) from LLM-issued JSON; lip-synced tutor avatar with explaining/encouraging/thinking/celebrating states |
| **D — Edge Attention Monitoring** | Client-side (MediaPipe/WASM) engagement scoring — no video leaves the device, gated behind parental consent |
| **E — Live Delivery, Scheduling & Assessment** | Daily timetable, live lesson player with pre-class ready-check, 24-hour replay library, scheduled quizzes with immediate feedback |
| **F — Parent Dashboard & Consent** | Progress/weak-topic visibility, homework/quiz monitoring, schedule controls, camera/mic consent management |

## Team

| Member | Owns |
|---|---|
| Faryal | Modules A & B — prompting architecture, verification bridge, misconception classification |
| Amna | Module C + frontend half of E — widget engine, avatar state machine, live lesson player, replay UI |
| Ibrahim | Data infra, auth & profiles, Module D, backend half of E, Module F — curriculum ingestion, scheduling engine, data model, parent dashboard backend |

## Repo layout

```
contracts/   # Shared JSON Schemas: events, lessons, curriculum, widgets, tutor actions
backend/     # FastAPI: session log, curriculum, scheduling, assessment, consent, parent, LLM + verifiers
frontend/    # Next.js: widgets, avatar, lesson player, home/profile, timetable, dashboards
tools/       # Codegen (contracts → Python + TypeScript types)
docs/        # Proposal, curriculum sourcing, architecture, roadmap, contributing
```

## Getting started

Needs: Python via [uv](https://docs.astral.sh/uv/), Node 20.9+, Docker (for Postgres 16 + pgvector).

```bash
make setup            # install dependencies
make db-up migrate    # start the database and apply migrations
make dev-backend      # http://localhost:8000/docs
make dev-frontend     # http://localhost:3000
make check            # lint, boundaries, tests, build; run before every PR
```

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before your first PR, and
[docs/ROADMAP.md](docs/ROADMAP.md) for build order.

## Status

Build phase (proposal defended Sept 2026). FYP-1 evaluation: 7–11 Dec 2026.

## Curriculum sources

- Maths: [EngageNY Mathematics (archive.org mirror)](https://archive.org/download/engageny-mathematics) — CC BY-NC-SA
- Science: [Core Knowledge Foundation free curriculum](https://www.coreknowledge.org/download-free-curriculum/)
- English: [taleem360.com — FBISE/Federal textbooks](https://www.taleem360.com/class-1-english-federal-text-book-pdf-fbise-gsf) (FBISE Grades 1–3, Punjab PCTB Grades 4–5; see [docs/curriculum-sources.md](docs/curriculum-sources.md))

## Assessment card coverage

**One concept JSON file now has one matching assessment JSON file.**
The 26 existing lesson assessments are combined into **10 assessment JSON
collections** matching 10 source concept JSON files: six in Grade 1 and four
in Grade 2. Each filename follows `<source JSON stem>.assessment_card.json`,
and sits beside the source JSON. Multi-lesson sources have all their existing
lesson assessments in that one file's `cards` array, in source order.

```text
Mathematics — 10 matched JSON pairs / 26 lesson assessment entries
├── Grade 1 — 6 pairs / 6 entries
│   ├── Module 1 → Lesson 1 → 1 pair
│   ├── Module 2 → Lesson 1 → 1 pair
│   ├── Module 3 → Lesson 1 → 1 pair
│   ├── Module 4 → Lesson 1 → 1 pair
│   ├── Module 5 → Lesson 1 → 1 pair
│   └── Module 6 → Lesson 1 → 1 pair
└── Grade 2 — 4 pairs / 20 entries
    ├── Module 1 → Lessons 1–8 combined in source → 1 pair / 1 entry
    ├── Module 3 → Lesson 1 included in source → 1 pair / 1 entry
    ├── Module 5 → Lessons 1–8 assessed → 1 pair / 8 entries
    └── Module 6 → Lessons 1–10 assessed → 1 pair / 10 entries
```

| Grade | Module | Source concept JSON | Matching assessment JSON | Assessments / source concepts | Coverage |
|---|---|---|---|---|---|
| 1 | 1 | [math_g1_m1_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%201/Module%201/math_g1_m1_l1_lesson.json) | [math_g1_m1_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%201/Module%201/math_g1_m1_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 1 | 2 | [math_g1_m2_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%202/Module%202/Math%20G1-M2%20Lessons/math_g1_m2_l1_lesson.json) | [math_g1_m2_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%202/Module%202/Math%20G1-M2%20Lessons/math_g1_m2_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 1 | 3 | [math_g1_m3_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%203/Module%203/Math%20G1-M3%20Lessons/math_g1_m3_l1_lesson.json) | [math_g1_m3_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%203/Module%203/Math%20G1-M3%20Lessons/math_g1_m3_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 1 | 4 | [math_g1_m4_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%204/Module%204/Math%20G1-M4%20Lessons/math_g1_m4_l1_lesson.json) | [math_g1_m4_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%204/Module%204/Math%20G1-M4%20Lessons/math_g1_m4_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 1 | 5 | [math_g1_m5_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%205/Module%205/Math%20G1-M5%20Lessons/math_g1_m5_l1_lesson.json) | [math_g1_m5_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%205/Module%205/Math%20G1-M5%20Lessons/math_g1_m5_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 1 | 6 | [math_g1_m6_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%206/Module%206/Math%20G1-M6%20Lessons/math_g1_m6_l1_lesson.json) | [math_g1_m6_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%206/Module%206/Math%20G1-M6%20Lessons/math_g1_m6_l1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 2 | 1 | [math_g2_m1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/math_g2_m1_lesson.json) | [math_g2_m1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/math_g2_m1_lesson.assessment_card.json) | 1 / 1 | Complete |
| 2 | 3 | [math_g2_m3_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/math_g2_m3_Lessons.json) | [math_g2_m3_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/math_g2_m3_Lessons.assessment_card.json) | 1 / 1 | Complete |
| 2 | 5 | [math_g2_m5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.json) | [math_g2_m5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.assessment_card.json) | 8 / 20 | Partial |
| 2 | 6 | [math_g2_m6_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.json) | [math_g2_m6_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.assessment_card.json) | 10 / 20 | Partial |

This change combines existing assessments; it creates no new lesson content.
Module 5 has assessments for 8 of its 20 included concept cards; Lessons 9–20
remain unassessed. Module 6 has assessments for 10 of its 20 cards; Lessons 11–20
remain unassessed. Both collections mark `coverage.status` as `partial` and list
`missing_concept_ids`. The other eight pairs cover every concept card included
in their source file. Complete file coverage does not mean reviewed for delivery.

Grade 2 Module 1 contains one combined concept card for Lessons 1–8. Module 3's
source contains only Lesson 1, although its source manifest expects 21 lessons
and marks the other concept cards pending. Neither file is split into invented
lesson cards. The other 14 lesson JSON files in the curriculum have no generated
assessments yet; no empty assessment files are used to imply coverage.

Each output root is an `assessment_card_collection` with source-file identity,
coverage and a `cards` array. Each array entry remains a complete v0.2 assessment:
one reused easy question, generated medium and three-part hard questions,
two follow-ups, four local rubrics, 15 progressive hints and five tutor guidance
records. Across all collections: **78 main questions, 52 follow-ups, 104 local
rubrics, 390 hints and 130 guidance records**. All lesson IDs, prompts, hints,
answers, rubrics, routes and worked solutions are preserved exactly.

For a script agent, load the concept source and matching assessment collection,
then match each assessment to its concept using `linked_concept.concept_id`.
Do not match by array position: the two partial collections omit unassessed
lessons. Question, rubric, hint and asset IDs remain scoped to that lesson pair.
See [the collection contract and loader example](docs/assessment-card-collections.md)
and [the lesson assessment contract](docs/assessment-cards-v0.2.md).

Validation confirms 10 matched filenames/source hashes, 26 preserved entries,
scoped references, original source order, accurate missing-lesson lists, and no
lost or duplicated assessments. JSON files use UTF-8 with 2-space indentation.
[Collection validation evidence](docs/assessment-card-collections-validation.json)
records the results. The existing answer checks, 202 worked-solution equation
checks, 624 routing scenarios and seven multipart classification scenarios remain
applicable because the lesson entries were preserved without changes.

All entries remain drafts with `ready_for_delivery: false`; human educational
review and eventual script-agent integration tests are still required. Source
metadata and worksheet-numbering uncertainties remain in the linked concept
cards. Individual assessment files were replaced by these collections in this
branch so each covered source JSON has exactly one assessment JSON beside it.
