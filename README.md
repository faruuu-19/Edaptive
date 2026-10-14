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

There are **75 standalone assessment JSONs for 75 concept IDs**. Every file
contains one full assessment object and is named
`<concept_id>.assessment_card.json`. There are **no active or archived module-wide
assessment bundles** in this checkout. All 75 existing assessments are preserved
without question, rubric, hint, follow-up or tutoring-rule changes.

222 duplicate, superseded or bundled assessment JSONs and seven obsolete ZIPs
were removed locally. The assessment content branch also removes its previous
61 assessment paths and uses 75 canonical concept-ID paths. Concept JSONs,
validation reports, runtime/model outputs and test fixtures are preserved.
Earlier assessment versions remain recoverable in Git history.

| Grade | Module | Assessed lessons | Assessment JSONs | Remaining work |
|---|---|---|---:|---|
| 1 | 1–6 | Lesson 1 in each module | 6 | — |
| 2 | 1 | 1–8 | 8 | — |
| 2 | 2 | — | 0 | Source not provided |
| 2 | 3 | 1 | 1 | Lessons 2–21 lack supplied concepts |
| 2 | 4 | — | 0 | Source not provided |
| 2 | 5 | 1–20 | 20 | — |
| 2 | 6 | 1–20 | 20 | — |
| 2 | 7 | 1–10 | 10 | Lessons 11–26 need assessments |
| 2 | 8 | 1–10 | 10 | Lessons 11–16 need assessments |

The 75 assessments refer to **57 concept source JSON files**. Grade 2 Modules
1, 3, 5 and 6 have separate supplied lesson concepts, totaling 49 pairs.
Module 7 and Module 8 concept sources still contain multiple `cards[]` entries.
Select the child with the required `concept_id` and pass it with the single
assessment whose `linked_concept.concept_id` and `concept_version` match.
The cleanup generates no new assessments and does not change concept sources.
Twelve Grade 3/4 source files still have no assessments in this manual dataset.

Use the [canonical concept-ID index](docs/assessment-card-collections-manifest.json)
for every assessment path, concept version and file hash. See the
[loading contract](docs/assessment-card-collections.md),
[full assessment contract](docs/assessment-cards-v0.2.md) and
[module conversion progress](docs/grade2-lesson-file-migration.json).
Updated lesson indexes are available for:

- [Grade 2 Module 1 lessons](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/lesson-wise/module_index.json).
- [Grade 2 Module 3 lessons](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/lesson-wise/module_index.json).
- [Grade 2 Module 5 lessons](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/lesson-wise/module_index.json).
- [Grade 2 Module 6 lessons](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%206/Module%206/Math%20G2-M6%20Lessons/lesson-wise/module_index.json).

Every retained assessment has three main questions, two follow-ups, four local
rubrics, 15 hints and five guidance records. Totals remain **225 main questions,
150 follow-ups, 300 local rubrics, 1,125 hints and 375 guidance records**.

[Cleanup validation](docs/assessment-cards-cleanup-validation.json) verifies all
75 unchanged assessment objects, unique concept IDs, scoped references,
concept/index hashes, full guidance, removal of obsolete files and ZIP contents.
It rechecks 713 worked equations and 1,830 reference-controller route scenarios;
these rechecks are recorded separately from historical evidence. Prior active
validation totals remain **713 worked equations, 1,820 routing scenarios and
seven multipart classification scenarios**. Earlier reports retain the
independent answer/accept-list verification history.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Open questions require semantic grading against their
source rubrics. Numeric answers do not verify drawings, folds, graph labels,
spoken vocabulary or coin choices. Module 6 Lessons 18–20 retain their semantic
rubrics; generated parity questions use explicitly labelled numeric codes.
Module 5 Lesson 11 source `exp_1` contains a tens-total discrepancy; its assessment
uses correct arithmetic. Source review flags remain preserved.
