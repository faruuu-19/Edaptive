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

There are **75 active assessment entries in 19 matching JSON pairs**. Grade 2
Module 1 is now converted into **eight separate lesson concepts and eight
standalone assessments**. Its old combined concept and mixed assessment are
archived for provenance and excluded from active totals and ZIPs.

The conversion preserves all 112 original Module 1 questions and rubrics in
exactly one lesson each. Each lesson has its own objective and supporting
content. Eight full assessments were rebuilt using only the corresponding
lesson methods/ranges. Use the [Module 1 lesson index](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/module_index.json)
to select the two inputs for a single-lesson script.

```text
Mathematics — 19 active JSON pairs / 75 assessment entries
├── Grade 1 — 6 pairs / 6 entries
│   └── Modules 1–6 → Lesson 1 in each → existing collections
└── Grade 2 — 13 pairs / 69 entries
    ├── Module 1 → Lessons 1–8 → 8 standalone lesson pairs → conversion complete
    ├── Module 2 → source not present
    ├── Module 3 → Lesson 1 included → 1 collection / 1 assessment
    │             source expects 21 lessons; 20 source concepts pending
    ├── Module 4 → source not present
    ├── Module 5 → Lessons 1–20 → 1 collection / 20 assessments
    ├── Module 6 → Lessons 1–20 → 1 collection / 20 assessments
    ├── Module 7 → Lessons 1–10 → 1 collection / 10 assessments
    │             Lessons 11–26 still need assessments
    └── Module 8 → Lessons 1–10 → 1 collection / 10 assessments
                  Lessons 11–16 still need assessments
```

Module 1 is the first completed lesson-file conversion. Other Grade 2 modules
retain their existing collections while migration proceeds module by module.
The [conversion progress index](docs/grade2-lesson-file-migration.json) separates
file-conversion progress from assessment coverage. Grade 2 Modules 2 and 4
have no source files in the provided curriculum.

