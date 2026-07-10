# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/), versioned per phase until v1.0.0 ships
(Conventional Commits drive the actual commit history — see `git log` for full detail;
NFR-009).

## [Unreleased]

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
