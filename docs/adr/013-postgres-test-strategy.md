# ADR-013: Postgres test strategy — testcontainers for CI/integration, Compose for dev

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: QA-001, §12.1, §12.2

## Context

QA-001 requires integration tests against a real Postgres instance. The SRS mentions
"testcontainers (or docker-compose test db)" as alternatives without picking one.

## Decision

Use `testcontainers-python` to spin up an ephemeral, hermetic Postgres per test session for CI
and local `pytest` runs. The docker-compose Postgres instance (`infra/docker-compose.yml`)
remains a separate, long-lived instance used only for `make dev` and manual seeding/browsing.

## Consequences

- Test runs are hermetic and parallel-safe (each test session gets its own container), avoiding
  state leakage between test runs and between test runs and the dev database.
- Developers can run `pytest` without first remembering to `docker compose up` — testcontainers
  manages its own container lifecycle.
- Two Postgres-launching mechanisms exist for two different purposes; this is intentional, not a
  duplication to clean up.
