# Backend

FastAPI, runs locally. Owns LLM orchestration and verification (Track A), data
infrastructure, scheduling, assessment, attention, consent and parent systems (Track C).

```bash
make db-up migrate    # Postgres 16 + pgvector on :5433, apply migrations
make dev-backend      # http://localhost:8000/docs
make test
```

Layout and rules: see `docs/ARCHITECTURE.md`. Each module under `app/modules/` has a
README naming its owner and iteration.
