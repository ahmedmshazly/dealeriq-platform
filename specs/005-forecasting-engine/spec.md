# Feature Specification: Forecasting Engine

**Feature Branch**: `005-forecasting-engine`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 4 — "DS-FC-001..007, FR-070..072, QA-003a"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every analytics job is a reproducible, recorded run (Priority: P1)

As an Admin, when I trigger the weekly forecast job (or it runs on schedule later), I get a
recorded `analytics_runs` row (job name, params, code version, data snapshot bounds, seed,
timing, status, metrics) — so results are always traceable to exactly what produced them, and
a second identical run never overlaps the first.

**Why this priority**: FR-070..072 aren't forecasting-specific — they're the run-tracking
contract every later analytics job (Phases 5-8) will reuse. Getting this pattern right now, on
the first analytics job, is what makes it a pattern rather than a one-off.

**Independent Test**: Trigger the job twice back-to-back via the API; the second call is
rejected (or queued, not run concurrently) while the first is still `running`; both eventually
show a complete row with real timing and status.

**Acceptance Scenarios**:

1. **Given** an Admin triggers a forecast run via `POST /api/v1/jobs/forecast/run` (the SRS's
   own `POST /jobs/{job_name}/run` convention, C-03), **When** the job finishes, **Then** an
   `analytics_runs` row exists with `status=succeeded`, real
   `started_at`/`finished_at`, the seed used, and summary metrics (FR-070).
2. **Given** a run is already `running`, **When** a second trigger request arrives for the same
   job, **Then** it is rejected with a conflict, not started concurrently (FR-072).
3. **Given** multiple completed runs exist, **When** an Analyst opens the workbench, **Then** it
   shows the latest successful run's forecasts by default, with older runs viewable on request
   (FR-071).

---

### User Story 2 - Per-series champion forecast, never worse than the naive floor (Priority: P1)

As an Analyst, for every (model, branch) demand series, I see a 12-week point forecast with an
80% interval from whichever method actually won a fair, per-series competition — and that method
is never one that couldn't even beat Seasonal Naive.

**Why this priority**: This is the actual analytical deliverable of the phase — everything else
(run tracking, CV harness, metrics) exists to make this comparison honest and reproducible.

**Independent Test**: Run the full pipeline on the Phase 3 dataset; for every series, confirm
the recorded champion's mean CV-fold MASE is <= Seasonal Naive's on that same series.

**Acceptance Scenarios**:

1. **Given** a (model, branch) series, **When** the forecast job runs, **Then** every method in
   the pool (DS-FC-003) is evaluated via rolling-origin CV (DS-FC-004) and the champion is the
   one with the lowest mean MASE across folds (DS-FC-006).
2. **Given** a series where no method beats Seasonal Naive, **When** champion selection runs,
   **Then** Seasonal Naive itself is recorded as champion — never a method that lost to it.
3. **Given** a completed run, **When** an Analyst opens a series' detail view, **Then** they see
   actuals, the champion's point forecast, and its 80% interval as a fan chart, plus that
   series' CV metrics table (DS-FC-007).

---

### User Story 3 - A leaderboard that lets an Analyst trust the forecasts (Priority: P2)

As an Analyst, I can see, across all series, which methods win how often and by how much — so I
can sanity-check the pipeline itself, not just individual forecasts.

**Why this priority**: Directly what the SRS's stated exit demo asks for ("leaderboard + fan
charts"); depends on User Story 2's data existing first.

**Independent Test**: Open the workbench leaderboard; confirm it aggregates real per-series
champion/metric data from the latest run, filterable by SBC class.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** an Analyst opens the leaderboard, **Then** they see
   champion-method win counts and mean MASE broken down by SBC demand class (smooth/erratic/
   intermittent/lumpy).

### Edge Cases

- What happens for a series too short for the minimum 52-week CV training window? Every Phase 3
  series has the full 156 weeks of history, so this can't occur on the seeded dataset; the CV
  harness raises a clear error rather than silently skipping or padding if it ever does (fail
  loud, not lossy-silent).
- What happens when AutoARIMA or ETS fails to converge for a pathological series? That method's
  CV fold is recorded as failed/excluded for that series rather than crashing the whole run;
  Seasonal Naive always has a result, so a champion can always be selected.
- What happens if a run is triggered while `make seed` hasn't populated any orders yet? The job
  fails fast with a clear "no series data" error recorded on the run row, not a silent empty
  success.

## Requirements *(mandatory)*

- **DS-FC-001**: Weekly demand series per (model, branch) and per (segment, branch) constructed
  from the order ledger, with explicit calendar alignment and zero-filling for weeks with no
  sales.
- **DS-FC-002** *(already built in Phase 3, `packages/analytics/src/dealeriq_analytics/sbc.py`;
  reused here, not rebuilt)*: SBC classification (smooth/erratic/intermittent/lumpy; ADI=1.32,
  CV²=0.49).
