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

**16 concept cards are covered by 16 assessment cards:** 6 for Grade 1 and 10
for Grade 2. Completed coverage follows this hierarchy:

```text
Mathematics
├── Grade 1 — 6 assessment cards
│   ├── Module 1 → Lesson 1
│   ├── Module 2 → Lesson 1
│   ├── Module 3 → Lesson 1
│   ├── Module 4 → Lesson 1
│   ├── Module 5 → Lesson 1
│   └── Module 6 → Lesson 1
└── Grade 2 — 10 assessment cards
    ├── Module 1 → Lessons 1–8 in one combined concept card → 1 assessment card
    ├── Module 3 → Lesson 1 → 1 assessment card
    └── Module 5 → Lessons 1–8 → 8 assessment cards, one per lesson
```

Grade 2 Module 1 is an explicit source exception: its JSON combines Lessons 1–8
under `math_g2_m1_make_ten_take_from_ten`. Its assessment preserves that concept
ID and combined objective. It is one assessment card. The source flags this
combined structure for human review.

| Grade | Curriculum module | Lesson(s) | Concept ID / assessment JSON | Levels present | Review status |
|---|---|---|---|---|---|
| 1 | 1 | 1 | [math_g1_m1_l1_embedded_numbers](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%201/Module%201/math_g1_m1_l1_embedded_numbers.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 1 | 2 | 1 | [math_g1_m2_l1_three_addends_make_ten](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%202/Module%202/Math%20G1-M2%20Lessons/math_g1_m2_l1_three_addends_make_ten.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 1 | 3 | 1 | [math_g1_m3_l1_compare_length_endpoints](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%203/Module%203/Math%20G1-M3%20Lessons/math_g1_m3_l1_compare_length_endpoints.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 1 | 4 | 1 | [math_g1_m4_l1_group_tens_ones](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%204/Module%204/Math%20G1-M4%20Lessons/math_g1_m4_l1_group_tens_ones.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 1 | 5 | 1 | [math_g1_m5_l1_shape_attributes](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%205/Module%205/Math%20G1-M5%20Lessons/math_g1_m5_l1_shape_attributes.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 1 | 6 | 1 | [math_g1_m6_l1_compare_difference_unknown](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade1/Grade%201%20Module%206/Module%206/Math%20G1-M6%20Lessons/math_g1_m6_l1_compare_difference_unknown.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 1 | 1–8 (combined source card) | [math_g2_m1_make_ten_take_from_ten](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%201/Module%201/Math%20G2-M1%20Lessons/math_g2_m1_make_ten_take_from_ten.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 3 | 1 | [math_g2_m3_l1_bundle_count_units](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%203/Module%203/Math%20G2-M3%20Lessons/math_g2_m3_l1_bundle_count_units.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 1 | [math_g2_m5_l1_ten_hundred_more_less](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l1_ten_hundred_more_less.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 2 | [math_g2_m5_l2_add_subtract_multiples_100](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l2_add_subtract_multiples_100.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 3 | [math_g2_m5_l3_add_hundreds_and_tens](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l3_add_hundreds_and_tens.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 4 | [math_g2_m5_l4_subtract_hundreds_and_tens](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l4_subtract_hundreds_and_tens.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 5 | [math_g2_m5_l5_make_next_hundred_to_add](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l5_make_next_hundred_to_add.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 6 | [math_g2_m5_l6_compensation_subtract_check](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l6_compensation_subtract_check.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 7 | [math_g2_m5_l7_share_critique_strategies](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l7_share_critique_strategies.assessment_card.json) | Easy, medium, hard | Draft; human review required |
| 2 | 5 | 8 | [math_g2_m5_l8_disks_to_addition_algorithm](ciriculam/Maths%20Concept%20Cards%20Curriculum/grade2/Grade%202%20Module%205/Module%205/Math%20G2-M5%20Lessons/math_g2_m5_l8_disks_to_addition_algorithm.assessment_card.json) | Easy, medium, hard | Draft; human review required |

Each assessment sits beside its linked concept card. It includes one reused easy
practice question, generated medium and hard questions, a follow-up for each
generated question, and four generated rubrics. Each hard question has three
parts and checks the final answer by a different route. Grade and number ranges
follow the linked concept card.

All 16 files use UTF-8 JSON with 2-space indentation and schema version
`0.1-draft`. Python validation confirmed parsing, exact template fields,
concept-card references, copied asset specifications, recomputed numeric answers,
and every rubric accept list. The open-text endpoint answer was checked against
the source's alignment rule. Generated situations and number combinations are
new; individual numbers taught in the lesson may recur.

All 16 remain drafts: `ready_for_delivery` is `false`, and the blocking issue
is `card review_status is draft; needs human review before use`. Source
uncertainties include Grade 1 Module 3 pagination, Grade 1 Module 6 source
version/license and worksheet labels, Grade 2 Module 1 combined lessons and
source metadata, and Grade 2 Module 3 worksheet labels.
