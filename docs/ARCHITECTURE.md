# Architecture (base structure)

```
contracts/            JSON Schemas shared by everyone (single source of truth)
  └─ make gen ─▶ frontend/src/contracts/generated  (TypeScript)
     backend validates against the schemas directly (app/core/contracts.py)

backend/  FastAPI, local only
  app/core/           config, DB, contract validation, identity (Track C)
  app/session_log/    append-only event store + /api/events     (Track C)
  app/modules/<name>/ one package per module, owner in README    (created by the owning track)
  migrations/         Alembic, Postgres 16 + pgvector            (Track C)

frontend/ Next.js + TypeScript
  src/lib/api.ts          the one client for the backend
  src/features/<name>/    one folder per feature, public API in index.ts
  src/app/                routes that compose features
```

## How modules cooperate

Modules never call each other's internals. They share data two ways:

1. **Contracts:** shapes of events, identity, curriculum content, widgets and tutor actions,
   each added by a contract PR once its owners agree it.
2. **The session log:** every student action, verifier verdict, tutor action and attention
   signal is appended as an event (`POST /api/events` or `app.session_log.append`).
   Dashboards, replay, mastery and evaluation are *projections*: they read the log in
   order (`after_seq` paging) and build their own views. Nothing updates or deletes
   events; Postgres triggers enforce this.

Appending is idempotent on `event_id`, so a client can safely retry.

## Adding a module's API

Create `app/modules/<name>/router.py` with `router = APIRouter()`. It is mounted at
`/api/<name>` automatically; nobody edits `main.py`.

## Identity and access

Hierarchy: **household → parent → students**. Auth is owned by Track C
(`app/modules/auth`, `frontend/src/features/auth`); the shape it produces is
`contracts/auth/actor.schema.json`.

Every other module only declares what it needs, from `app/core/identity.py`:

| Need | Use |
|---|---|
| Any signed-in student or parent | `actor: CurrentActor` |
| Parent-only (dashboard, consent, schedule/privacy controls) | `actor: ParentActor` |
| A student may only touch their own data | `ensure_student_access(actor, student_id)` |

No module reads PINs, cookies or tokens. Until the auth module installs its resolver,
these dependencies return 401 (fail closed).

## Data model

Tables, the event catalog and the analytics layer are specified in `docs/DATA-MODEL.md`.
