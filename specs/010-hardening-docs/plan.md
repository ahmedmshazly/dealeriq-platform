# Implementation Plan: Hardening & Docs

**Branch**: `010-hardening-docs` | **Date**: 2026-07-11 | **Spec**: `specs/010-hardening-docs/spec.md`

## Summary

Six independent hardening tracks, all closing real, previously-surveyed gaps rather than
rebuilding what already works: a Playwright golden-path E2E suite (the phase's own named exit
criterion) exercising create-order → discount-triggers-pending-approval → the transactional
discount-approval alert (Phase 6, rule e) fires → Manager approves → alert visible → acknowledged;
a small `httpx`-based latency benchmark script reporting real p95 figures for representative CRUD
endpoints and the two Phase 8 dashboard endpoints; making the already-present-but-non-blocking
`pip-audit`/`npm audit` CI steps build-blocking with a documented waiver file; re-verifying (not
rebuilding) the already-implemented OpenAPI contract-diff and static-quality gates;
`eslint-plugin-jsx-a11y` wired into the existing eslint config with real violations fixed; and one
new operational runbook (`docs/runbooks/jobs-and-alerts.md`) plus the one missing package README
(`infra/README.md`).

## Technical Context

**Language/Version**: Python 3.12 (`apps/api`, `packages/analytics`, benchmark script), TypeScript
(`apps/web`, Playwright suite) - unchanged.

**Primary Dependencies**: `@playwright/test` (new devDependency, `apps/web`) - the standard,
free, open-source E2E runner named directly by QA-004's own requirement text; `eslint-plugin-jsx-
a11y` (new devDependency, `apps/web`) - the standard free ESLint accessibility plugin. No new
Python dependencies: the benchmark script uses `httpx` (already a dependency, already used by
`TestClient`); the dependency-audit waiver check is a small stdlib-only script (`json` + the
already-CI-invoked `pip-audit --format json` / `npm audit --json`), not a new scanning tool.

**Storage**: PostgreSQL 16, unchanged. No new tables - the vulnerability waiver list is a
committed file (`security/dependency-waivers.json`), not a database table, since it's reviewed
via PR like code, not managed at runtime.

**Testing**: Playwright (new) for the golden-path E2E suite, run against a real dev-stack
instance (real Postgres, real API, real Next.js - no mocks, per QA-004's own text). Existing
pytest/vitest suites are re-verified, not extended, except where the a11y lint fix requires a
component change that an existing test already covers.

**Target Platform**: unchanged - Docker Compose local dev, single-instance. The benchmark script
and Playwright suite both run against `make dev`'s standard local stack.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) - no new top-level project; one new top-level `scripts/` directory (the repo has none
today) for the benchmark tool and the dependency-waiver checker, matching where such
cross-cutting tooling conventionally lives.

**Performance Goals**: NFR-003's own targets are what's being measured, not a design goal for
this phase's own new tooling - the benchmark script itself just needs to run a few hundred
requests in well under a minute, which is not performance-sensitive.

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (Playwright/a11y-lint/benchmark are opt-in `make` targets, not part of the default
bootstrap/seed/dev path). The golden-path E2E test must use the same seeded credentials every
other phase's manual browser verification has used (`sales1@dealeriq.dev` /
`manager1@dealeriq.dev`, password `SeedUser123!`), and must create its own order rather than
depending on any specific pre-seeded order's state, so it's safe to re-run against a live dev
database without colliding with itself.

**Scale/Scope**: one new Playwright config + one E2E spec file; one new benchmark script; one new
waiver file + a CI/Makefile change to make two already-existing audit steps blocking; one new
eslint plugin + config change + real violation fixes across existing components; one new runbook;
one new README. No new API routes, no new database tables, no new business features.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: `@playwright/test` and `eslint-plugin-jsx-a11y`
  are additive devDependencies within the existing `apps/web` package - no new top-level package,
  no change to the mandated stack (FastAPI/Next.js/Postgres/APScheduler/statsforecast/
  scikit-learn/Recharts remain exactly as-is). New `scripts/` top-level directory is tooling, not
  a stack change.
- **Principle II (Free, Local-First, Zero Paid Services)**: both new devDependencies are free,
  open-source, and run entirely locally (Playwright drives a local Chromium install; the a11y
  linter is static analysis) - no paid service, no network call to a third party at test/lint
  time. The benchmark script hits only the local dev stack.
- **Principle III (Security & RBAC by Default)**: the E2E test itself is a direct exercise of
  this principle - it proves, end-to-end, that a discount above `order_approval_discount_
  threshold` really does require `orders:approve` (not just `orders:manage_own`) before an order
  can proceed, using real seeded Sales and Manager accounts, not a stubbed permission check.
- **Principle IV (Migrations & Append-Only Data Integrity)**: no schema changes this phase.
- **Principle V (Analytics Reproducibility & Scientific Integrity)**: not applicable - no
  analytics computation is added or changed this phase.
- **Principle VI (API Contract Discipline)**: User Story 4 re-verifies (via a deliberate,
  discarded throwaway change) that the existing contract-diff CI step still fails closed as
  QA-005 requires - no change to the mechanism itself.
- **Principle VII (Testing & Quality Bar, NON-NEGOTIABLE)**: this phase directly implements the
  constitution's own QA-004 clause ("the golden path... is covered by Playwright E2E") and
  extends the "must be green" quality bar to two previously-non-blocking checks (QA-007).
- **Principle VIII (Documentation & Traceability)**: the new runbook and `infra/README.md`
  directly satisfy this principle's own "job/alert runbooks... kept current" clause.
- **Principle IX (Reproducible Onboarding)**: re-verified as part of this phase's own exit demo,
  per every prior phase's precedent - no new bootstrap/seed step added.
- **Principle X (Observability & Reliability)**: not modified; the new runbook documents this
  principle's existing behavior (job retry-once-with-backoff, last-successful-run-stays-served)
  rather than changing it.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/010-hardening-docs/
├── spec.md
├── plan.md              # this file
└── tasks.md              # Phase 2 output
```

