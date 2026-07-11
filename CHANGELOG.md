# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/), versioned per phase until v1.0.0 ships
(Conventional Commits drive the actual commit history — see `git log` for full detail;
NFR-009).

## [Unreleased]

### Phase 9 — Hardening & Docs

- `apps/web`: a Playwright golden-path E2E suite (QA-004) — login → create a high-discount order
  → submit → approve (as Manager, proving `orders:approve` is a real server-enforced boundary) →
  the resulting `discount_approval` alert appears → acknowledge — run against a real dev stack,
  nothing mocked. `eslint-plugin-jsx-a11y`'s recommended rules, now enforced (`--max-warnings 0`
  is also new — see below); found and fixed 5 real `label-has-associated-control` findings via
  the rule's own `controlComponents` option.
- `scripts/` (new top-level directory): `benchmark_api.py` — real p50/p95/mean latency for
  representative CRUD endpoints and the two Phase 8 dashboard endpoints against the real seeded
  database; `check_dependency_audit.py` — makes the previously-non-blocking `pip-audit`/
  `npm audit` CI steps real, cross-referencing every finding against a committed, reviewed waiver
  file (`security/dependency-waivers.json`).
- New `make e2e`, `make benchmark`, `make audit` targets; `audit` is now a prerequisite of
  `make ci`.
- A real performance bug found via the new benchmark, not code review: `GET /vehicle-units`
  measured p95=734ms (target 300ms) — `list_vehicle_units` loaded the entire ~15k-row units table
  into Python on every call regardless of filters, then filtered/sorted/paginated in Python.
  Pushed filtering, ordering, and pagination into SQL; p95 dropped to 29ms.
- A real QA-006 enforcement gap found via deliberate demonstration: eslint warnings (e.g.
  unused variables) never failed the build — `eslint .` had no `--max-warnings` flag. Zero
  pre-existing warnings across `apps/web`, so tightened immediately to `--max-warnings 0`.
- Six real npm dependency-audit findings, all reviewed and waived with individually-verified
  reasons: five are Vite/esbuild/Vitest dev-server-only attack surfaces this project never
  exercises (fix requires a vitest 2.x→4.x major bump); the sixth (postcss XSS) is vendored
  inside Next.js's own bundled `node_modules` — verified directly that an npm `overrides` entry
  cannot actually remove it and produces an invalid dependency tree for no real benefit, so
  waited on an upstream Next.js patch instead of a fake fix. `pip-audit`: 0 findings.
  `docs/runbooks/jobs-and-alerts.md` (new) and `infra/README.md` (new). Writing the runbook
  surfaced a real, previously-undisclosed gap: NFR-005's "retried once with backoff" is not
  implemented anywhere — documented the true current behavior and added the gap to
  `docs/backlog.md` rather than claiming behavior that doesn't exist.
- QA-005 (OpenAPI contract-diff) and QA-006 (static quality) were already fully implemented from
  prior phases; both re-verified still failing closed via deliberate, reverted demonstrations.
- 1 new Playwright E2E spec, no new pytest/vitest files (existing suites re-verified passing,
  after fixing a real Vitest/Playwright file-collection conflict this phase's own new E2E spec
  caused) — `make ci` clean end-to-end (245 pytest tests, 94% coverage; vitest 8/8; the new
  audit gate; `next build` 20 routes).

### Phase 8 — Dashboards & Reports

- `apps/api`: `achieved_accuracy.py` reads back Phase 4's own persisted forecasts and scores them
  against real actuals that have since arrived — the first genuine out-of-sample forecast-quality
  metric in the system, distinct from the training-time cross-validation `ForecastMetric` fields.
  Dedups multiple runs' overlapping forecasts for the same week by taking the *earliest* covering
  run (ADR-024) and reuses Phase 4's already-validated `mase()` unchanged. `sales_summary.py`
  aggregates real delivered-order revenue/margin/top-bottom-models from `OrderEvent`.
  `dashboard_service.py` composes both plus inventory health, open anomalies, and unacknowledged
  alerts into `GET /dashboards/manager` and `GET /dashboards/sales` (server-side scoped to the
  current user, never a request parameter). `monthly_report.py` composes the same building blocks
  for one completed calendar month; `GET /reports/monthly` rejects the current in-progress month.
- `apps/web`: the dashboard placeholder is replaced with real role-branched Manager/Sales
  dashboards (sales-vs-forecast interval chart, top/bottom models, inventory health, leads ranked
  by score, sales vs. target); a new achieved-accuracy diagnostic on the existing analytics detail
  page; a new monthly report view with a month picker; PNG/CSV chart export utilities
  (`lib/chart-export.ts`), used across both dashboards and the analytics detail page.
