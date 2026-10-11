# Edaptive: notes for coding agents

Edaptive is an offline, local-model homeschool tutor for Grades 1–5 (FAST NUCES FYP, team
of 3). The AI proposes and a deterministic tool verifies: the model never decides truth.
Read `README.md`, then `docs/CONTRIBUTING.md` and `docs/ARCHITECTURE.md` before changing code.

## Hard rules

- **Offline only.** No paid APIs, cloud services, CDNs or remote fonts at runtime.
- **Scope is frozen** to the accepted proposal. Don't add features nobody agreed.
- **Verification first.** No unverified LLM output reaches the UI. The LLM is called only
  from the Socratic Engine (Track A), 1–2 calls per turn, with schema-constrained output.
- **Children's data stays minimal** and consent-gated. Attention processing stays in the
  browser; no video is stored.

## How the code fits together

- Shared shapes live in `contracts/` (JSON Schema). Build against them, not other modules'
  internals. After changing a contract, run `make gen` and commit the output.
- Modules share data only through contracts and the append-only session log
  (`/api/events`), and the log rejects unregistered event types. Backend modules never
  import each other; frontend features import each other only via their `index.ts`.
  Tooling enforces both.
- Identity comes from `app/core/identity.py` (`CurrentActor`, `ParentActor`,
  `ensure_student_access`). Never read cookies, PINs or tokens in feature code.
- Each folder's owning track is in `.github/CODEOWNERS`. Only change your own track's
  folders; propose contract changes in a separate PR.

## UI: follow the Storybook theme

All UI uses the theme in **`docs/DESIGN.md`**: paper background, navy ink outlines, tomato
and mustard accents, flat offset shadows, Fraunces headings and Andika body text, inline SVG
icons and no emoji, light theme only. Use the tokens and classes in
`frontend/src/app/globals.css`; don't hard-code colours or add another look.
Subject colours: Maths = tomato, English = mustard, Science = teal.

## Before every PR

```bash
make check
```

It runs codegen, lint, module boundaries, backend tests against Postgres and the frontend
build. Fill in the PR template's checklist.