| Grade | Module | Lesson/file format | Concept JSON | Assessment JSON | Assessments / source concepts |
|---|---|---|---|---|---|
| 1 | 1 | Collection | [math_g1_m1_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%201/Module%201/math_g1_m1_l1_lesson.json) | [math_g1_m1_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%201/Module%201/math_g1_m1_l1_lesson.assessment_card.json) | 1 / 1 |
| 1 | 2 | Collection | [math_g1_m2_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%202/Module%202/Math%20G1-M2%20Lessons/math_g1_m2_l1_lesson.json) | [math_g1_m2_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%202/Module%202/Math%20G1-M2%20Lessons/math_g1_m2_l1_lesson.assessment_card.json) | 1 / 1 |
| 1 | 3 | Collection | [math_g1_m3_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%203/Module%203/Math%20G1-M3%20Lessons/math_g1_m3_l1_lesson.json) | [math_g1_m3_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%203/Module%203/Math%20G1-M3%20Lessons/math_g1_m3_l1_lesson.assessment_card.json) | 1 / 1 |
| 1 | 4 | Collection | [math_g1_m4_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%204/Module%204/Math%20G1-M4%20Lessons/math_g1_m4_l1_lesson.json) | [math_g1_m4_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%204/Module%204/Math%20G1-M4%20Lessons/math_g1_m4_l1_lesson.assessment_card.json) | 1 / 1 |
| 1 | 5 | Collection | [math_g1_m5_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%205/Module%205/Math%20G1-M5%20Lessons/math_g1_m5_l1_lesson.json) | [math_g1_m5_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%205/Module%205/Math%20G1-M5%20Lessons/math_g1_m5_l1_lesson.assessment_card.json) | 1 / 1 |
| 1 | 6 | Collection | [math_g1_m6_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%206/Module%206/Math%20G1-M6%20Lessons/math_g1_m6_l1_lesson.json) | [math_g1_m6_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%206/Module%206/Math%20G1-M6%20Lessons/math_g1_m6_l1_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 1 | [math_g2_m1_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-1/math_g2_m1_l1_lesson.json) | [math_g2_m1_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-1/math_g2_m1_l1_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 2 | [math_g2_m1_l2_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-2/math_g2_m1_l2_lesson.json) | [math_g2_m1_l2_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-2/math_g2_m1_l2_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 3 | [math_g2_m1_l3_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-3/math_g2_m1_l3_lesson.json) | [math_g2_m1_l3_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-3/math_g2_m1_l3_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 4 | [math_g2_m1_l4_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-4/math_g2_m1_l4_lesson.json) | [math_g2_m1_l4_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-4/math_g2_m1_l4_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 5 | [math_g2_m1_l5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-5/math_g2_m1_l5_lesson.json) | [math_g2_m1_l5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-5/math_g2_m1_l5_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 6 | [math_g2_m1_l6_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-6/math_g2_m1_l6_lesson.json) | [math_g2_m1_l6_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-6/math_g2_m1_l6_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 7 | [math_g2_m1_l7_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-7/math_g2_m1_l7_lesson.json) | [math_g2_m1_l7_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-7/math_g2_m1_l7_lesson.assessment_card.json) | 1 / 1 |
| 2 | 1 | 8 | [math_g2_m1_l8_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-8/math_g2_m1_l8_lesson.json) | [math_g2_m1_l8_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/lesson-8/math_g2_m1_l8_lesson.assessment_card.json) | 1 / 1 |
| 2 | 3 | Collection | [math_g2_m3_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/math_g2_m3_Lessons.json) | [math_g2_m3_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/math_g2_m3_Lessons.assessment_card.json) | 1 / 1 |
| 2 | 5 | Collection | [math_g2_m5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.json) | [math_g2_m5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_lesson.assessment_card.json) | 20 / 20 |
| 2 | 6 | Collection | [math_g2_m6_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.json) | [math_g2_m6_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/math_g2_m6_Lessons.assessment_card.json) | 20 / 20 |
| 2 | 7 | Collection | [math_g2_m7_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.json) | [math_g2_m7_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.assessment_card.json) | 10 / 26 |
| 2 | 8 | Collection | [math_g2_m8_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.json) | [math_g2_m8_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.assessment_card.json) | 10 / 16 |

Eight standalone pairs and nine collections have complete coverage of included
source concepts. Modules 7 and 8 are partial, with 16 and 6 missing assessment
IDs respectively. Twelve other active source files, in Grades 3 and 4, still
have no assessments. Complete coverage is separate from human review and
script delivery readiness.

Each assessment has three main questions, two follow-ups, four local rubrics,
15 hints and five guidance records. Active totals are **225 main questions,
150 follow-ups, 300 local rubrics, 1,125 hints and 375 guidance records**.
The 67 earlier active entries are preserved exactly, one superseded entry is
archived unchanged, and eight new lesson-specific entries replace it.

For a script agent, standalone assessments use `card_type: assessment_card` and
are passed directly with their matching concept. Collections use
`card_type: assessment_card_collection`; select the required child by concept
ID. Always match `linked_concept.concept_id` and `concept_version`, and resolve
local IDs inside that pair. Source hashes for standalone pairs are in the
module index. See the [pairing and loader contract](docs/assessment-card-collections.md)
and [lesson assessment contract](docs/assessment-cards-v0.2.md).

[Module 1 extraction validation](docs/concept-cards-grade2-module1-lesson-wise-validation.json)
checks the 112 preserved questions/rubrics, references and package hashes:
96 numeric answer keys/accept variants, one pair key and three text truth
checks were independently verified; 12 original open rubrics were preserved.
[Module 1 assessment validation](docs/assessment-cards-grade2-module1-lesson-wise-validation.json)
records 96 worked-equation checks and 192 tutoring routes for the eight rebuilt
assessments. [Current pair validation](docs/assessment-card-collections-validation.json)
records 75 active entries, ZIP equality and archive preservation. Active
cumulative evidence covers **713 worked equations, 1,820 route scenarios and
seven multipart classification scenarios**; checks for the retired assessment
are excluded from these totals. Earlier reports remain historical evidence.

All concepts and assessments remain drafts for human educational review;
script-agent integration has not been tested. Lesson extraction uses the
combined JSON, not newly read original lesson PDFs. Shared support hints retain
original source provenance, while generated assessment grounds remain in the
current lesson. Some fixed ten/teen facts recur in new stories. Open concept
questions need semantic grading; a source `pair_of_parts` key can use
`valid_pairs`, while hard assessment keys use three named parts.

Previously documented limits remain: numeric answers/codes do not verify
actual drawings, folds, constructions, graph labels, spoken vocabulary or coin
choices. The Module 8 trapezoid definition is inclusive and its square question
asks for the most specific listed name. Module 6 open parity questions use
source partial-credit criteria. Module 5 Lesson 11's source `exp_1` gives 10 for
its tens total; including the new ten gives 11. Its assessment uses correct
arithmetic. Source metadata and worksheet uncertainties remain in linked cards.
