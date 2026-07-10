# ADR-001: Single Monorepo

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.1, C-05

## Context

DealerIQ is composed of a FastAPI backend, a Next.js frontend, a Python analytics package, and a
generated TypeScript API client. These pieces share a contract (OpenAPI) and a delivery
timeline, and the project is built and reviewed by a single engineer/team for its v1.0 scope.

## Decision

Use one GitHub repository (`dealeriq/`) containing `apps/api`, `apps/web`, `packages/analytics`,
`packages/api-client`, `infra/`, and `docs/` (layout fixed in SRS §3.2).

## Consequences

- Atomic commits across the API contract, generated client, and frontend consumer are possible
  and expected (supports C-05: the frontend must consume the generated client, never drift from
  it silently).
- One CI pipeline, one review surface — appropriate for a single-team, single-cadence project.
- Vercel's native monorepo support (Root Directory = `apps/web`) keeps the Stage-2 deployment
  path (§12.4) simple later.
- Two repos would only be justified by independent teams or release cadences, neither of which
  applies here.
