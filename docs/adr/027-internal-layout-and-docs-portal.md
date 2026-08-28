# ADR-027: Internal layout refinement and Diataxis docs portal

- Status: Accepted
- Date: 2026-07-17
- Requirement refs: SRS §3.2, C-05, Principle I
- Supplements: ADR-001

## Context

ADR-001 fixed the top-level monorepo (`apps/`, `packages/`, `infra/`, `docs/`, `specs/`).
After v1.0 delivery, several hygiene and discoverability issues remained:

- `domain/` in the API held services, job pipelines, alert rules, and report builders in one
  flat package - hard to navigate at enterprise scale.
- Web feature UI lived entirely inside fat App Router `page.tsx` files.
- Host scripts, reviews, and seed logins sat at the repo root without a clear home.
- Documentation was strong (SRS, ADRs, runbooks) but lacked a Diataxis portal,
  architecture diagrams, unified configuration reference, and contribution/security entry points.

Top-level package boundaries must stay stable (Principle I / ADR-001). Internal organization
and documentation can deepen without changing the OpenAPI contract or public package names.

## Decision

1. **Top-level layout unchanged:** `apps/api`, `apps/web`, `packages/analytics`,
   `packages/api-client`, `infra/`, `docs/`, `specs/` remain the mandated monorepo roots.
2. **Brand assets:** tokens and logos are consumed from their copies in `apps/web/`.
3. **API internal layout** under `dealeriq_api/domain/`:
   - `models/` - SQLAlchemy ORM (unchanged)
   - `services/` - transactional use cases + audit + lead state machine
   - `alerts/` - alert rule evaluation engine
   - `reports/` - monthly report, sales summary, achieved accuracy
   - `jobs/` - analytics job pipelines + job lifecycle
   - Top-level `dealeriq_api/jobs/` remains thin registry re-exports for scheduler/HTTP names.
4. **Web internal layout:** feature UI under `apps/web/features/<name>/`; App Router pages stay
   thin route shells.
5. **Ops paths:** API image Dockerfile lives at `infra/Dockerfile`; host tools under
   `scripts/ops/` and `scripts/ci/`.
6. **Docs portal:** Diataxis structure under `docs/` (`getting-started/`, `how-to/`,
   `reference/`, `explanation/`) with `docs/README.md` as the index. `specs/` stays
   a planning archive, separate from durable product docs.
7. **No repository layer** in this change - services continue to use SQLAlchemy `Session`
   directly (documented as intentional).

## Consequences

- Import paths under `dealeriq_api.domain.*` change; public HTTP paths and OpenAPI operation
  IDs do not.
- Makefile, CI, compose, and runbooks must reference the new script/Dockerfile locations.
- Constitution Principle I and SRS §3.2 are updated to describe the refined internal layout
  and docs portal without relaxing stack discipline.