### Source code

```text
apps/web/
├── playwright.config.ts             # NEW: baseURL http://localhost:3000, webServer disabled
│                                     # (run against an already-running `make dev` stack, matching
│                                     # every prior phase's "verify against the real dev stack"
│                                     # convention rather than spinning up an ephemeral instance)
├── e2e/
│   └── golden-path.spec.ts          # NEW: login (sales) -> create order with a discount above
│                                     # threshold -> submit -> logout -> login (manager) ->
│                                     # approve -> open /alerts -> confirm the discount_approval
│                                     # alert for this order is visible -> acknowledge it
├── eslint.config.mjs                 # MODIFIED: + eslint-plugin-jsx-a11y's recommended config
└── app/**/*.tsx                      # MODIFIED where the new a11y lint rule finds a real,
                                       # fixable violation (scope determined by running the rule,
                                       # not predicted in advance)

scripts/                              # NEW top-level directory (none exists today)
├── benchmark_api.py                  # NEW: httpx-based p95 latency benchmark against a real
│                                     # running API - representative CRUD endpoints (list/get on
│                                     # orders, customers, leads, vehicle-units) plus
│                                     # GET /dashboards/manager and GET /dashboards/sales
└── check_dependency_audit.py         # NEW: runs pip-audit and npm audit (already invoked in CI),
                                       # filters findings against security/dependency-waivers.json,
                                       # exits non-zero on any real, unwaived finding

security/
└── dependency-waivers.json           # NEW: [{id, package, reason, reviewed_by, review_date,
                                       # re_review_by}] - committed, reviewed like code

.github/workflows/ci.yml               # MODIFIED: pip-audit/npm audit steps now pipe through
                                        # check_dependency_audit.py instead of `|| true`

Makefile                               # MODIFIED: + `make e2e` (Playwright), + `make benchmark`,
                                        # + `make audit` (the waiver-aware check) - none added to
                                        # the default `ci`/`dev` targets' critical path except
                                        # the now-blocking audit step, which `make ci` already runs

docs/runbooks/
└── jobs-and-alerts.md                 # NEW: the analytics job scheduler (which jobs, DS-OPS-001's
                                        # schedule, ENABLE_SCHEDULER, AnalyticsRun lifecycle,
                                        # diagnosing a stuck/failed run via POST /jobs/{name}/run
                                        # and the runs table) + the alert engine (rule config via
                                        # /admin/alert-rules, dedup-key semantics, notification
                                        # fan-out, verifying the digest via MailHog)

infra/
└── README.md                          # NEW: docker-compose.yml services (postgres, mailhog),
                                        # seed/generate.py + ground_truth/, scripts/
```

**Structure Decision**: extends the existing monorepo with one new top-level `scripts/`
directory (cross-cutting tooling that belongs to no single package) and one new top-level
`security/` directory (the waiver file, reviewed like code but not part of any package's own
source tree) - both additive, no existing directory reorganized.

## Golden-path E2E suite (QA-004)

Single spec file, one full run through the named path, driven through the real UI (form fills,
real clicks) against a real running dev stack - no API shortcuts, no mocked responses:

1. Log in as `sales1@dealeriq.dev` via the real login form.
2. On `/orders`, create a draft order against a real in-stock unit with a discount fraction
   deliberately above `order_approval_discount_threshold` (0.05) - the exact condition that
   routes the order to `pending_approval` and fires the transactional `discount_approval` alert
   (Phase 6, rule e) inside `submit_order`'s own transaction.
3. Submit the order via the order detail page's Submit action; confirm its status becomes
   `pending_approval`.
4. Log out; log in as `manager1@dealeriq.dev`.
5. Approve the order via its detail page's Approve action (requires `orders:approve` - proves the
   RBAC boundary is real, not just hidden).
