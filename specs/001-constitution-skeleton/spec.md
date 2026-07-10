# Feature Specification: Constitution & Skeleton

**Feature Branch**: `001-constitution-skeleton`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 0 — "§3 layout, C-01..05, NFR-006/007/009, CI shell,
docker-compose, Makefile, ADR-001..020"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh-machine bootstrap (Priority: P1)

As a developer cloning the repo for the first time, I run `make bootstrap && make seed && make
dev` and get a working local system (API + web reachable in a browser) without any manual steps
beyond having Docker/Python/Node installed.

**Why this priority**: This is the reproducibility gate (NFR-007) that every later phase is
re-verified against; nothing else in the project matters if this doesn't work.

**Independent Test**: From a clean checkout, time the three-command sequence; API responds on its
health endpoint and the web app renders a placeholder page, in ≤15 minutes.

**Acceptance Scenarios**:

1. **Given** a clean clone with only Docker/Python 3.12/Node 20+/uv installed, **When** `make
   bootstrap` runs, **Then** all Python and Node dependencies install successfully with pinned,
   locked versions.
2. **Given** bootstrap has completed, **When** `make seed` runs, **Then** Postgres is migrated to
   the (currently empty) latest schema head without error.
3. **Given** seed has completed, **When** `make dev` runs, **Then** `GET /api/v1/health` returns
   200 and the Next.js app serves a page at `/` referencing the DealerIQ brand mark.

---

### User Story 2 - CI shell runs the same checks as local dev (Priority: P2)

As the sole reviewer of this project, I want a GitHub Actions workflow that runs the same lint/
typecheck/test commands `make ci` runs locally, so "CI green" means something concrete even
before a remote runs it.

**Why this priority**: NFR-009 requires CI as a documented artifact; later phases' QA gates (QA-
001..007) depend on this shell existing first.

**Independent Test**: `make ci` exits 0 locally; the workflow YAML invokes the identical Makefile
targets.

**Acceptance Scenarios**:

1. **Given** the skeleton is complete, **When** `make ci` runs, **Then** lint, typecheck, and the
   (currently trivial) test suites for `apps/api`, `apps/web`, and `packages/analytics` all pass.

---

### User Story 3 - Local secrets never leak (Priority: P2)

As the project owner, I want `.env.example` fully documenting every variable and gitleaks
scanning every commit, so no secret is ever accidentally committed from Phase 0 onward.

**Why this priority**: Constitution "Additional Constraints" and QA-007 require this from day
one, not retrofitted later.

**Independent Test**: `.env` is gitignored; gitleaks runs as a pre-commit hook and in CI; a
deliberately-inserted fake secret in a scratch file is caught before commit.

**Acceptance Scenarios**:

1. **Given** a file containing a fake AWS-style secret pattern, **When** `git commit` is
   attempted, **Then** the gitleaks pre-commit hook blocks the commit.

### Edge Cases

- What happens when Docker is not running when `make dev` is invoked? → Makefile target checks
  and prints a clear error rather than a raw connection-refused stack trace.
- What happens when a required env var is missing? → App fails fast at startup with a named
  missing-variable error, not a silent default.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-SKEL-001**: Repository MUST follow the exact monorepo layout in SRS §3.2
  (`apps/api`, `apps/web`, `packages/analytics`, `packages/api-client`, `infra/`, `docs/`,
  `.github/workflows/`, `Makefile`).
- **FR-SKEL-002**: `apps/api` MUST be a FastAPI app exposing `GET /api/v1/health` returning
  `{"status": "ok"}`, with OpenAPI schema generation enabled.
- **FR-SKEL-003**: `apps/web` MUST be a Next.js 15 (App Router, TypeScript) app rendering a
  placeholder home page using the Brand Kit tokens (imported `tokens.css`, Tailwind config).
- **FR-SKEL-004**: `packages/analytics` MUST be an installable Python package (empty domain logic
  at this phase, just packaging + a smoke-test).
- **FR-SKEL-005**: `packages/api-client` MUST exist with a codegen script wired to
  `apps/api`'s OpenAPI schema (openapi-typescript + openapi-fetch per ADR-012), even though there
  are no real endpoints to generate against yet beyond `/health`.
- **FR-SKEL-006**: `infra/docker-compose.yml` MUST define `postgres` (16) and `mailhog` services
  with named volumes and healthchecks.
- **FR-SKEL-007**: `Makefile` MUST define `bootstrap`, `seed`, `dev`, `ci`, `test`, `lint` targets
  per NFR-007.
- **FR-SKEL-008**: `.github/workflows/ci.yml` MUST invoke the same Makefile targets used locally
  (lint → typecheck → unit tests → build web → generate+compile API client).
- **FR-SKEL-009**: `.env.example` MUST exist documenting every environment variable used by
  `apps/api` and `apps/web` at this phase; `.env` MUST be gitignored.
- **FR-SKEL-010**: gitleaks MUST run as both a pre-commit hook and a CI step from this phase
  onward (QA-007).
- **FR-SKEL-011**: structured JSON request logging (request id, latency) MUST be present in the
  FastAPI app skeleton (NFR-006), even before there is a user id to log.

### Key Entities

None — this phase introduces no domain data model (that begins in Phase 1/2).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `time (make bootstrap && make seed && make dev)` completes in ≤15 minutes on a
  clean checkout (NFR-007).
- **SC-002**: `make ci` exits 0.
- **SC-003**: `curl localhost:8000/api/v1/health` returns `{"status":"ok"}` with a 200 and a
  structured JSON log line is emitted for the request.
- **SC-004**: `curl localhost:3000` (or a headless fetch) returns the placeholder home page HTML
  referencing the DealerIQ wordmark.

## Assumptions

- Docker Desktop/Engine + Compose v2, Python 3.12, Node 20+, uv are present (verified already in
  this environment).
- No real domain logic, auth, or database tables are expected at this phase — this is
  infrastructure only.
- "CI green" for this phase means `make ci` passes locally; there was no git remote yet,
  so the GitHub Actions workflow is authored but not remotely executed (documented explicitly in
  the phase report, not glossed over).
