# Implementation Plan: Inventory Intelligence & Anomalies

**Branch**: `006-inventory-anomalies` | **Date**: 2026-07-10 | **Spec**: `specs/006-inventory-anomalies/spec.md`

## Summary

Two pure-computation modules in `packages/analytics` (no DB dependency, independently testable):
an inventory-intelligence module (ABC/XYZ classification + reorder points derived from Phase 4's
champion forecasts + unit aging/survival analysis) and an anomaly-detection module (STL+robust-
z-score series monitoring, generalized ESD confirmation, transaction-level discount-outlier
checks) - plus a thin `apps/api` orchestration layer reusing Phase 4's `AnalyticsRun`
run-tracking contract, and an inventory-intelligence workbench (ABC/XYZ heatmap + anomaly list)
consuming only the generated API client. QA-003(b) - the anomaly detector recovering ≥80% of
Phase 3's injected ground truth at ≤10% false positives - becomes a CI-blocking pytest this
phase, the same treatment QA-003(a) got in Phase 4.

## Technical Context

**Language/Version**: Python 3.12 (`packages/analytics`, `apps/api`), TypeScript/Next.js 15
(`apps/web`) - unchanged from prior phases.

**Primary Dependencies**: `statsmodels` (already present, ADR-018 scoped it to STL - this phase
is exactly that scope's consumer) for STL decomposition and the generalized ESD test (via
`scipy.stats`, already a transitive dependency); `lifelines` (new dependency) for the
Kaplan-Meier survival curve (DS-INV-004) - the standard, actively-maintained, free/OSS Python
survival-analysis library; no other new dependencies. `apps/api` gains none.

**Storage**: PostgreSQL 16, three new tables (`inventory_intel`, `unit_risk`, `anomalies`) per
one new Alembic migration, per the SRS §7 schema (verbatim column names) - all keyed by
`run_id` back to Phase 4's `analytics_runs`, reusing that run-tracking table rather than
inventing a parallel one (FR-070 already covers "every analytics execution," not just
forecasting).

**Testing**: pytest (ABC/XYZ cutoffs, reorder-point arithmetic, and the z-score/ESD detector
logic against hand-computed fixtures, BEFORE wiring into the pipeline, per the project's
standing working rule), testcontainers-python for the run/API integration tests (ADR-013, same
pattern as Phases 1-2, 4).

**Target Platform**: unchanged - Docker Compose local dev, single-instance.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) - no new top-level project.

