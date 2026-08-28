# ADR-008: Alembic migrations only, no auto-create

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, DAT-001

## Context

Schema evolution needs to be a reviewable, auditable artifact rather than an implicit side
effect of starting the application (as SQLAlchemy's `Base.metadata.create_all` would produce).

## Decision

All schema changes are authored as Alembic migrations, reviewed in PRs; the application never
auto-creates or auto-alters tables at runtime, in any environment including local dev.

## Consequences

- Every schema change has a diffable, reviewable artifact and a rollback path.
- `alembic upgrade head` is a required, explicit step in `make bootstrap`/`make seed` - schema
  state is never implicit.
- Autogenerate (`alembic revision --autogenerate`) is used to draft migrations quickly but every
  generated migration is manually reviewed before being committed (see ADR-011) - autogenerate
  drafts, it does not decide.
