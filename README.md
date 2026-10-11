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

**One covered concept JSON file has one matching assessment JSON file.**
There are **48 lesson assessment entries in 10 assessment JSON collections**,
matching six source files in Grade 1 and four in Grade 2. Each assessment file
is named `<source JSON stem>.assessment_card.json` and sits beside its source.
Its `cards` array contains the assessed concepts in source order.

The latest batch adds **Grade 2 Module 6 Lessons 11–20**. Modules 5 and 6 now
both cover all 20 concepts included in their source files. The previous
38 assessment entries are preserved exactly.

```text
Mathematics — 10 matched JSON pairs / 48 lesson assessment entries
├── Grade 1 — 6 pairs / 6 entries
│   ├── Module 1 → Lesson 1 → 1 pair
│   ├── Module 2 → Lesson 1 → 1 pair
│   ├── Module 3 → Lesson 1 → 1 pair
│   ├── Module 4 → Lesson 1 → 1 pair
│   ├── Module 5 → Lesson 1 → 1 pair
│   └── Module 6 → Lesson 1 → 1 pair
└── Grade 2 — 4 pairs / 42 entries
    ├── Module 1 → Lessons 1–8 combined in source → 1 pair / 1 entry
    ├── Module 3 → Lesson 1 included in source → 1 pair / 1 entry
    ├── Module 5 → Lessons 1–20 assessed → 1 pair / 20 entries
    └── Module 6 → Lessons 1–20 assessed → 1 pair / 20 entries
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
| 2 | 5 | [math_g2_m5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.json) | [math_g2_m5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.assessment_card.json) | 20 / 20 | Complete |
| 2 | 6 | [math_g2_m6_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.json) | [math_g2_m6_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.assessment_card.json) | 20 / 20 | Complete |

All ten collections cover every concept included in their source JSON, with
empty `coverage.missing_concept_ids` lists. Complete coverage describes the
included source content; it does not mean reviewed for delivery or that all
curriculum files have assessments.

Grade 2 Module 1 has one combined concept card for Lessons 1–8. Module 3's
source includes only Lesson 1 although its manifest expects 21 lessons and
marks the other concepts pending. The other 14 lesson JSON files in the
curriculum have no generated assessments yet.

Each collection contains complete v0.2 lesson assessments: one reused easy
practice question, generated medium and three-part hard questions, two
follow-ups, four local rubrics, 15 progressive hints and five tutor guidance
records. Across all collections: **144 main questions, 96 follow-ups, 192
local rubrics, 720 hints and 240 guidance records**. Guidance covers correct,
partial, incorrect, unclear and incomplete responses; help, silence, retries,
follow-up returns and worked-answer reveals have explicit rules.

For a script agent, load the source and its matching collection, then match
by `linked_concept.concept_id`. Match IDs even when both files contain the same number of entries; future
partial collections can omit unassessed lessons. Question, rubric, hint and asset IDs
remain scoped to each concept/assessment pair. See the
[collection contract and loader example](docs/assessment-card-collections.md)
and [lesson assessment contract](docs/assessment-cards-v0.2.md).

Python validation checks JSON parsing, field coverage, source hashes and order,
all references, answer keys and accept variants, original-entry preservation,
coverage lists and ZIP byte equality. Cumulative validation covers **497
worked-solution equations, 1,170 tutoring-route scenarios and seven multipart
classification scenarios**. [Collection validation](docs/assessment-card-collections-validation.json)
records current coverage; [new-batch validation](docs/assessment-cards-grade2-module6-lessons11-20-validation.json)
records the independently recomputed answers and checks for the ten new entries.
The [previous Module 5 validation](docs/assessment-cards-grade2-module5-lessons9-20-validation.json)
records the twelve additions that completed that module.

All entries remain drafts with `ready_for_delivery: false`; human educational
review and script-agent integration tests remain outstanding. Reused easy
items follow their source practice questions; some calculation items require
several place value actions. Numeric answers assess strategy use, while guidance
models why a method helps. Module 6 Lessons 18–20 also reuse open questions
whose linked rubrics grade explanations and permit partial credit for a correct
classification without its reason. Generated parity questions use explicit
numeric labels: 1 for even and 2 for odd/not even. Drawing prompts explain equal
squares and shared lines, but numeric answers do not verify the drawing itself.
Module 5 Lesson 11's source `exp_1` says its tens total is 10; including the new ten gives 11. The
assessment's worked answer uses the correct arithmetic and preserves the
original concept file. Source metadata and worksheet-numbering uncertainties
remain in the concept cards.
