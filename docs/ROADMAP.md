# Roadmap and build order

Four iterations; each ends with a working, demoable slice (FYP process rule).
Maths first: English and Science reuse the same pipeline with a different verifier.

## 0. Foundation (now)

The base structure: contracts, session log, identity seam, module layout, ownership, `make check`.
**Everyone branches from `main` after this merges.**

## Mid-1: fully verified maths slice

The contracts each track publishes **first**, in this order, so nobody builds on guesses:

| Order | Contract | Track | Unblocks |
|---|---|---|---|
| 1 | Content formats (concept card + assessment card, to agree), DB schema, Actor (auth) | C (with A, B) | A and B read content and know who is acting |
| 2 | Widget schema (`fraction_bar`, `number_line`, `base_ten`) | B | lesson authoring, player |
| 3 | Tutor action schema + `tutor.*` / `verifier.*` events | A | player renders tutor turns |

Then in parallel:

| Track A | Track B | Track C |
|---|---|---|
| Socratic Engine, SymPy verifier, verification-badge UI | Widget schema, avatar state machine, manipulative widgets, avatar v1 | Curriculum Compiler (maths), DB schema, auth + Home & Profile UI |

Demo: child picks a profile → opens a maths lesson from the DB → tutor turn verified by
SymPy → widget shown → all of it in the session log.

## Final-1 (FYP-1 evaluation, 7–11 Dec 2026)

| Track A | Track B | Track C |
|---|---|---|
| Misconception classifier, adaptive engine, remediation | Voice pipeline, lesson player, voice input | Scheduling engine, assessment backend, timetable UI, progress dashboard |

## Mid-2

| Track A | Track B | Track C |
|---|---|---|
| Grammar verifier, English runtime | Replay store, nudge engine, replay library, rewards | Attention pipeline (WASM), consent model, engagement indicator, parent dashboard v1 |

## Final-2

| Track A | Track B | Track C |
|---|---|---|
| Science verifier (RAG), hallucination audit, citation overlay | Lip-sync, widget metrics, avatar v2, simulation widgets | Schedule enforcement, schedule controls, privacy controls |

## Still to decide (team)

Local LLM model · auth mechanism (owner decided: Track C; proposed: profile picker + parent PIN) · admin role · hosting/deployment · Mid-1 date.
