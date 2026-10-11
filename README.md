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
There are **68 lesson assessment entries in 12 assessment JSON collections**,
matching six source files in Grade 1 and six in Grade 2. Each assessment file
is named `<source JSON stem>.assessment_card.json` and sits beside its source.
Its `cards` array contains assessed concepts in source order.

The latest batch adds **Grade 2 Module 8 Lessons 1–10**, covering shape
attributes, polygon names and drawings, quadrilateral families, cubes,
composite shapes and equal shares. Its source has 16 concepts: the matching
collection contains 10 assessments and lists Lessons 11–16 as pending.
The previous 58 entries are preserved exactly. Module 7 remains at Lessons
1–10 of 26, and Modules 5 and 6 each cover all 20 included concepts.

```text
Mathematics — 12 matched JSON pairs / 68 lesson assessment entries
├── Grade 1 — 6 pairs / 6 entries
│   ├── Module 1 → Lesson 1 → 1 pair
│   ├── Module 2 → Lesson 1 → 1 pair
│   ├── Module 3 → Lesson 1 → 1 pair
│   ├── Module 4 → Lesson 1 → 1 pair
│   ├── Module 5 → Lesson 1 → 1 pair
│   └── Module 6 → Lesson 1 → 1 pair
└── Grade 2 — 6 pairs / 62 entries
    ├── Module 1 → Lessons 1–8 combined in source → 1 pair / 1 entry
    ├── Module 3 → Lesson 1 included in source → 1 pair / 1 entry
    ├── Module 5 → Lessons 1–20 assessed → 1 pair / 20 entries
    ├── Module 6 → Lessons 1–20 assessed → 1 pair / 20 entries
    ├── Module 7 → Lessons 1–10 assessed → 1 pair / 10 entries
    │             Lessons 11–26 pending → 16 unassessed concepts
    └── Module 8 → Lessons 1–10 assessed → 1 pair / 10 entries
                  Lessons 11–16 pending → 6 unassessed concepts
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
| 2 | 7 | [math_g2_m7_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.json) | [math_g2_m7_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.assessment_card.json) | 10 / 26 | Partial |
| 2 | 8 | [math_g2_m8_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.json) | [math_g2_m8_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.assessment_card.json) | 10 / 16 | Partial |

Ten collections cover every concept included in their source JSON. Modules 7
and 8 are partial, with 22 pending concept IDs in their
`coverage.missing_concept_ids` lists. Complete coverage describes included
source content; review and delivery readiness are separate.

Grade 2 Module 1 has one combined concept card for Lessons 1–8. Module 3's
source includes only Lesson 1 although its manifest expects 21 lessons and
marks the other concepts pending. The other 12 lesson JSON files in the
curriculum have no generated assessments yet.

Each child assessment has one reused easy practice question, generated medium
and three-part hard questions, two follow-ups, four local rubrics, 15 progressive
hints and five tutor guidance records. Across all collections: **204 main
questions, 136 follow-ups, 272 local rubrics, 1,020 hints and 340 guidance
records**. Guidance defines feedback, help, silence, attempts, retries,
follow-up returns, preservation of correct hard parts and worked-answer reveals.

For a script agent, load the source and its matching collection, then match by
`linked_concept.concept_id`. Match IDs even when both files contain the same
number of entries. Question, rubric, hint and asset IDs stay scoped to each
concept/assessment pair. See the [collection contract and loader example](docs/assessment-card-collections.md)
and [lesson assessment contract](docs/assessment-cards-v0.2.md).

Python validation checks JSON parsing, exact field coverage, source hashes and
order, references, answers and accept variants, original-entry preservation,
coverage lists and ZIP byte equality. Cumulative validation covers **627
worked-solution equations, 1,652 tutoring-route scenarios and seven multipart
classification scenarios**. [Collection validation](docs/assessment-card-collections-validation.json)
records current coverage. [New Module 8 validation](docs/assessment-cards-grade2-module8-lessons1-10-validation.json)
records the independently recomputed geometric, counting and equal-share
answers, 28 worked equations and 240 routes for the ten additions. Geometry
models check cube attributes, triangle composition and square/rhombus
classification; rational share models check fraction choices. Previous batches
are recorded in the [Module 7 validation](docs/assessment-cards-grade2-module7-lessons1-10-validation.json),
[Module 6 validation](docs/assessment-cards-grade2-module6-lessons11-20-validation.json)
and [Module 5 validation](docs/assessment-cards-grade2-module5-lessons9-20-validation.json).

All entries remain drafts with `ready_for_delivery: false`; human educational
review and script-agent integration tests remain outstanding. Module 8 uses
explicit numeric choice keys when answers name a shape or share. Correct codes
do not verify spoken vocabulary or explanations. Drawings, folds, joins and
matching actions are described and modelled; numeric responses do not verify
that the learner actually performed them. The source defines trapezoid
inclusively, with at least one pair of parallel sides; the square item asks for
the most specific name from its choices. Lesson 2 easy combines recognition
and missing-side counting; Lesson 4 easy uses index-card angle counting as a
prerequisite. Source high review flags naming reused items in Lessons 3 and 5
remain recorded as review blockers.

In Module 7, Lesson 5 counts coins rather than cents; Lessons 6–9 use source US
coin and dollar values. Totals and minimum counts do not verify an actual fair
trade or selected coin combination. Module 6 Lessons 18–20 reuse open questions
whose source rubrics permit partial credit for classification without its
reason. Generated parity questions use explicit numeric labels. Module 5
Lesson 11's source `exp_1` says its tens total is 10; including the new ten gives
11. The assessment uses correct arithmetic and preserves the concept file.
Source metadata and pictured worksheet uncertainties remain in linked concepts.
