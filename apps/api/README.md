# apps/api — DealerIQ API

FastAPI (Python 3.12) backend. Owns the database; the sole security boundary (RBAC is enforced
here only, never trusted from the frontend). See `docs/srs/DealerIQ-SRS.md` §5, §7, §8.

## Layout

```
src/dealeriq_api/
├── auth/       # JWT, refresh-token rotation, RBAC dependencies, password hashing (Phase 1)
├── domain/     # SQLAlchemy models (rbac, refresh_token, audit_log so far), audit helper
├── routes/     # REST endpoints, versioned /api/v1 (auth, users, roles, permissions, audit-log)
├── jobs/       # APScheduler job definitions (Phase 4+)
├── alerts/     # rule engine, notification dispatch (Phase 6+)
└── core/       # config, logging, db session, errors, rate limiter
alembic/        # migrations — schema changes ONLY via reviewed Alembic revisions (ADR-008)
tests/
├── unit/        # no DB — passwords, tokens, lockout-window arithmetic
├── integration/  # real ephemeral Postgres via testcontainers-python (ADR-013)
└── conftest.py
```

## Auth (Phase 1)

Deny-by-default: every route declares `Depends(require_permission("resource:action"))`. Access
tokens are short-lived JWTs (`Authorization: Bearer`); refresh tokens are opaque, httpOnly-cookie
values with rotation and reuse detection (ADR-019). Self-registration is disabled — the first
Admin account is seeded by the `0001_auth_rbac` migration from `BOOTSTRAP_ADMIN_EMAIL`/
`BOOTSTRAP_ADMIN_PASSWORD` (see `.env.example`) with `must_change_password=true`.

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
