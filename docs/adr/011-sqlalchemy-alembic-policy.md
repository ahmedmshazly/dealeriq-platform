# ADR-011: SQLAlchemy 2.0 typed declarative + Alembic autogenerate-then-review

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: DAT-001, DAT-002

## Context

ADR-008 fixes "Alembic migrations, no auto-create" but not the ORM style or the exact autogenerate
workflow.

## Decision

Use SQLAlchemy 2.0's typed declarative mapping (`Mapped[...]`, `mapped_column(...)`) for all
domain models. Migrations are drafted with `alembic revision --autogenerate` and then manually
reviewed and edited before commit; `alembic check` (verifying no un-migrated model changes) runs
in CI.

## Consequences

- Typed declarative models give mypy-checkable ORM code (supports the constitution's strict-mypy
  quality bar on domain code).
- Autogenerate accelerates drafting migrations but is never trusted blindly — a human
  reviews every generated diff for destructive operations before it's
  committed, consistent with ADR-008's "no implicit schema change" principle.
- `alembic check` in CI catches the case where a model was changed but no migration was
  generated at all.
