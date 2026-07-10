# Tasks: Forecasting Engine

**Input**: plan.md from `specs/005-forecasting-engine/`

## Task list

- [x] T001 Add `statsforecast` to `packages/analytics/pyproject.toml` dependencies (ADR-005/018)
- [x] T002 `forecasting/series.py`: build weekly (model,branch) and (segment,branch) series from
      an orders dataframe, explicit calendar alignment + zero-fill (DS-FC-001)
- [x] T003 Unit tests: series construction calendar-alignment and zero-fill edge cases
- [x] T004 `forecasting/metrics.py`: MASE, sMAPE, pinball loss (q=0.1/0.5/0.9), 80%-coverage
      (DS-FC-005)
- [x] T005 Unit tests: every metric in T004 against hand-computed fixtures, written and passing
      *before* any pipeline code calls them (constitution Principle V)
- [x] T006 `forecasting/methods.py`: thin wrapper around statsforecast's model pool (Naive,
      SeasonalNaive, SimpleExponentialSmoothing, AutoETS, AutoARIMA, CrostonClassic, CrostonSBA,
      TSB) (DS-FC-003)
- [x] T007 `forecasting/cv.py`: rolling-origin CV harness (52-week min training window, 4-week
      step, 12-week horizon, n_windows=24 for this dataset's 156 weeks) (DS-FC-004)
- [x] T008 Unit test: CV fold count/boundaries match the derived n_windows=24 for a 156-week
      series; a too-short series raises a clear error rather than silently skipping
- [x] T009 `forecasting/champion.py`: per-series champion selection (lowest mean CV MASE, must
      beat Seasonal Naive or Seasonal Naive itself is champion) + final full-history refit for
      the persisted 12-week forecast + 80% interval (DS-FC-006, DS-FC-007)
- [x] T010 Unit test: champion selection never returns a method that lost to Seasonal Naive;
      exact-tie resolves to Seasonal Naive; a method that failed every CV fold is never champion
- [x] T011 `apps/api/src/dealeriq_api/domain/models/analytics.py`: `AnalyticsRun`,
      `SeriesProfile`, `Forecast`, `ForecastMetric` SQLAlchemy models (schema per SRS §7)
- [x] T012 Alembic migration: `analytics_runs`, `series_profiles`, `forecasts`,
      `forecast_metrics` tables + indices (DAT-004: `forecasts(run_id, series_key)`); new
      permission keys (`jobs:trigger`, `forecasts:view`) granted per SRS role table
- [x] T013 `apps/api/src/dealeriq_api/domain/forecast_job.py`: orchestration — reads
      orders/vehicle_units, calls `packages/analytics.forecasting`, writes
      run/series_profiles/forecasts/forecast_metrics inside the run's transaction
      (running→succeeded/failed lifecycle, never left dangling)
- [x] T014 `apps/api/src/dealeriq_api/jobs/forecast.py`: register the job with APScheduler
      (ADR-004) so it's addressable by `job_name="forecast"` — no cron trigger yet, just the
      registry entry the HTTP trigger needs
- [x] T015 `apps/api/src/dealeriq_api/routes/jobs.py`: `POST /jobs/{job_name}/run` (admin-only,
      C-03, FR-072 concurrency guard via conditional insert), `GET /jobs/{job_name}/runs`
      (FR-071 run history)
- [x] T016 `apps/api/src/dealeriq_api/routes/forecasts.py` +
      `apps/api/src/dealeriq_api/schemas/forecasts.py`: `GET /forecasts` (leaderboard, latest
      succeeded run by default, `run_id` query param for historical runs), `GET
      /forecasts/{series_key}` (fan-chart points + that series' CV metrics)
- [x] T017 Integration tests (testcontainers-python, ADR-013): full job run persists a
      `succeeded` run + forecasts/metrics for every series; a second trigger while one is
      `running` is rejected (409); a run that raises mid-job ends `failed`, not `running` forever
- [x] T018 Regenerate `packages/api-client` against the new endpoints
- [x] T019 `apps/web/app/(authenticated)/analytics/page.tsx`: leaderboard — champion win counts
      + mean MASE by SBC class, filterable, consuming only the generated client
- [x] T020 `apps/web/app/(authenticated)/analytics/[seriesKey]/page.tsx`: fan chart (actuals +
      point forecast + 80% interval band) and that series' CV metrics table
- [x] T021 Sidebar nav: add an Analytics entry, gated on `forecasts:view`
- [x] T022 Run the full forecast job against the real Phase 3 dataset (66+15 series); verify
      every series has exactly one champion whose mean CV MASE ≤ Seasonal Naive's (SC-001, SC-002)
- [x] T023 Verify SC-003/QA-003a directly: champion beats Seasonal Naive's MASE (strictly) on
      ≥60% of intermittent-class series; wire this check as a CI-blocking pytest from this point
      forward (constitution Principle VII)
- [x] T024 Verify SC-004: triggering a second run while one is in progress is rejected, not run
      concurrently — a real HTTP-level check, not just a unit test of the guard function
- [x] T025 Verify SC-005 in a real browser: trigger a run, watch the leaderboard and at least one
      fan chart render real data from it
- [x] T026 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci` (now
      including the new CI-blocking QA-003a test)
