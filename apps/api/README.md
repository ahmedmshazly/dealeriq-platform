# apps/api - DealerIQ API

FastAPI (Python 3.12) backend. Owns the database; the sole security boundary (RBAC is enforced
here only, never trusted from the frontend). See `docs/srs/DealerIQ-SRS.md` §5, §7, §8 and
`docs/explanation/architecture.md`.

## Layout (ADR-027)

```
src/dealeriq_api/
├── auth/                 # JWT, refresh-token rotation, RBAC deps, password hashing
├── domain/
│   ├── models/           # SQLAlchemy ORM entities
│   ├── services/         # transactional use cases, audit helper, lead state machine
│   ├── alerts/           # alert rule evaluation engine
│   ├── reports/          # monthly report, sales summary, achieved accuracy
│   ├── jobs/             # forecast / inventory / scoring / alert / digest pipelines
│   └── base.py           # ORM declarative base
├── routes/               # REST endpoints, versioned /api/v1
├── schemas/              # Pydantic request/response DTOs (non-auth)
├── jobs/                 # thin registry re-exports (job name SSOT for scheduler + HTTP)
└── core/                 # config, logging, db session, errors, rate limiter, scheduler
alembic/                  # migrations - schema changes ONLY via reviewed Alembic revisions
tests/
├── unit/                 # no DB
├── integration/          # real ephemeral Postgres via testcontainers (ADR-013)
└── conftest.py
```

There is **no repository layer** - services and jobs use SQLAlchemy `Session` directly
(intentional; see ADR-027).

## Auth

Deny-by-default: every route declares `Depends(require_permission("resource:action"))`. Access
tokens are short-lived JWTs (`Authorization: Bearer`); refresh tokens are opaque, httpOnly-cookie
values with rotation and reuse detection (ADR-019). Self-registration is disabled - the first
Admin account is seeded by the auth RBAC migration from `BOOTSTRAP_ADMIN_EMAIL`/
`BOOTSTRAP_ADMIN_PASSWORD` (see `.env.example`) with `must_change_password=true`.

## Running locally

From the repo root: `make dev` (starts this alongside the web app and infra), or standalone:

```bash
uv run uvicorn dealeriq_api.main:app --reload --port 8000
```

Interactive API docs: `http://localhost:8000/api/v1/docs`. OpenAPI schema:
`http://localhost:8000/api/v1/openapi.json` (this is what `packages/api-client` generates
against - see ADR-012).

## Tests

```bash
uv run pytest apps/api/tests --cov=dealeriq_api --cov-report=term-missing
```

## Migrations

```bash
cd apps/api && uv run --project .. alembic revision --autogenerate -m "describe the change"
# review the generated migration before committing - autogenerate drafts, it does not decide
# (ADR-011)
cd apps/api && uv run --project .. alembic upgrade head
```
