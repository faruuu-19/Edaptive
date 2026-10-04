# Architecture (base structure)

```
contracts/            JSON Schemas shared by everyone (single source of truth)
  └─ make gen ─▶ backend/app/contracts/generated   (Pydantic)
              └▶ frontend/src/contracts/generated  (TypeScript)

backend/  FastAPI, local only
  app/core/           config, DB, contract validation           (Track C)
  app/session_log/    append-only event store + /api/events     (Track C)
  app/modules/<name>/ one package per module, owner in README    (A or C)
  migrations/         Alembic, Postgres 16 + pgvector            (Track C)

frontend/ Next.js + TypeScript
  src/lib/api.ts          the one client for the backend
  src/features/<name>/    one folder per feature, public API in index.ts
  src/app/                routes that compose features
```

## How modules cooperate

Modules never call each other's internals. They share data two ways:

1. **Contracts:** shapes of lessons, curriculum nodes, widgets, tutor actions.
2. **The session log:** every student action, verifier verdict, tutor action and attention
   signal is appended as an event (`POST /api/events` or `app.session_log.append`).
   Dashboards, replay, mastery and evaluation are *projections*: they read the log in
   order (`after_seq` paging) and build their own views. Nothing updates or deletes
   events; Postgres triggers enforce this.

Appending is idempotent on `event_id`, so a client can safely retry.

## Adding a module's API

Create `app/modules/<name>/router.py` with `router = APIRouter()`. It is mounted at
`/api/<name>` automatically; nobody edits `main.py`.
