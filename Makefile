.PHONY: bootstrap seed dev down ci test lint migrate

COMPOSE = docker compose -f infra/docker-compose.yml

# Installs every toolchain dependency needed for local development (NFR-007).
# Must work on a clean clone with only Docker/Python 3.12/Node 20+/uv present.
bootstrap:
	@echo "==> Fetching pinned local tools (gitleaks)"
	@./infra/scripts/ensure-gitleaks.sh
	@echo "==> Installing Python dependencies (uv workspace: apps/api, packages/analytics)"
	@uv sync --all-packages --group dev
	@echo "==> Installing Node dependencies (npm workspaces: apps/web, packages/api-client)"
	@npm install
	@echo "==> Installing pre-commit and git hooks"
	@uv tool install pre-commit --quiet 2>/dev/null || true
	@uv tool run pre-commit install
	@if [ ! -f .env ]; then cp .env.example .env; echo "==> Created .env from .env.example"; fi
	@echo "==> Bootstrap complete."

# Brings up infra, migrates the schema to head, then runs the full synthetic data generator
# (GEN-001..006): ~15k orders, ~6k leads/customers, 156 weeks of demand history, injected
# anomalies — see specs/004-synthetic-data/ and docs/adr/021-synthetic-demand-volume-vs-sbc-coverage.md.
seed:
	@echo "==> Starting infra (postgres + mailhog)"
	@$(COMPOSE) up -d
	@echo "==> Waiting for postgres to be healthy"
	@until [ "$$($(COMPOSE) ps postgres --format '{{.Health}}')" = "healthy" ]; do sleep 1; done
	@echo "==> Running Alembic migrations"
	@cd apps/api && uv run --project .. alembic upgrade head
	@echo "==> Running synthetic data generator"
	@uv run python infra/seed/generate.py
	@echo "==> Seed complete."

# Runs infra + API (uvicorn --reload) + web (next dev) concurrently.
dev:
	@if ! docker info >/dev/null 2>&1; then \
		echo "ERROR: Docker does not appear to be running. Start Docker and retry."; exit 1; \
	fi
	@$(COMPOSE) up -d
	@echo "==> Starting API (uvicorn --reload, :8000) and web (next dev, :3000). Ctrl+C stops both."
	@trap 'kill 0' EXIT INT TERM; \
	uv run uvicorn dealeriq_api.main:app --reload --host 0.0.0.0 --port 8000 & \
	npm run dev:web & \
	wait

down:
	@$(COMPOSE) down

migrate:
	@cd apps/api && uv run --project .. alembic upgrade head

# Static quality gates (QA-006): ruff + mypy (strict on domain/analytics) + eslint + tsc --noEmit.
lint:
	@echo "==> ruff"
	@uv run ruff check apps/api/src apps/api/alembic packages/analytics/src apps/api/tests packages/analytics/tests infra/seed/generate.py
	@echo "==> ruff format --check"
	@uv run ruff format --check apps/api/src apps/api/alembic packages/analytics/src apps/api/tests packages/analytics/tests infra/seed/generate.py
	@echo "==> mypy (strict)"
	@uv run mypy apps/api/src packages/analytics/src infra/seed/generate.py
	@echo "==> eslint (apps/web)"
	@npm run lint:web
	@echo "==> tsc --noEmit (apps/web)"
	@npm run typecheck:web

# Test suites (QA-001, QA-004): pytest (api + analytics) + vitest (web).
test:
	@echo "==> pytest"
	@uv run pytest apps/api/tests packages/analytics/tests --cov=dealeriq_api --cov=dealeriq_analytics --cov-report=term-missing
	@echo "==> vitest"
	@npm run test:web

# The same checks CI runs (§12.2). Before a git remote existed, `make ci`
# passing locally was the evidence backing the "CI green" exit criterion.
# Starts the API standalone (no DB required to serve OpenAPI schema) just long enough to
# regenerate the API client against it, then tears it down — mirrors what the GitHub
# Actions workflow does with a service container.
ci: lint test
	@echo "==> next build"
	@npm run build:web
	@echo "==> generate + compile API client"
	@uv run uvicorn dealeriq_api.main:app --host 127.0.0.1 --port 8123 & \
	API_PID=$$!; \
	trap "kill $$API_PID 2>/dev/null" EXIT; \
	for i in $$(seq 1 20); do curl -sf http://127.0.0.1:8123/api/v1/health >/dev/null && break; sleep 0.5; done; \
	NEXT_PUBLIC_API_URL=http://127.0.0.1:8123 npm run generate --workspace packages/api-client; \
	npm run build --workspace packages/api-client
	@echo "==> CI checks passed."
