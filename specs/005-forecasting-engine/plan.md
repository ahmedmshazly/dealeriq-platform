# Implementation Plan: Forecasting Engine

**Branch**: `005-forecasting-engine` | **Date**: 2026-07-10 | **Spec**: `specs/005-forecasting-engine/spec.md`

## Summary

A pure-computation forecasting pipeline (`packages/analytics`, no DB dependency, independently
testable) - construct weekly series from orders, classify by SBC, run every DS-FC-003 method
through rolling-origin CV, score with MASE/sMAPE/pinball/coverage, select a per-series champion
never worse than Seasonal Naive - plus a thin `apps/api` orchestration layer that wraps it in the
FR-070/071/072 run-tracking contract every later analytics job will reuse, and an Analyst
workbench (leaderboard + fan charts) consuming only the generated API client.

## Technical Context

**Language/Version**: Python 3.12 (`packages/analytics`, `apps/api`), TypeScript/Next.js 15
(`apps/web`) - unchanged from prior phases.

**Primary Dependencies**: `statsforecast` (ADR-005, narrowed by ADR-018 to be the sole DS-FC-003
method-pool implementation - `statsmodels` stays scoped to STL for Phase 5), added to
`packages/analytics`'s dependencies this phase. `apps/api` gains no new dependencies -
APScheduler is already present (ADR-004) but this phase only wires the on-demand HTTP trigger,
not cron registration.

**Storage**: PostgreSQL 16, four new tables (`analytics_runs`, `series_profiles`, `forecasts`,
`forecast_metrics`) per one new Alembic migration, per the SRS §7 schema (verbatim column names).

**Testing**: pytest (metrics against hand-computed fixtures, BEFORE wiring into the pipeline, per
the project's standing working rule), testcontainers-python for the run/API integration tests
(ADR-013, same pattern as Phases 1-2).

**Target Platform**: unchanged - Docker Compose local dev, single-instance.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) - no new top-level project.

**Performance Goals**: full pipeline (66 series × 8 methods × 24 CV folds ≈ 12,672 fits) completes
in a reasonable local-dev budget - target well under a minute, since statsforecast vectorizes
across series and the method pool is all classical/lightweight (no deep learning).

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (the forecast job is triggered on demand, not part of bootstrap/seed); QA-003(a)
becomes CI-blocking starting this phase.

**Scale/Scope**: 66 (model, branch) series from Phase 3's dataset, plus a smaller number of
(segment, branch) aggregate series (5 segments × 3 branches = 15) per DS-FC-001's second series
type - 81 series total, comfortably under NFR-004's 500-series bound (already referenced in
Phase 3's plan.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: forecasting logic in `packages/analytics`,
  orchestration/routes in `apps/api`, UI in `apps/web` consuming only the generated client - no
  new top-level package.
