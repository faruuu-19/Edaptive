BACKEND_RUN ?= uv run
PYTHON ?= python3

# One entry point for every routine task. `make check` is the gate before every PR.
.PHONY: setup db-up db-down migrate gen dev-backend dev-frontend test lint check

setup:            ## install backend + frontend dependencies
	cd backend && uv sync
	cd frontend && npm ci

db-up:            ## start Postgres 16 + pgvector on :5433
	docker compose up -d --wait db

db-down:
	docker compose down

migrate:          ## apply DB migrations
	cd backend && $(BACKEND_RUN) alembic upgrade head

gen:              ## regenerate TypeScript types from /contracts
	./tools/gen_contracts.sh

dev-backend:      ## FastAPI on :8000 (docs at /docs)
	cd backend && $(BACKEND_RUN) uvicorn app.main:app --reload --port 8000

dev-frontend:     ## Next.js on :3000, /api proxied to :8000
	cd frontend && npm run dev

test:
	cd backend && $(BACKEND_RUN) pytest

lint:
	cd backend && $(BACKEND_RUN) ruff check . && $(BACKEND_RUN) ruff format --check . && $(BACKEND_RUN) lint-imports
	cd frontend && npm run lint && npm run typecheck

check: gen lint test runtime-check  ## run before every PR
	cd frontend && npm run build
	@if [ -n "$$(git status --porcelain -- frontend/src/contracts/generated)" ]; then \
		echo "Generated contract types are stale: run 'make gen' and commit."; exit 1; fi

.PHONY: runtime-check
runtime-check:
	$(PYTHON) tools/verify_runtime.py
	$(PYTHON) -m unittest discover -s tests
	$(PYTHON) -m unittest voice_service.test_jobs voice_service.test_service voice_service.test_demo_server voice_service.test_lecture
