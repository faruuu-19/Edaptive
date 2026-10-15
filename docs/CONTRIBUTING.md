# Working together

## Branches

- `main` is always demoable. Nobody pushes to it directly; everything lands by PR, after
  `make check` passes.
- Branch per piece of work, named by track: `track-a/…`, `track-b/…`, `track-c/…`,
  plus `contracts/…` for contract-only changes.
- Keep branches short (days, not weeks). Rebase or merge `main` in daily so you never
  integrate a month of drift at once.
- Each person can work in their own git worktree:
  `git worktree add ../edaptive-track-c track-c/curriculum-compiler`.

## Who touches what

Paths and owners are in `.github/CODEOWNERS`; add your own folders there when you create them. Rule of thumb: edit only your track's
folders. If you need something from another track, ask for a contract change; don't
reach into their code. Tooling enforces this:

- Backend: `import-linter` fails if one module imports another (`make lint`).
- Frontend: ESLint fails on deep imports into another feature; use its `index.ts`.
- Session log: rejects events that aren't registered in the contracts.

## Changing a contract

1. Open a `contracts/…` PR containing only the schema change, its example and `make gen` output.
2. All three tracks review. Merge it **before** the feature PRs that depend on it.
3. Breaking change? Version it (see `contracts/README.md`); don't edit v1 in place.

## Before opening a PR

```bash
make check
```

It checks generated types are up to date, lint, module boundaries, tests against Postgres,
and the frontend build. Paste the result in your PR.

## UI

Every screen follows the Storybook theme in `docs/DESIGN.md`. Use the shared tokens and
classes; don't add a second look.

## Ground rules from the project brief

- Offline only at runtime: no paid APIs, no cloud services, no fonts/CDNs fetched at build.
- No unverified LLM output reaches the UI. The LLM is called only from the Socratic Engine (Track A),
  1–2 calls per turn, with schema-constrained output.
- Lessons are JSON data. Authoring a lesson never requires engine code changes.
- Children's data: minimal fields, consent-gated, attention processing stays in the browser,
  no video stored.
- Scope is the accepted proposal. No new features without the team agreeing.
