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

There are **75 active assessment entries in 57 matching JSON pairs**.
**Grade 2 Module 6 Lessons 1–20 now each have a standalone concept JSON and
matching full assessment JSON.** All existing concept and assessment content,
including 700 concept questions and their rubrics, is preserved. This conversion
creates 20 separate lesson pairs and requires no new assessment entries.

Use the [Module 6 lesson index](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/module_index.json) to select the two inputs for a
one-lesson script. Each index records linked concept ID/version and both file
hashes. Repository paths are relative to the repository root; downloadable ZIP
paths are relative to the extracted folder. Original collection files are
retained byte-for-byte under each converted module's `legacy/module-wide/`
folder and excluded from active indexes, coverage and packages.

```text
Mathematics — 57 active JSON pairs / 75 assessment entries
├── Grade 1 — 6 pairs / 6 entries
│   └── Modules 1–6 → Lesson 1 in each → existing collections
└── Grade 2 — 51 pairs / 69 entries
    ├── Module 1 → Lessons 1–8 → 8 standalone pairs → converted
    ├── Module 2 → source not present
    ├── Module 3 → Lesson 1 → 1 standalone pair → available lesson converted
    │             Lessons 2–21 still need concept sources and assessments
    ├── Module 4 → source not present
    ├── Module 5 → Lessons 1–20 → 20 standalone pairs → converted
    ├── Module 6 → Lessons 1–20 → 20 standalone pairs → converted
    ├── Module 7 → Lessons 1–10 → 1 collection / 10 assessments
    │             Lessons 11–26 still need assessments
    └── Module 8 → Lessons 1–10 → 1 collection / 10 assessments
                  Lessons 11–16 still need assessments
```