6. Open `/alerts`; confirm a `discount_approval`-rule alert referencing this specific order is
   present (matched by the order id in the alert's payload, not just "an alert exists" - proving
   it's *the* alert this test caused, not a stale one from other seeded data).
7. Acknowledge it via the alerts page's own action; confirm its status updates.

Runs against an already-running `make dev` stack (not a Playwright-managed ephemeral server),
matching how every prior phase's own exit-demo verification has worked - `make e2e` documents
this prerequisite rather than trying to orchestrate it itself.

## Latency benchmark (NFR-003)

`scripts/benchmark_api.py`: authenticates once (real login), then issues N requests (configurable,
default enough for a stable p95 - e.g. 100) per endpoint to a small representative CRUD set
(`GET /orders`, `GET /customers`, `GET /leads`, `GET /vehicle-units`) plus
`GET /dashboards/manager` and `GET /dashboards/sales`, against the real seeded dev database.
Reports p95/p50/mean per endpoint. This is a measurement tool, not a load generator - sequential
requests are sufficient to characterize p95 latency at realistic single-user request rates,
matching NFR-003's own framing ("p95 API latency... on a laptop"), not a concurrent-load test
(which NFR-003 does not ask for).

## Dependency-audit gate (QA-007)

`security/dependency-waivers.json` - a flat list of `{id, package, reason, reviewed_by,
review_date, re_review_by}` entries, one per accepted finding. `scripts/check_dependency_audit.py`
runs `pip-audit --format json` and `npm audit --json`, cross-references each reported
vulnerability id against the waiver file, and exits non-zero listing every unwaived finding by id
and package - the CI step becomes `pip-audit ... ; npm audit ... ; python
scripts/check_dependency_audit.py` (real invocation order confirmed in tasks.md), replacing the
current `|| true` no-op. gitleaks' existing block-on-detection behavior is unchanged (already
correct per QA-007, re-verified not rebuilt).

## Accessibility (NFR-008)

`eslint-plugin-jsx-a11y`'s `recommended` config added to `apps/web/eslint.config.mjs`, run against
the full existing component tree. Every real finding is either fixed directly (the expected
common case - missing `alt`, a click handler on a non-interactive element, a form control missing
an accessible name) or, for a genuine false positive, suppressed with an inline
`// eslint-disable-next-line jsx-a11y/<rule> -- <reason>` comment, never a rule-level or
file-level blanket disable. Chart data-table fallback: satisfied by Phase 8's existing CSV export
(already wired to every dashboard/analytics chart) per spec.md's Assumptions - documented as a
deliberate interpretation of the constitution's own phrasing ("every chart has a CSV data-table
fallback," Additional Constraints), not re-litigated with new UI.

## Runbook & READMEs (NFR-009, scoped)

`docs/runbooks/jobs-and-alerts.md`: scheduler section (the five DS-OPS-001 cron jobs, their
schedule, `ENABLE_SCHEDULER`, how to trigger any job on demand via
`POST /jobs/{name}/run`, how to read an `AnalyticsRun` row to tell success/failure/still-running,
NFR-005's retry-once-with-backoff and last-successful-run-stays-served guarantees); alert-engine
section (the six built-in rules + the two customer-analytics rules, dedup-key semantics
preventing duplicate open alerts, role-based notification fan-out, `/admin/alert-rules` config,
verifying the daily digest via MailHog's own HTTP API - matching Phase 6's own exit-demo
verification method). `infra/README.md`: what's under `infra/` (docker-compose.yml's two
services, `seed/generate.py` + `ground_truth/`, any `scripts/`), pointing to
`docs/runbooks/local-dev.md` for the actual bootstrap/seed/dev walkthrough rather than
duplicating it.

## Validation sequence (proves the phase works end-to-end)

1. Run `make e2e` against a real `make dev` stack; confirm the golden-path suite passes
   end-to-end (SC-001). Deliberately break one step (e.g. temporarily require a permission the
   Manager account lacks) and confirm the suite fails at exactly that step, then revert (SC-002).
2. Run `make benchmark` against the real seeded dev database; record real p95 figures for every
   endpoint in scope, compare against the 300ms/2s targets, and document any miss with the real
   number (SC-003).
3. Deliberately introduce (on a throwaway, discarded change) a dependency with a known
   vulnerability and confirm CI fails; add a waiver entry for a real, currently-reported finding
   (if any exists in the current dependency tree) or a synthetic one, confirm CI passes with it
   waived and fails without it (SC-004).
4. Run the new eslint a11y rule across the full `apps/web` tree; fix every real violation; rerun
   to a clean pass (SC-005).
5. Hand the new runbook to a fresh read-through (self-review against the "could someone
   unfamiliar with the code answer these operational questions using only this doc" bar) covering
   both required scenarios (SC-006).
6. Full exit demo: `make e2e` green, plus a full `make bootstrap && make seed && make dev` cycle
   on a clean checkout completing within 15 minutes (SC-007, re-verifying NFR-007 per every prior
   phase's precedent).