- **Principle IV (Migrations & Append-Only Integrity)**: `analytics_runs`/`forecasts`/
  `forecast_metrics`/`series_profiles` are analytics tables (DAT-003) - never touched by
  transactional code, and never mutated in place once a run completes (a re-run creates a new
  `run_id`, it doesn't update old rows) - append-only in spirit even though not literally an
  event ledger like `stock_movements`.
- **Principle V (Analytics Reproducibility & Scientific Integrity)**: this is the principle this
  entire phase operationalizes - MASE/pinball/coverage computed and unit-tested against
  hand-computed fixtures *before* being wired into the CV harness (same discipline Phase 3 used
  for SBC classification); QA-003(a) becomes a CI-blocking scientific validation test starting
  now, per the constitution's own phase-4-trigger language.
- **Principle VII (Testing bar)**: QA-003(a) CI-blocking from this phase forward - verified by
  actually running the full pipeline against the real Phase 3 dataset and checking the ≥60%
  figure, not asserting it structurally.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/005-forecasting-engine/
├── plan.md              # this file (research/data-model/quickstart folded in below,
│                        # matching Phase 3's single-file plan.md precedent)
└── tasks.md              # Phase 2 output
```

### Source code

```text
packages/analytics/src/dealeriq_analytics/
├── sbc.py                       # existing (Phase 3) — reused as-is
├── generator/                   # existing (Phase 3) — untouched
└── forecasting/
    ├── __init__.py
    ├── series.py                 # DS-FC-001: build weekly (model,branch) and
    │                              # (segment,branch) series from an orders dataframe,
    │                              # explicit calendar alignment + zero-fill
    ├── metrics.py                 # DS-FC-005: MASE, sMAPE, pinball loss, 80%-coverage —
    │                              # unit-tested against hand-computed fixtures first
    ├── methods.py                  # DS-FC-003: thin wrapper around statsforecast's
    │                               # model pool (Naive, SeasonalNaive, SES, AutoETS,
    │                               # AutoARIMA, CrostonClassic, CrostonSBA, TSB)
    ├── cv.py                        # DS-FC-004: rolling-origin CV harness (52-week
    │                                # min training window, 4-week step, 12-week horizon)
    └── champion.py                  # DS-FC-006/007: per-series champion selection
                                      # (Seasonal Naive floor) + final 12-week forecast
                                      # + 80% interval assembly

packages/analytics/tests/
├── test_forecast_metrics.py     # MASE/sMAPE/pinball/coverage vs hand-computed fixtures
├── test_forecast_series.py       # calendar alignment + zero-fill edge cases
├── test_forecast_cv.py            # fold count/boundaries against the 156-week dataset
└── test_champion_selection.py      # Seasonal-Naive-floor invariant, tie-breaking

apps/api/src/dealeriq_api/
├── domain/models/
│   └── analytics.py              # AnalyticsRun, SeriesProfile, Forecast, ForecastMetric
├── domain/
│   └── forecast_job.py            # orchestration: read orders -> packages/analytics ->
│                                   # write run/forecasts/metrics, inside one DB transaction
│                                   # per run for the run-row lifecycle (running->succeeded/failed)
├── jobs/
│   └── forecast.py                 # APScheduler job registration (ADR-004) — registers the
│                                    # job so it's addressable by job_name; no cron trigger yet
├── routes/
│   ├── jobs.py                      # POST /jobs/{job_name}/run, GET /jobs/{job_name}/runs
│   └── forecasts.py                  # GET /forecasts (leaderboard), GET /forecasts/{series_key}
└── schemas/
    └── forecasts.py

apps/api/alembic/versions/
└── <rev>_forecasting_engine.py     # analytics_runs, series_profiles, forecasts,
                                     # forecast_metrics tables + indices (DAT-004:
                                     # forecasts(run_id, series_key))

apps/web/app/(authenticated)/analytics/
├── page.tsx                        # leaderboard: champion win counts + mean MASE by
│                                    # SBC class, filterable
└── [seriesKey]/page.tsx             # fan chart: actuals + point forecast + 80% interval,
                                     # that series' CV metrics table
```

**Structure Decision**: extends the existing three-package monorepo - no new top-level
directories. `forecasting/` sits alongside `generator/` in `packages/analytics` since both are
pure, DB-free computation reused by a thin `apps/api` orchestration layer, mirroring the
established Phase 3 split.

## Series construction (DS-FC-001)

Two series families, both built from the `orders`/`vehicle_units` ledger (the same tables Phase
3's generator populated - no new source data):

- **(model, branch)**: 66 series, one per distinct `vehicle_units.model_id × branch_id` pair
  present in the order history (exactly the set Phase 3's demand generator produced).
- **(segment, branch)**: 15 series (5 segments × 3 branches), summing weekly unit counts across
  all models in that segment at that branch.

For both, weekly bins are calendar-aligned to the same Monday-start week convention
`infra/seed/generate.py` used (`REFERENCE_LAST_WEEK_START`-style anchoring, so week boundaries
match exactly what generated the data), and any week with zero deliveries in that window is
explicitly zero-filled - never dropped - since ADI/CV² (DS-FC-002) and every method in the pool
depend on a complete, gap-free weekly index.

## Method pool & CV harness (DS-FC-003, DS-FC-004)

`statsforecast.models`: `Naive`, `SeasonalNaive(season_length=52)`, `SimpleExponentialSmoothing`,
`AutoETS`, `AutoARIMA`, `CrostonClassic`, `CrostonSBA`, `TSB` - one `StatsForecast` instance per
run, all 8 models fit together across all series (statsforecast vectorizes this internally).

Rolling-origin CV via `StatsForecast.cross_validation(df, h=12, step_size=4, n_windows=24)`:
`n_windows=24` reproduces `floor((156-52-12)/4)+1=24`, the exact fold count Phase 3's plan.md
already derived for this dataset's 156-week length - the first fold's training window is the
minimum 52 weeks, each subsequent fold advances the origin 4 weeks, and the last fold's 12-week
test horizon lands exactly on the final week of history. A method that fails to converge on a
given series/fold (AutoARIMA/AutoETS are the two realistic candidates) has that fold recorded as
failed and excluded from that method's mean - never crashes the run; Seasonal Naive cannot fail
this way, so a champion always exists.

## Metrics (DS-FC-005) - unit-tested against hand-computed fixtures before pipeline wiring

- **MASE** (primary): mean absolute error of the forecast, scaled by the mean absolute seasonal
  (52-week) naive error on the *training* portion - scale-free and defined even when the series
  has zero periods (unlike MAPE), which is why it's DS-FC-005's primary metric for a dataset that
  includes intermittent/lumpy series.
- **sMAPE** (secondary): standard symmetric MAPE, reported alongside MASE for interpretability.
- **Pinball loss** at q ∈ {0.1, 0.5, 0.9}: `max(q*(y-yhat_q), (q-1)*(y-yhat_q))`, averaged across
  the horizon.
- **80%-interval empirical coverage**: fraction of actuals falling within `[yhat_lo80, yhat_hi80]`
  across all CV folds for that series/method.

Each has a small, hand-computed fixture test (3-5 point toy series with the metric computed by
hand) in `test_forecast_metrics.py`, following the same discipline Phase 3 used for `sbc.py`
before either was trusted inside a larger pipeline.

## Champion selection (DS-FC-006, DS-FC-007)

Per series: compute each method's mean MASE across its (non-failed) CV folds; the champion is
the minimum, **but only if it's ≤ Seasonal Naive's mean MASE on that same series** - if every
non-naive method loses to Seasonal Naive, Seasonal Naive itself is recorded as champion. Ties
resolve in DS-FC-003's listed method order (Seasonal Naive preferred on an exact tie, since it's
the simplest sufficient explanation). The champion's forecast is then refit on the *full* 156
weeks (not just a CV fold) to produce the actual persisted 12-week point forecast + 80% interval
that `forecasts` stores.

## Run orchestration & schema (FR-070..072)

`analytics_runs` (job_name, params_json, seed, code_version, data_from, data_to, status,
metrics_json, started_at, finished_at) is the append-only backbone; `series_profiles`
(series_key, adi, cv2, pattern_class, run_id) records that run's own SBC classification (so a
future change to the cutoffs doesn't retroactively reinterpret an old run); `forecasts` (run_id,
series_key, week_start, yhat, yhat_lo80, yhat_hi80, method) and `forecast_metrics` (run_id,
series_key, method, mase, smape, pinball_q10/50/90, coverage80, is_champion) hold the per-series
output - schema matches SRS §7's representative-resources list verbatim.

`POST /jobs/forecast/run` (admin-only, C-03) creates an `analytics_runs` row with
`status=running` in the same transaction it checks no other row for `job_name='forecast'` is
already `running` (FR-072's concurrency guard - a plain conditional insert, not a distributed
lock, consistent with this project's single-instance local-first deployment scope). On success
the row flips to `succeeded` with `finished_at`/`metrics_json` populated; on any exception it
flips to `failed` with the error captured in `metrics_json`, never left dangling as `running`.
`GET /forecasts` (leaderboard) and `GET /forecasts/{series_key}` (fan chart + metrics) both
default to the latest `succeeded` run, with an optional `run_id` query param for FR-071's
"Analysts can view any historical run."

## Validation sequence (proves the phase works end-to-end)

1. `POST /jobs/forecast/run` against the real Phase 3 dataset; poll `GET /jobs/forecast/runs`
   until `status=succeeded`.
2. Query `GET /forecasts` (leaderboard); confirm every one of the 66 (model,branch) series has
   exactly one `is_champion=true` row in `forecast_metrics`.
3. For every series, confirm the champion's `mase` ≤ Seasonal Naive's `mase` on that series
   (SC-002) - a throwaway script, not just asserted by the pipeline's own bookkeeping, mirroring
   Phase 3's "validate now, don't assume" treatment of its own generator.
4. Restrict to intermittent-class series (`series_profiles.pattern_class='intermittent'`);
   confirm the champion beats Seasonal Naive's MASE (strictly, not a tie) on ≥60% of them
   (SC-003 / QA-003a) - wired as a CI-blocking pytest from this point forward.
5. Open the Analyst workbench in a real browser; confirm the leaderboard and at least one fan
   chart render real data from the run just triggered (SC-005).