There are **49 standalone lesson pairs and eight remaining collections**.
Modules 1, 5 and 6 are fully converted for all their included lessons. Module 3
is converted only for its one supplied concept; its index lists twenty missing
source lessons. Modules 7 and 8 retain partial collections with 16 and 6 pending
assessments. The [conversion progress index](docs/grade2-lesson-file-migration.json)
separates file conversion from assessment coverage. Grade 2 Modules 2 and 4
have no provided source files. Twelve active Grade 3/4 source files still have
no assessments.

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
| 2 | 3 | 1 | [math_g2_m3_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/lesson-wise/lesson-1/math_g2_m3_l1_lesson.json) | [math_g2_m3_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/lesson-wise/lesson-1/math_g2_m3_l1_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 1 | [math_g2_m5_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-1/math_g2_m5_l1_lesson.json) | [math_g2_m5_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-1/math_g2_m5_l1_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 2 | [math_g2_m5_l2_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-2/math_g2_m5_l2_lesson.json) | [math_g2_m5_l2_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-2/math_g2_m5_l2_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 3 | [math_g2_m5_l3_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-3/math_g2_m5_l3_lesson.json) | [math_g2_m5_l3_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-3/math_g2_m5_l3_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 4 | [math_g2_m5_l4_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-4/math_g2_m5_l4_lesson.json) | [math_g2_m5_l4_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-4/math_g2_m5_l4_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 5 | [math_g2_m5_l5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-5/math_g2_m5_l5_lesson.json) | [math_g2_m5_l5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-5/math_g2_m5_l5_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 6 | [math_g2_m5_l6_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-6/math_g2_m5_l6_lesson.json) | [math_g2_m5_l6_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-6/math_g2_m5_l6_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 7 | [math_g2_m5_l7_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-7/math_g2_m5_l7_lesson.json) | [math_g2_m5_l7_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-7/math_g2_m5_l7_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 8 | [math_g2_m5_l8_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-8/math_g2_m5_l8_lesson.json) | [math_g2_m5_l8_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-8/math_g2_m5_l8_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 9 | [math_g2_m5_l9_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-9/math_g2_m5_l9_lesson.json) | [math_g2_m5_l9_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-9/math_g2_m5_l9_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 10 | [math_g2_m5_l10_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-10/math_g2_m5_l10_lesson.json) | [math_g2_m5_l10_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-10/math_g2_m5_l10_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 11 | [math_g2_m5_l11_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-11/math_g2_m5_l11_lesson.json) | [math_g2_m5_l11_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-11/math_g2_m5_l11_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 12 | [math_g2_m5_l12_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-12/math_g2_m5_l12_lesson.json) | [math_g2_m5_l12_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-12/math_g2_m5_l12_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 13 | [math_g2_m5_l13_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-13/math_g2_m5_l13_lesson.json) | [math_g2_m5_l13_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-13/math_g2_m5_l13_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 14 | [math_g2_m5_l14_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-14/math_g2_m5_l14_lesson.json) | [math_g2_m5_l14_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-14/math_g2_m5_l14_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 15 | [math_g2_m5_l15_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-15/math_g2_m5_l15_lesson.json) | [math_g2_m5_l15_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-15/math_g2_m5_l15_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 16 | [math_g2_m5_l16_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-16/math_g2_m5_l16_lesson.json) | [math_g2_m5_l16_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-16/math_g2_m5_l16_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 17 | [math_g2_m5_l17_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-17/math_g2_m5_l17_lesson.json) | [math_g2_m5_l17_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-17/math_g2_m5_l17_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 18 | [math_g2_m5_l18_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-18/math_g2_m5_l18_lesson.json) | [math_g2_m5_l18_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-18/math_g2_m5_l18_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 19 | [math_g2_m5_l19_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-19/math_g2_m5_l19_lesson.json) | [math_g2_m5_l19_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-19/math_g2_m5_l19_lesson.assessment_card.json) | 1 / 1 |
| 2 | 5 | 20 | [math_g2_m5_l20_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-20/math_g2_m5_l20_lesson.json) | [math_g2_m5_l20_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/lesson-20/math_g2_m5_l20_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 1 | [math_g2_m6_l1_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-1/math_g2_m6_l1_lesson.json) | [math_g2_m6_l1_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-1/math_g2_m6_l1_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 2 | [math_g2_m6_l2_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-2/math_g2_m6_l2_lesson.json) | [math_g2_m6_l2_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-2/math_g2_m6_l2_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 3 | [math_g2_m6_l3_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-3/math_g2_m6_l3_lesson.json) | [math_g2_m6_l3_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-3/math_g2_m6_l3_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 4 | [math_g2_m6_l4_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-4/math_g2_m6_l4_lesson.json) | [math_g2_m6_l4_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-4/math_g2_m6_l4_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 5 | [math_g2_m6_l5_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-5/math_g2_m6_l5_lesson.json) | [math_g2_m6_l5_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-5/math_g2_m6_l5_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 6 | [math_g2_m6_l6_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-6/math_g2_m6_l6_lesson.json) | [math_g2_m6_l6_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-6/math_g2_m6_l6_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 7 | [math_g2_m6_l7_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-7/math_g2_m6_l7_lesson.json) | [math_g2_m6_l7_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-7/math_g2_m6_l7_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 8 | [math_g2_m6_l8_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-8/math_g2_m6_l8_lesson.json) | [math_g2_m6_l8_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-8/math_g2_m6_l8_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 9 | [math_g2_m6_l9_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-9/math_g2_m6_l9_lesson.json) | [math_g2_m6_l9_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-9/math_g2_m6_l9_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 10 | [math_g2_m6_l10_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-10/math_g2_m6_l10_lesson.json) | [math_g2_m6_l10_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-10/math_g2_m6_l10_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 11 | [math_g2_m6_l11_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-11/math_g2_m6_l11_lesson.json) | [math_g2_m6_l11_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-11/math_g2_m6_l11_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 12 | [math_g2_m6_l12_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-12/math_g2_m6_l12_lesson.json) | [math_g2_m6_l12_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-12/math_g2_m6_l12_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 13 | [math_g2_m6_l13_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-13/math_g2_m6_l13_lesson.json) | [math_g2_m6_l13_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-13/math_g2_m6_l13_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 14 | [math_g2_m6_l14_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-14/math_g2_m6_l14_lesson.json) | [math_g2_m6_l14_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-14/math_g2_m6_l14_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 15 | [math_g2_m6_l15_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-15/math_g2_m6_l15_lesson.json) | [math_g2_m6_l15_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-15/math_g2_m6_l15_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 16 | [math_g2_m6_l16_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-16/math_g2_m6_l16_lesson.json) | [math_g2_m6_l16_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-16/math_g2_m6_l16_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 17 | [math_g2_m6_l17_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-17/math_g2_m6_l17_lesson.json) | [math_g2_m6_l17_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-17/math_g2_m6_l17_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 18 | [math_g2_m6_l18_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-18/math_g2_m6_l18_lesson.json) | [math_g2_m6_l18_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-18/math_g2_m6_l18_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 19 | [math_g2_m6_l19_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-19/math_g2_m6_l19_lesson.json) | [math_g2_m6_l19_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-19/math_g2_m6_l19_lesson.assessment_card.json) | 1 / 1 |
| 2 | 6 | 20 | [math_g2_m6_l20_lesson.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-20/math_g2_m6_l20_lesson.json) | [math_g2_m6_l20_lesson.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/lesson-20/math_g2_m6_l20_lesson.assessment_card.json) | 1 / 1 |
| 2 | 7 | Collection | [math_g2_m7_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.json) | [math_g2_m7_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/math_g2_m7_Lessons.assessment_card.json) | 10 / 26 |
| 2 | 8 | Collection | [math_g2_m8_Lessons.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.json) | [math_g2_m8_Lessons.assessment_card.json](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/math_g2_m8_Lessons.assessment_card.json) | 10 / 16 |

Each standalone assessment is a complete v0.2 object with `card_type:
assessment_card`; pass it directly with its linked concept. Remaining
collections have `card_type: assessment_card_collection`; select a child by
concept ID. Always match `linked_concept.concept_id` and `concept_version`.
Local question/rubric/hint/asset IDs stay scoped to the selected pair. Source
hashes for standalone pairs are stored in the module index. See the
[pairing and loader contract](docs/assessment-card-collections.md) and
[lesson assessment contract](docs/assessment-cards-v0.2.md).

Every assessment retains three main questions, two follow-ups, four local
rubrics, 15 progressive hints and five guidance records with feedback, worked
answers, attempts, help, silence and fallback rules. Active totals remain
**225 main questions, 150 follow-ups, 300 local rubrics, 1,125 hints and 375
guidance records**. All 75 earlier active entries are preserved exactly.
Module 1's former mixed assessment remains retired and excluded from totals;
Module 3/5/6 collections are archived without retiring their unchanged lesson
assessments.

[Module 6 conversion validation](docs/assessment-cards-grade2-module6-lesson-wise-validation.json)
checks 20 pairs, original object equality, scoped references, full hints and
guidance, index hashes and portable package bytes. Numeric answers and parity
truths, accept variants, 150 worked equations and 506 reference-controller
routes were independently rechecked. Repeat checks are not added again to
cumulative totals. [Current pair validation](docs/assessment-card-collections-validation.json)
records all 57 pairs, archive preservation and ZIP byte equality. Active
cumulative evidence remains **713 worked equations, 1,820 routes and seven
multipart classification scenarios**.

[Module 3/5 conversion validation](docs/assessment-cards-grade2-modules3-5-lesson-wise-validation.json)
retains evidence for 21 unchanged pairs and 381 preserved concept questions.
[Module 1 extraction validation](docs/concept-cards-grade2-module1-lesson-wise-validation.json)
and [Module 1 assessment validation](docs/assessment-cards-grade2-module1-lesson-wise-validation.json)
retain evidence for its eight rebuilt assessments and 112 preserved concept
questions. Concept and assessment IDs/versions remain unchanged by conversion.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Module 6 Lessons 18–20 reuse open source questions:
grade equivalent explanations against their rubrics and apply partial credit
only for the stated criteria. Generated parity questions use explicitly
labelled numeric codes. Source `pair_of_parts` keys can contain `valid_pairs`,
whereas hard assessment keys use three named parts. Numeric answers/codes do
not verify actual drawings, folds, graph labels, spoken vocabulary or coin
choices. Module 5 Lesson 11 source `exp_1` says its tens total is 10; including
the new ten gives 11. The preserved assessment uses correct arithmetic. Other
source review flags and worksheet uncertainties remain unchanged.