- A single admin-configurable default monthly sales target (`Settings.default_monthly_sales_target`),
  not per-salesperson quotas — a real quota-management system is unscoped expansion, recorded as a
  P2 backlog item (ADR-024).
- A real chart-export bug found via real-browser SC-004 verification, not caught by any automated
  test: `querySelector("svg")` matched the first `<svg>` in the chart container — one of Recharts'
  own 14x14 per-legend-item icon svgs, not the chart — silently exporting a near-blank thumbnail.
  Fixed by scoping to `.recharts-wrapper > svg`, the chart's actual root element.
- Exit demo (SRS §13: "Manager/Sales dashboards complete") verified end-to-end against the real
  seeded database and in a real browser: cross-salesperson lead/sales isolation confirmed
  programmatically (zero overlap between two real salespeople's open-lead sets); a hand-computed
  independent revenue/margin calculation for a completed month matched the API exactly to the
  cent; achieved accuracy honestly reports "not enough history yet" system-wide right now (the
  live system's sole forecast run's entire horizon is still in the future) rather than a
  fabricated number, with the underlying dedup/alignment logic proven against a hand-computed
  fixture instead.
- 4 new/extended backend integration test files, no new frontend test files (UI correctness
  verified live in a real browser instead) — all green; `make ci` clean end-to-end (245 pytest
  tests, up from 235 at Phase 7; vitest 8/8; `next build` 20 routes, up from 19 — `/reports`
  added; live API-client regeneration with zero diff).

### Phase 7 — Customer Analytics

- `packages/analytics`: RFM segmentation (population-relative R/F/M quintiles mapped to five
  named segments — Champions/At Risk/Loyal Customers/Hibernating/New, ADR-022) and a calibrated
  lead-conversion model (L2-regularized logistic regression, isotonic calibration via
  `CalibratedClassifierCV`, temporal train/validation split, top-3 per-lead explanations,
  ADR-023); a hand-implemented Population Stability Index for FR-074's drift monitoring.
- `apps/api`: `lead_scoring_job.py` orchestrates RFM → lead scoring → drift check each run,
  persisting `CustomerRfmProfile`/`LeadScore`; completes Phase 6's deferred `lead_idle`
  score-cutoff; activates DS-OPS-001's 04:00 daily cron slot. `GET /leads` now surfaces
  conversion probability, segment, and explanation; new `GET /customers/{id}` (RFM segment +
  purchase history, FR-033).
- `apps/web`: a new customer detail page (segment badge, R/F/M scores, purchase history) and an
  expandable per-lead explanation panel on the leads list.
- Four real bugs found and fixed while validating against the real seeded database, not just unit
  tests: (1) a Phase 3 data-generation gap — every seeded lead always resolved to won/lost,
  leaving none open for this phase to score — fixed by truncating the funnel walk to what could
  plausibly have happened by "today"; (2) genuine label leakage in the only available
  "interaction count" proxy (`count(LeadEvent)`, mechanically downstream of Phase 3's
  outcome-dependent funnel-walk branching) — fixed by bounding the count to a lead's first 21
  days, dropping an implausible ~0.97 validation ROC-AUC to a defensible ~0.89; (3) PSI drift
  monitoring initially covered features that are mechanically non-exchangeable between the
  training and scoring populations, guaranteeing false-positive drift alerts on every run — fixed
  by scoping to compositional features only; (4) PSI's quantile binning silently reported zero
  drift for any shift in a binary/one-hot column — fixed by binning low-cardinality features by
  exact value.
- QA-003(c) (lead-model recovers sign of ground-truth coefficients) is now CI-blocking, extending
  Phase 3's own simulator-level check to Phase 7's actual deployed pipeline: sign recovery on
  every checkable coefficient, discrimination/calibration graded relative to the achievable
  ceiling and the naive baseline on a clean synthetic population (not fixed literals).
- 26 new analytics tests plus a CI-blocking QA-003(c) scientific-validation test, and 10 new
  backend integration tests — all green; `make ci` clean end-to-end (235 pytest tests, vitest
  8/8, `next build` 20 routes).

### Phase 6 — Alerts & Notifications

- `apps/api`: an alert-rule engine in the domain layer (not `packages/analytics` — every rule
  here is a DB read against already-computed Phase 4/5 outputs compared to a threshold, not a
  DB-free statistical computation) implementing FR-061's six built-in rules — stock at/below
  reorder point, vehicle aging, sales anomaly (severity from DS-ANO's own score), forecast-implied
  stockout within lead time, discount-approval-required order submission, lead idle beyond a
  threshold (score-cutoff deferred to Phase 7, pending DS-CUST lead scoring). A shared
  `open_alert()` helper enforces FR-062's dedup-key/no-duplicate-open-alert invariant and fans out
  role-scoped `notifications`.
- Rule (e) (discount approval) fires **synchronously inside `order_service.submit_order`'s own
  transaction** — FR-060's transactional-trigger case — reusing the same threshold comparison
  that already decided the order needs approval, so the two can never drift apart.
- `alert_job.py` orchestrates rules (a)-(d)/(f) against the latest succeeded forecast/inventory
  runs, skipping (and recording, per DS-OPS-002) any rule whose upstream run doesn't exist yet.
  `digest_job.py` sends a daily HTML digest email per subscribed user via stdlib `smtplib` to
  MailHog — no new email-service dependency.
- `core/scheduler.py`: APScheduler's first real cron activation (forecast weekly, inventory/
  alerts/digest daily) — Phase 4/5 only ever registered a job *name*, deferring actual scheduling
  to this phase. Defaults **off** (`Settings.enable_scheduler=False`); only `make dev` opts in,
  since a scheduled job opens its own DB session directly and would otherwise hit the live dev
  database during test runs, bypassing the test suite's `get_db` override.
- `GET/POST /alerts`, `/alerts/{id}/acknowledge`, `/alerts/{id}/resolve` (audit-logged via the
  existing `write_audit_row`); `GET/PATCH /alert-rules` (FR-065, Manager/Admin only, versioned +
  audit-logged). New `alert_rules`/`alerts`/`notifications` tables, seeded with the six built-in
  rules and DS-OPS-001's stated defaults.
- `apps/web`: a notification center (`/alerts` — live sidebar badge count, status/severity
  filters, acknowledge→resolve lifecycle) and an FR-065 admin config page (`/admin/alert-rules`).
- Exit demo (SRS §13: "nightly jobs → alerts → digest in MailHog") verified end-to-end against
  the real seeded database with zero manual steps beyond the four job triggers: forecast →
  inventory → alerts (65 stock-reorder, 91 unit-aging, 558 sales-anomaly, 11 forecast-stockout,
  0 lead-idle — the last a genuine data characteristic, since Phase 3's lead funnel resolves every
  seeded lead to a terminal `won`/`lost` state) → digest (4 real emails, confirmed via MailHog's
  own HTTP API, not mocked).
- Three real cross-test-pollution bugs (same root cause as ADR-013's shared testcontainers
  Postgres) surfaced and fixed in the final full-suite `make ci` pass: unfiltered `Alert` lookups
  in `test_alert_rules.py` colliding with other test files' same-`rule_key` fixtures; Phase 4's
  `get_series_actuals` computing its calendar from the *global* orders table instead of the
  series-specific subset; and a Phase 4 test assuming a forecast leaderboard's first entry was
  always its own series. See the phase report's Deviations section for full detail.
- 20 new backend integration tests (rules, lifecycle, config, a real-SMTP digest test verified
  against MailHog's own API), 1 pre-existing frontend test updated for a new `QueryClientProvider`
  dependency — all green; `make ci` clean end-to-end (199 pytest tests, vitest 8/8, `next build`
  19 routes).

### Phase 5 — Inventory Intelligence & Anomalies

- `packages/analytics`: ABC (revenue-share) × XYZ (demand-CV) classification; reorder points
  derived from Phase 4's champion forecast quantiles (not a fixed multiplier); Kaplan-Meier
  survival analysis (`lifelines`, ADR-017) for 30-day sale probability with correct right-
  censoring of still-in-stock units; STL + robust z-score series anomaly detection with a
  hand-implemented generalized ESD confirmation test, validated directly against Rosner (1983)'s
  published 54-point worked example; transaction-level discount-outlier detection matching Phase
  3's own pricing-error injector's discount-fraction convention exactly.
- `apps/api`: `InventoryIntel`/`UnitRisk`/`Anomaly` schema, all reusing Phase 4's `AnalyticsRun`
  run-tracking table; `GET /inventory/abc-xyz` (heatmap), `GET /inventory/models/{id}`
  (drill-down), `GET /inventory/units`, `GET /anomalies` — an on-demand `job_name="inventory"`
  trigger following Phase 4's exact orchestration pattern.
- `apps/web`: an Inventory Intelligence workbench — a 9-cell ABC/XYZ heatmap linking into a
  per-model drill-down (reorder points per branch, on-lot units with aging/survival status), and
  a severity-sorted, scope-filterable anomaly list.
- A real gap in Phase 3's synthetic data found and fixed this phase: the generator never left any
  units "in stock" (every unit was born already sold), leaving DS-INV-003/004 nothing to compute
  over. Fixed by adding a current-lot-inventory realization step to `infra/seed/generate.py`
  (236 `IN_STOCK` units seeded, sized at ~3 weeks of supply per series, acquisition dates spread
  to include genuinely-aging units).
- QA-003(b) (anomaly detector recovers ≥80% of injected anomalies at ≤10% false-positive rate) is
  now CI-blocking, the same treatment QA-003(a) got in Phase 4: **100% recovery, 2.0% FPR**
  for series-level demand shocks (verified both in-memory via a dedicated pytest and directly
  against the real seeded database); **100% recovery, ~1.8% FPR** for transaction-level pricing
  errors (verified directly against the real database).
- Two real bugs found and fixed while validating against real ground truth, not just unit tests:
  the series-level detector initially monitored only (segment, branch) aggregates, diluting the
  (model, branch)-level shocks Phase 3 actually injects — fixed by monitoring both granularities;
  and a latent test-hygiene bug in Phase 4's own `test_forecast_job.py` (a test that silently
  "passed" by falling back to an earlier test's stale data, because it never checked its own
  trigger's response status) was found and fixed in the same pass.
- 30 new analytics tests plus a CI-blocking QA-003(b) scientific-validation test, and 6 new
  backend integration tests — all green; 95% coverage.

### Phase 4 — Forecasting Engine

- `packages/analytics/forecasting`: rolling-origin (expanding-window) cross-validation over an
  8-method statsforecast pool (Naive, SeasonalNaive, auto-tuned Simple Exponential Smoothing,
  AutoETS, AutoARIMA, CrostonClassic, CrostonSBA, TSB) with a fold count derived from each
  series' actual length rather than hardcoded; MASE/sMAPE/pinball-loss/80%-coverage metrics
  validated against hand-computed fixtures before ever being wired into the pipeline; per-series
  champion selection (lowest mean CV MASE, must beat Seasonal Naive or Seasonal Naive itself is
  champion) with a full-history refit for the persisted 12-week forecast + interval.
- `apps/api`: `AnalyticsRun`/`SeriesProfile`/`Forecast`/`ForecastMetric` schema; an on-demand
  `POST /jobs/forecast/run` (admin-only, 409 on concurrent trigger) plus `GET
  /jobs/forecast/runs`; `GET /forecasts` (leaderboard) and `GET /forecasts/{series_key}`
  (fan-chart detail + CV metrics).
- `apps/web`: an Analytics workbench — leaderboard filterable by SBC pattern class with a
  trigger button and live run-status polling, and a per-series fan chart (Recharts: actuals,
  champion forecast, 80% interval band) with a sortable CV metrics table.
- Full 81-series pipeline run against the real Phase 3 dataset (66 model-branch + 15
  segment-branch series): 855.9s; 0/81 champions worse than Seasonal Naive (SC-002); champion
  beats Seasonal Naive on 79.4% (27/34) of intermittent-class series, clearing QA-003(a)'s ≥60%
  bar — now a CI-blocking pytest, not just a manual check.
- Two real bugs found and fixed by actually running the pipeline: a hardcoded CV fold count
  that silently produced all-NaN folds for any series shorter than the original 156-week
  dataset (now derived per-run from actual series length); a pre-existing unfiltered-list
  assumption in Phase 2's order-flow integration tests that this phase's larger synthetic
  dataset finally broke (now filtered by `model_id`).
- 34 new analytics tests (metrics/series/CV/champion-selection fixtures plus the QA-003(a)
  scientific-validation gate, now CI-blocking per the constitution's Phase 4+ mandate) and 4 new
  backend integration tests; 140 backend+analytics tests total, 95% coverage. `make ci`'s
  wall-clock floor is now set by the QA-003(a) test alone (~10 min), a disclosed trade documented
  in the phase report.

### Phase 3 — Synthetic Data Generator

- `packages/analytics`: SBC demand-pattern classifier (ADI/CV², DS-FC-002 pulled forward); an
  NB-GLM weekly demand simulator (trend + Fourier seasonality + promotions + branch effect)
  spanning all four SBC classes; a lead-funnel logit simulator with a fully signed, sign-
  recoverable coefficient table; demand-shock injection with self-verified detectability
  (independent STL re-decomposition, not just an analytic prediction).
- `infra/seed/generate.py`: bulk-inserts the generated world into Postgres (3 branches, 22
  vehicle models, ~6.4k customers, 15.2k orders with full unit/ledger/order-event trails, 6k
  leads with legal state-machine event paths) and writes GEN-006's ground-truth JSON. Wired to
  `make seed`, runtime ~16.5s.
- `infra/seed/notebooks/profile.md`: a real dataset profile (SBC histogram, order volume by
  segment/branch/payment-type, lead conversion by channel/segment, customer repeat-purchase
  distribution, injected anomaly list) pulled from an actual seeded database.
- Total order volume (~15.2k) deliberately exceeds GEN-001's approximate "~4-8k" estimate — see
  ADR-021 for why reaching ≥10 series in every SBC class requires it, given the NB-GLM's
  zero-probability math under this dataset's fixed 156-week/3-branch/~25-model shape.
- 18 new analytics tests (SBC fixtures, generator determinism/coverage, lead sign-recovery,
  anomaly detectability), all green; 112 backend tests (up from 95), 95% coverage.

### Phase 2 — Core Domain

- `apps/api`: branches, vehicle models/units with an append-only stock-movement ledger
  (receipt/reservation/sale/adjustment, every status change ledgered in the same transaction);
  customers with a non-blocking duplicate-phone/email warning; leads with a state-machine-
  validated funnel (new→contacted→test_drive→negotiating→won/lost); the full order lifecycle
  (draft→submit→pending_approval/approved→delivered/cancelled) with a configurable discount-
  threshold auto-approval, atomic `SELECT...FOR UPDATE` unit reservation, and margin visible
  only to Manager+; the FR-012 owner-or-permission mechanism shared by leads and orders.
- `apps/web`: Inventory, Customers, Leads, and Orders (list + detail/timeline) pages, all
  consuming only the generated API client; sidebar nav extended accordingly.
- 95 backend tests (up from 37), 94% coverage; full order lifecycle (both the auto-approve and
  Manager-approval paths) verified end-to-end in a real browser, including the 403 a Sales user
  gets when attempting to approve their own pending order.

### Phase 1 — Auth & RBAC

- `apps/api`: email+password login issuing a JWT access token (15 min) and a rotating opaque
  refresh token (7 days, httpOnly/SameSite=Strict/Secure-in-prod cookie) with reuse detection
  that revokes the whole token family (ADR-019); Argon2id password hashing (ADR-009); account
  lockout after 5 failed logins within 15 minutes with admin unlock; forced password-change flag
  for admin-created accounts; deny-by-default `require_permission()` dependency on every route;
  4 roles / granular permission-string matrix seeded by migration (`0001_auth_rbac`) along with a
  bootstrap Admin account; append-only audit log with a filterable `GET /audit-log`.
- `apps/web`: login page (Brand Kit "Sign In" mockup translated to Tailwind/React), forced
  change-password flow, an in-memory-access-token auth context with transparent
  refresh-and-retry-once on 401 (ADR-014), an authenticated app shell with a role-driven sidebar,
  and admin pages for users/permissions/audit-log — all consuming only the generated API client.
- 37 backend tests (pytest, testcontainers-python Postgres per ADR-013) at 96% coverage; 8
  frontend tests (Vitest + RTL); full flow manually verified end-to-end in a real browser
  (login → forced password change → dashboard → RBAC-gated admin pages → logout).
- Added `GET /api/v1/auth/me` (not in the original plan) so the frontend can know who's logged
  in without decoding the JWT client-side.

### Phase 0 — Constitution & Skeleton

- Initialized the monorepo layout (SRS §3.2): `apps/api` (FastAPI), `apps/web` (Next.js 15),
  `packages/analytics`, `packages/api-client`, `infra/`, `docs/`.
- Ratified the project constitution (`docs/constitution.md` v1.0.0) and recorded
  ADR-001..020.
- Stood up a working hello-world vertical slice: `GET /api/v1/health`, structured JSON request
  logging (NFR-006), a Next.js home page consuming it and rendering the DealerIQ brand mark,
  Alembic wired to an empty migration chain, and a real end-to-end OpenAPI → TypeScript client
  codegen pipeline (C-05, ADR-012).
- Docker Compose (Postgres 16 + MailHog), a `Makefile` (`bootstrap`/`seed`/`dev`/`ci`/`test`/
  `lint`/`down`/`migrate`), gitleaks secret scanning (pre-commit + CI), and a GitHub Actions CI
  workflow shell.