- **DS-FC-003**: Method pool — Naive, Seasonal Naive, Simple Exponential Smoothing, ETS
  (automatic), AutoARIMA, Croston, SBA, TSB — via statsforecast (ADR-005, narrowed by ADR-018
  to statsforecast-only for this pool; statsmodels stays scoped to STL for Phase 5's detector).
- **DS-FC-004**: Rolling-origin (expanding-window) cross-validation: minimum 52-week training
  window, 4-week step, 12-week horizon.
- **DS-FC-005**: Point-forecast accuracy via MASE (primary) and sMAPE (secondary); interval
  quality via pinball loss at q ∈ {0.1, 0.5, 0.9} and empirical 80%-interval coverage.
- **DS-FC-006**: Per-series champion = lowest mean MASE across CV folds; Seasonal Naive is the
  mandatory floor — no method is champion unless it beats Seasonal Naive on MASE.
- **DS-FC-007**: Weekly forecast job output per series — 12-week point forecasts, 80% intervals,
  champion method id, CV metrics — persisted to `forecasts`/`forecast_metrics`, keyed by run.
- **FR-070**: Every analytics execution recorded as a run: job name, parameters, code/package
  version, data snapshot bounds, seed, started/finished timestamps, status, metrics.
- **FR-071**: Forecast outputs versioned per run; dashboards read the latest successful run by
  default; Analysts can view any historical run.
- **FR-072**: Admins can trigger any job on demand via UI/API, with a concurrency guard (a job
  cannot run twice simultaneously).
- **QA-003(a)**: Scientific validation, CI-blocking from this phase onward — champion methods
  beat Seasonal Naive on ≥60% of intermittent-class series.

*(DS-FC-008/009, both P1, are backlogged per `docs/backlog.md` — bottom-up reconciliation
diagnostic and per-fold residual diagnostics view are both explicitly deferrable stretch goals
per the SRS's own priority marking, not load-bearing for the P0 champion-selection pipeline.)*

### Key Entities

- **AnalyticsRun**: one row per job execution — job name, params (JSON), seed, code/package
  version, data snapshot bounds, status (running/succeeded/failed), started/finished
  timestamps, summary metrics (JSON). The append-only backbone every other Phase-4+ table hangs
  off via `run_id`.
- **SeriesProfile**: one row per (series_key, run) — the ADI/CV²/SBC class computed for that
  series in that run, so historical runs remain self-describing even if the classifier's cutoffs
  ever change.
- **Forecast**: one row per (run, series_key, week_start) — point forecast, 80% interval bounds,
  method used.
- **ForecastMetric**: one row per (run, series_key, method) — MASE, sMAPE, pinball@{10,50,90},
  80%-coverage, and whether this method was that series' champion.

## Success Criteria *(mandatory)*

- **SC-001**: The forecast job runs end-to-end against the real Phase 3 dataset (66 series) and
  completes in a reasonable local-dev time budget, recording one `analytics_runs` row with
  `status=succeeded`.
- **SC-002**: Every series has exactly one champion method whose mean CV-fold MASE is ≤ Seasonal
  Naive's mean CV-fold MASE on that same series — no exceptions.
- **SC-003 (QA-003a)**: Across intermittent-class series, the champion method beats Seasonal
  Naive's MASE on ≥60% of them (a stronger bar than SC-002's "at least ties," and the one that's
  CI-blocking from this phase forward).
- **SC-004**: Triggering a second run while one is in progress is rejected, not run concurrently.
- **SC-005**: The Analyst workbench's leaderboard and fan-chart views render real per-series
  forecast/metric data from the latest successful run — verified in a real browser, not just via
  API response shape.

## Assumptions

- The forecasting pipeline lives in `packages/analytics` (pure computation, testable without a
  DB) with a thin `apps/api` orchestration layer that reads orders/leads from Postgres, invokes
  the pipeline, and writes `analytics_runs`/`forecasts`/`forecast_metrics`/`series_profiles` —
  mirroring the existing domain-service pattern (`order_service.py` etc.), not a separate
  execution framework. APScheduler (ADR-004, already SRS-fixed) backs the job registry, but only
  the on-demand HTTP trigger (`POST /jobs/{job_name}/run`, C-03) is wired this phase; actual
  nightly cron scheduling is Phase 6's concern (alerts/notifications runbook) per the SRS's own
  phase split — this phase only needs the job to be triggerable, not self-scheduling.
- Concurrency guard (FR-072) is implemented as a simple "is any run for this job_name currently
  `running`?" check inside the same transaction that creates the new run row, not a distributed
  lock — appropriate for this project's single-instance local-first deployment model (consistent
  with ADR-020's rate-limiter precedent of choosing the simplest correct mechanism for this
  deployment scale).
- Per (model, branch) series only — per (segment, branch) aggregate series (also required by
  DS-FC-001) are constructed and profiled the same way but do not get their own champion
  selection UI in this phase; they exist so Phase 8 dashboards can show segment-level rollups
  without recomputing from raw orders.
