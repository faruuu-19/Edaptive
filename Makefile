# One entry point for every routine task. `make check` runs exactly what CI runs.
.PHONY: setup db-up db-down migrate gen dev-backend dev-frontend test lint check

setup:            ## install backend + frontend dependencies
	cd backend && uv sync
	cd frontend && npm ci

db-up:            ## start Postgres 16 + pgvector on :5433
	docker compose up -d --wait db

db-down:
	docker compose down

migrate:          ## apply DB migrations
	cd backend && uv run alembic upgrade head

gen:              ## regenerate Python + TypeScript types from /contracts
	./tools/gen_contracts.sh

dev-backend:      ## FastAPI on :8000 (docs at /docs)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:     ## Next.js on :3000, /api proxied to :8000
	cd frontend && npm run dev

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
	cd frontend && npm run lint && npm run typecheck

check: gen lint test  ## everything CI checks
	cd frontend && npm run build
	git diff --exit-code -- backend/app/contracts/generated frontend/src/contracts/generated \
		|| (echo "Generated contract types are stale: run 'make gen' and commit." && exit 1)