**Performance Goals**: the anomaly detector's STL decomposition runs once per monitored series
(same 81-series scale as Phase 4, plus per-model discount-outlier checks over the full order
ledger) - target well under a minute, since STL per series is O(n) and there's no CV-style
refitting loop like Phase 4's forecasting pipeline had.

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (this job is triggered on demand, like Phase 4's); QA-003(b) becomes CI-blocking
starting this phase, alongside QA-003(a) from Phase 4 - both now run in `make ci`'s pytest phase.

**Scale/Scope**: ABC/XYZ + reorder points over the same 66 (model, branch) pairs Phase 4 forecasts;
unit aging/risk over the full seeded `vehicle_units` table (~thousands of units); anomaly
detection over the same 81 series Phase 4 monitors (66 model-branch + 15 segment-branch) plus
per-model transaction-level discount checks over ~15k orders.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: inventory/anomaly logic in `packages/analytics`,
  orchestration/routes in `apps/api`, UI in `apps/web` consuming only the generated client - no
  new top-level package. `lifelines` is the one new dependency, free/OSS, justified below.
- **Principle II (Free, Local-First, Zero Paid Services)**: `lifelines` is BSD-licensed, pip-
  installable, no network calls - consistent with the project's existing free-OSS-only stack.
- **Principle IV (Migrations & Append-Only Integrity)**: `inventory_intel`/`unit_risk`/
  `anomalies` are analytics tables (DAT-003) - never touched by transactional code, never
  mutated in place once a run completes (a re-run creates a new `run_id`), matching Phase 4's
  `forecasts`/`forecast_metrics` precedent exactly.
- **Principle V (Analytics Reproducibility & Scientific Integrity)**: ABC/XYZ cutoffs and the
  z-score/ESD anomaly logic get hand-computed fixture tests before pipeline wiring, same
  discipline as Phase 3's SBC classifier and Phase 4's forecast metrics; QA-003(b) becomes a
  CI-blocking scientific validation test starting now (see spec.md Assumptions for why this is
  in scope despite the SRS table row not spelling out "QA-003(b)" literally - same judgment call
  Phase 4's own row made explicit for part (a)).
- **Principle VII (Testing bar)**: QA-003(b) CI-blocking from this phase forward - verified by
  actually running the detector against Phase 3's real persisted ground truth and computing
  recovery/false-positive rates directly, not asserting them structurally.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/006-inventory-anomalies/
├── plan.md              # this file (research/data-model/quickstart folded in below,
│                        # matching Phase 3/4's single-file plan.md precedent)
└── tasks.md              # Phase 2 output
```

### Source code

```text
packages/analytics/src/dealeriq_analytics/
├── sbc.py, generator/, forecasting/    # existing (Phases 3-4) - untouched
├── inventory/
│   ├── __init__.py
│   ├── abc_xyz.py            # DS-INV-001: revenue-share ABC + demand-CV XYZ classification
│   ├── reorder.py             # DS-INV-002: reorder point from a champion forecast's
│   │                          # q-quantile of lead-time demand
│   └── survival.py             # DS-INV-003/004: days-on-lot, Kaplan-Meier fit per segment,
│                                # 30-day sale probability + worst-decile flag
└── anomalies_detector/
    ├── __init__.py
    ├── series_anomalies.py    # DS-ANO-001/002: STL (robust=False) + robust z-score,
    │                          # generalized ESD confirmation
    └── transaction_anomalies.py  # DS-ANO-003: per-model discount-outlier check

packages/analytics/tests/
├── test_abc_xyz.py                 # hand-computed cutoff fixtures
├── test_reorder.py                  # reorder-point arithmetic vs hand calculation
├── test_survival.py                  # Kaplan-Meier fixture (toy censored/uncensored data)
├── test_series_anomalies.py           # z-score/ESD vs hand-computed toy series
├── test_transaction_anomalies.py       # discount-outlier fixture
└── test_qa003b_scientific_validation.py  # CI-blocking: recovery/false-positive rate vs
                                            # Phase 3's real persisted ground truth

apps/api/src/dealeriq_api/
├── domain/models/
│   └── inventory_intel.py       # InventoryIntel, UnitRisk, Anomaly SQLAlchemy models
├── domain/
│   └── inventory_job.py          # orchestration: read orders/units/forecasts ->
│                                  # packages/analytics -> write run/inventory_intel/
│                                  # unit_risk/anomalies, reusing Phase 4's AnalyticsRun
├── jobs/
│   └── inventory.py               # job registry entry, job_name="inventory" (mirrors
│                                   # jobs/forecast.py's pattern exactly)
├── routes/
│   └── inventory_intel.py          # GET /inventory/abc-xyz (heatmap), GET /inventory/units
│                                    # (aging/risk list), GET /anomalies (list, filterable)
└── schemas/
    └── inventory_intel.py

apps/api/alembic/versions/
└── <rev>_inventory_anomalies.py    # inventory_intel, unit_risk, anomalies tables + indices

apps/web/app/(authenticated)/inventory-intel/
├── page.tsx                        # ABC/XYZ heatmap (9 cells) + anomaly list, filterable
└── [modelId]/page.tsx               # per-model drill-down: reorder point, aging units,
                                     # survival curve
```

**Structure Decision**: extends the existing three-package monorepo - no new top-level
directories. `inventory/` and `anomalies_detector/` sit alongside `forecasting/` in
`packages/analytics`, mirroring the established Phase 3/4 split of pure computation vs. thin
`apps/api` orchestration. Reuses Phase 4's `AnalyticsRun` table rather than adding a second
run-tracking mechanism - this job is `job_name="inventory"`, a sibling of `job_name="forecast"`,
not a new pattern.

## ABC/XYZ classification (DS-INV-001)

Per model (across all branches, matching the SRS's model-level revenue framing): ABC by
cumulative revenue share, sorted descending - cumulative ≤ 80% is A, next up to 95% is B, the
remainder is C (the standard boundary convention: a model straddling a cutoff belongs to the
looser class, since its inclusion is what crosses the boundary). XYZ by coefficient of variation
of weekly unit demand (using the same weekly series Phase 4's `packages/analytics/forecasting/
series.py` already builds - reused, not recomputed) - CV < 0.5 is X, 0.5-1.0 is Y, > 1.0 is Z.
Models with zero order history are excluded from the ranked matrix and surfaced separately as
"insufficient history" (spec.md Edge Cases).

## Reorder points (DS-INV-002)

For each (model, branch) with a succeeded Phase 4 forecast run: read that series' persisted
12-week point forecast + the CV fold residual distribution already stored in
`forecast_metrics` (mean and spread are recoverable from the champion's CV MASE and the
persisted quantile columns `forecasts.yhat_lo80`/`yhat_hi80`, which bracket the 80% interval -
the reorder point uses the configurable service-level quantile, default 90%, interpolated from
that same interval rather than assuming a parametric distribution). Reorder point = sum of the
per-week q-quantile demand over the configured lead-time window (default 2 weeks, configurable).
A (model, branch) with no succeeded forecast run is skipped with a recorded reason (spec.md User
Story 2, Acceptance Scenario 2) - never backed by a fabricated forecast.

## Unit aging & survival (DS-INV-003, DS-INV-004)

Days-on-lot = `today - vehicle_units.acquisition_date` for every `in_stock`/`reserved` unit;
flagged if past the segment's configurable aging threshold (default 90 days). For DS-INV-004,
time-to-sale per segment is built from `stock_movements` (a unit's `RECEIPT` to its `SALE`
event, both already ledgered per FR-021) - sold units are uncensored observations, still-in-stock
units are right-censored at their current age (`lifelines.KaplanMeierFitter` handles censoring
natively, which is precisely why a plain histogram of past sale times would be wrong here: it
would silently exclude every unit that hasn't sold yet, biasing toward fast-moving stock). Given
the fitted per-segment curve, each in-stock unit's 30-day sale probability = `1 -
S(age+30)/S(age)` (conditional survival); units in the worst probability decile are flagged.

## Anomaly detection (DS-ANO-001, DS-ANO-002)

Reuses Phase 4's weekly series construction for (branch, segment) sales series, plus two new
weekly series (average discount, average margin per branch/segment) built the same
calendar-aligned, zero-filled way. STL decomposition with `robust=False` (per Phase 3's own
empirically-verified finding - see spec.md Assumptions), residuals scored by modified z-score
`0.6745*(resid-median)/MAD`; `|z| > 3.5` flags an anomaly, severity = `min(|z|/3.5, 5.0)`
(capped, so one extreme outlier doesn't dominate a downstream severity-sorted list). Series
whose residual MAD falls below Phase 3's `MIN_STABLE_MAD=0.2` floor are skipped with a recorded
reason (the exact degeneracy Phase 3 diagnosed). For series with ≥ 2 full seasonal cycles of
history, the generalized ESD test (`scipy.stats` doesn't ship this directly - implemented as a
small, independently unit-tested function per the published Rosner 1983 algorithm, since this is
a well-defined textbook procedure, not a judgment call) runs on the same residuals and its
confirmation (or non-confirmation) is stored alongside the z-score, never gating whether the
z-score anomaly itself is persisted (DS-ANO-002: "both scores are stored").

## Transaction-level anomalies (DS-ANO-003)

Per model, compute the mean and σ of `orders.discount` across all historical orders for that
model (existing `discount` column, no new data needed). Flag any order whose `negotiated_price <
list_price - k*σ(discount)` for that model, k configurable (default 3). Models with fewer than
5 historical orders are skipped (σ is not meaningfully estimable) - mirrors Phase 3's own
`MIN_ORDERS_FOR_PRICING_STATS=5` floor used when injecting these same errors, so the detector's
statistical floor matches the generator's own.

## Persistence & orchestration (DS-ANO-004, reusing FR-070)

`inventory_intel` (run_id, model_id, branch_id, abc, xyz, reorder_point, safety_stock,
service_level), `unit_risk` (run_id, unit_id, days_on_lot, p_sale_30d, risk_decile), `anomalies`
(run_id, scope, series_key/entity_id, observed, expected, score, method, severity, status) -
schema matches SRS §7 verbatim, all FK'd to `analytics_runs.id`. `POST /jobs/inventory/run`
(admin-only, C-03) follows Phase 4's exact `forecast_job.py` lifecycle pattern
(running→succeeded/failed, concurrency guard via conditional insert in the same transaction) -
literally the same orchestration shape, different pipeline. `anomalies.status` defaults to
`"new"` - a status field Phase 6's alert engine can transition, not one this phase manages
beyond writing the initial value (DS-ANO-004: "feed rule FR-061(c)... without this phase building
the alert engine itself").

## Validation sequence (proves the phase works end-to-end)

1. `POST /jobs/inventory/run` against the real seeded dataset (after Phase 4's forecast job has
   already succeeded at least once); poll `GET /jobs/inventory/runs` until `status=succeeded`.
2. Query the ABC/XYZ heatmap endpoint; confirm every model with order history appears in exactly
   one of the 9 cells and the counts sum to the classified-model total (SC-001).
3. For a sample (model, branch), hand-compute the reorder point from that series' persisted
   Phase 4 forecast and compare to the stored value (SC-002).
4. Confirm every in-stock unit has a `unit_risk` row with a plausible `days_on_lot`, and that
   units past threshold are flagged (SC-003).
5. Run the QA-003(b) validation directly against Phase 3's persisted ground-truth anomaly
   records: recovery rate ≥ 80%, false-positive rate ≤ 10% (SC-004) - wired as a CI-blocking
   pytest from this point forward, mirroring QA-003(a)'s treatment in Phase 4.
6. Open the inventory-intelligence workbench in a real browser; confirm the heatmap and anomaly
   list render real data from the run just triggered (SC-005).
