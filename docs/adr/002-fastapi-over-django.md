# ADR-002: FastAPI over Django

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, C-05

## Context

The predecessor system (NaserSalem Motors, 2022) was a Django + PostgreSQL system of record.
DealerIQ needs an OpenAPI-first, typed contract that can drive generated-client codegen (C-05),
and benefits from async I/O for the API layer while background jobs run analytics work.

## Decision

Use FastAPI (Python 3.12) with Pydantic v2 models as the API framework, rather than Django (with
or without Django REST Framework).

## Consequences

- OpenAPI 3.1 schema generation is native and drives the TypeScript client build (ADR-012),
  satisfying C-05 without a separate schema-authoring step.
- Pydantic-typed request/response contracts catch shape mismatches at development time.
- This deliberately complements rather than repeats the 2022 Django project - the two systems
  demonstrate different, appropriate tool choices for different problem shapes.
- Django's batteries (admin site, ORM migrations baked in) are not available for free; SQLAlchemy
  + Alembic (ADR-011) and a hand-built admin console (FR-082) substitute for them.
