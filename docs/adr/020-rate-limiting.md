# ADR-020: Rate limiting - slowapi, in-memory

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: API-003

## Context

API-003 requires rate limiting on auth endpoints (e.g., 10/min/IP). A Redis-backed limiter would
add an operational dependency this project doesn't otherwise need locally.

## Decision

Use `slowapi` (Starlette/FastAPI-native) with its in-memory store for v1.0.

## Consequences

- Free, small, no new infrastructure dependency - consistent with C-01 and with the project's
  existing "Stage 2 = config/infra swap only" philosophy used elsewhere (e.g., email provider,
  hosted Postgres).
- In-memory state means limits are per-process, not shared across horizontally-scaled API
  instances - not a concern for local, single-instance v1.0 operation. A Redis-backed store is
  the documented Stage-2 follow-up if the API is ever scaled horizontally.
