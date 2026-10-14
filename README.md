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

There are **91 standalone assessment JSONs for 91 concept IDs**. Each file is
named `<concept_id>.assessment_card.json` and contains one full assessment object.
**Grade 2 Module 7 Lessons 1–26 are complete**, each with a separate concept JSON
and matching assessment JSON. Sixteen missing assessments were added; the ten
existing Module 7 assessments and all 75 earlier assessments are unchanged.
All 26 Module 7 concepts, including 980 source questions, are preserved.
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
| 2 | 8 | 1–10 | 10 | Lessons 11–16 need assessments |

Grade 1 has six assessments; Grade 2 has 85. The 91 assessments refer to 82
active concept source JSON files. Grade 2 Modules 1, 3, 5, 6 and 7 have 75
standalone lesson pairs. Module 8's source still has `cards[]`: select its child
by concept ID and pass it with that concept's standalone assessment. Twelve
Grade 3/4 source files remain unassessed in this manual dataset.

Use the [Module 7 lesson index](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%207/Module%207/Math%20G2-M7%20Lessons/lesson-wise/module_index.json) for all 26 input pairs and their
hashes. Use the [canonical concept-ID index](docs/assessment-card-collections-manifest.json)
for the whole dataset, and see the [loading contract](docs/assessment-card-collections.md),
[full assessment contract](docs/assessment-cards-v0.2.md) and
[module conversion progress](docs/grade2-lesson-file-migration.json).
Repository index paths are relative to repository root; ZIP paths are relative
to their extracted directory. Module 7's original concept collection is retained
under `legacy/module-wide/` for provenance and excluded from active coverage.

Every assessment has three main questions, two follow-ups, four local rubrics,
15 hints and five guidance records with feedback, worked answers and bounded
retry/fallback rules. Totals are **273 main questions, 182 follow-ups, 364 local
rubrics, 1,365 hints and 455 guidance records**.

[New Module 7 assessment validation](docs/assessment-cards-grade2-module7-lessons11-26-validation.json)
checks all sixteen new cards, independently recomputed answers and accept
variants, three-part checks, references, full hints/guidance, 109 worked
equations and 390 reference-controller route scenarios.
[Complete Module 7 pair validation](docs/assessment-cards-grade2-module7-lesson-wise-validation.json)
checks all 26 pairs, preserved source objects, hashes and ZIP contents. It
rechecks 211 equations and 632 routes across the full module; those repeats are
not added again to cumulative evidence. [Current dataset validation](docs/assessment-card-collections-validation.json)
checks all 91 cards and preservation of the prior 75. Active cumulative evidence
is **822 worked equations, 2,210 routes and seven multipart classification scenarios**.

The earlier cleanup removed 222 old/duplicate assessment JSONs and seven obsolete
ZIPs locally. Only canonical per-concept assessment files are active; earlier
assessment versions are recoverable in Git history. Historical validation
reports and concept provenance are retained.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Module 7 Lessons 17, 18 and 24 reuse open questions:
accept equivalent explanations under their source rubrics and apply partial
credit only for the stated criteria. Lesson 18 measurements are approximate;
numeric codes label unit choices. Numeric answers do not verify physical
measuring, ruler construction, tape diagrams, graph labels or spoken reasoning.
Source review flags and worksheet uncertainties remain preserved, including
Module 5 Lesson 11's documented source arithmetic discrepancy.
