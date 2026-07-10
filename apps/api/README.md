# apps/api — DealerIQ API

FastAPI (Python 3.12) backend. Owns the database; the sole security boundary (RBAC is enforced
here only, never trusted from the frontend). See `docs/srs/DealerIQ-SRS.md` §5, §7, §8.

## Layout

```
src/dealeriq_api/
├── auth/       # JWT, RBAC, password hashing (Phase 1+)
├── domain/     # SQLAlchemy models, services (Phase 1+); Base declarative class lives here now
├── routes/     # REST endpoints, versioned /api/v1 (Phase 1+)
├── jobs/       # APScheduler job definitions (Phase 4+)
├── alerts/     # rule engine, notification dispatch (Phase 6+)
└── core/       # config, logging, db session, errors
alembic/        # migrations — schema changes ONLY via reviewed Alembic revisions (ADR-008)
tests/
```

## Running locally

From the repo root: `make dev` (starts this alongside the web app and infra), or standalone:

```bash
uv run uvicorn dealeriq_api.main:app --reload --port 8000
```

Interactive API docs: `http://localhost:8000/api/v1/docs`. OpenAPI schema:
`http://localhost:8000/api/v1/openapi.json` (this is what `packages/api-client` generates
against — see ADR-012).

## Tests

```bash
uv run pytest apps/api/tests --cov=dealeriq_api --cov-report=term-missing
```

## Migrations

```bash
cd apps/api && uv run --project .. alembic revision --autogenerate -m "describe the change"
# review the generated migration before committing — autogenerate drafts, it does not decide
# (ADR-011)
cd apps/api && uv run --project .. alembic upgrade head
```
