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

There are **97 standalone assessment JSONs for 97 concept IDs**. Each file is
named `<concept_id>.assessment_card.json` and contains one full assessment object.
**Grade 2 Module 8 Lessons 1–16 are complete**, each with a separate concept JSON
and matching assessment JSON. Six missing assessments (Lessons 11–16) were added;
the ten existing Module 8 assessments and all 91 earlier assessments are unchanged.
All 16 Module 8 concepts, including their source questions, are preserved.
No assessment bundles or duplicate draft JSONs were created.

| Grade | Module | Assessed lessons | Assessment JSONs | Remaining work |
|---|---|---|---:|---|
| 1 | 1–6 | Lesson 1 in each module | 6 | — |
| 2 | 1 | 1–8 | 8 | — |
| 2 | 2 | — | 0 | Source not provided |
| 2 | 3 | 1 | 1 | Lessons 2–21 lack supplied concepts |
| 2 | 4 | — | 0 | Source not provided |
| 2 | 5 | 1–20 | 20 | — |
| 2 | 6 | 1–20 | 20 | — |
| 2 | 7 | 1–26 | 26 | Complete |
| 2 | 8 | 1–16 | 16 | Complete |

Grade 1 has six assessments; Grade 2 has 91. The 97 assessments refer to 97
active concept source JSON files, one per assessed concept. Grade 2 Modules 1, 3,
5, 6, 7 and 8 have 91 standalone lesson pairs. Twelve Grade 3/4 source files
remain unassessed in this manual dataset.

Use the [Module 8 lesson index](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%208/Module%208/Math%20G2-M8%20Lessons/lesson-wise/module_index.json) or the
[Module 7 lesson index](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/lesson-wise/module_index.json) for the standalone input pairs and
hashes. Use the [canonical concept-ID index](docs/assessment-card-collections-manifest.json)
for the whole dataset, and see the [loading contract](docs/assessment-card-collections.md),
[full assessment contract](docs/assessment-cards-v0.2.md) and
[module conversion progress](docs/grade2-lesson-file-migration.json).
Repository index paths are relative to repository root; ZIP paths are relative
to their extracted directory. The original Module 7 and Module 8 concept
collections are retained under `legacy/module-wide/` for provenance and excluded
from active coverage.

Every assessment has three main questions, two follow-ups, four local rubrics,
15 hints and five guidance records with feedback, worked answers and bounded
retry/fallback rules. Totals are **291 main questions, 194 follow-ups, 388 local
rubrics, 1,455 hints and 485 guidance records**.

[New Module 8 assessment validation](docs/assessment-cards-grade2-module8-lessons11-16-validation.json)
checks all six new cards, independently recomputed answers and accept variants
(area, clock-hand and elapsed-time arithmetic from the saved prompts), three-part
different-route checks, references, full hints/guidance, 35 worked equations and
144 reference-controller route scenarios.
[Complete Module 8 pair validation](docs/assessment-cards-grade2-module8-lesson-wise-validation.json)
checks all 16 pairs, preserved source objects, hashes and ZIP contents. It
rechecks 63 equations and 384 routes across the full module; those repeats are
not added again to cumulative evidence. Earlier validations:
[Module 7 new assessments](docs/assessment-cards-grade2-module7-lessons11-26-validation.json) and
[Module 7 pairs](docs/assessment-cards-grade2-module7-lesson-wise-validation.json).
[Current dataset validation](docs/assessment-card-collections-validation.json)
checks all 97 cards and preservation of the prior 91. Active cumulative evidence
is **857 worked equations, 2,354 routes and seven multipart classification scenarios**.

The earlier cleanup removed 222 old/duplicate assessment JSONs and seven obsolete
ZIPs locally. Only canonical per-concept assessment files are active; earlier
assessment versions are recoverable in Git history. Historical validation
reports and concept provenance are retained.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Module 7 Lessons 17, 18 and 24 reuse open questions:
accept equivalent explanations under their source rubrics and apply partial
credit only for the stated criteria. Lesson 18 measurements are approximate;
numeric codes label unit choices. Module 8 Lessons 11 and 12 reuse easy questions
whose exact answers are words ("another fourth", "yes"); Lesson 13's hard answers are
clock-number labels and Lesson 15 uses explicit 1 = a.m. / 2 = p.m. codes. Numeric
answers do not verify physical measuring, ruler construction, tape diagrams, graph
labels, folds, partitions, drawings, clock-hand positions or spoken reasoning.
Source review flags and worksheet uncertainties remain preserved, including
Module 5 Lesson 11's documented source arithmetic discrepancy.
