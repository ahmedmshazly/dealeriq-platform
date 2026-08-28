# Tasks: Inventory Intelligence & Anomalies

**Input**: plan.md from `specs/006-inventory-anomalies/`

## Task list

- [x] T001 Add `lifelines` to `packages/analytics/pyproject.toml` dependencies (ADR-017)
- [x] T002 `inventory/abc_xyz.py`: ABC (cumulative revenue share: A ≤80%, B ≤95%, C remainder) +
      XYZ (demand CV: X<0.5, Y 0.5-1.0, Z>1.0) classification per model, reusing Phase 4's
      weekly-series builder; models with zero order history excluded, not force-classified
      (DS-INV-001)
- [x] T003 Unit tests: ABC/XYZ against hand-computed fixtures (boundary cases: a model exactly at
      the 80%/95% cumulative cutoff; a model with zero history)
- [x] T004 `inventory/reorder.py`: reorder point = service-level quantile (default 90%) of
      lead-time demand, summed over the configurable lead-time window, read from Phase 4's
      persisted champion forecast + 80% interval; (model,branch) pairs with no succeeded forecast
      run skipped with a recorded reason (DS-INV-002)
- [x] T005 Unit test: reorder-point arithmetic against a hand-computed example; confirms the
      "no forecast run yet" skip path records a reason rather than defaulting to zero
- [x] T006 `inventory/survival.py`: days-on-lot per unit + configurable-per-segment aging
      threshold (default 90 days) (DS-INV-003); Kaplan-Meier fit per segment via `lifelines`
      from `stock_movements` RECEIPT→SALE spans (sold=uncensored, in-stock=right-censored at
      current age), 30-day conditional sale probability + worst-decile flag (DS-INV-004)
- [x] T007 Unit tests: days-on-lot arithmetic; a toy Kaplan-Meier fixture (small hand-verifiable
      censored/uncensored dataset) confirming the fitted survival probabilities match a manual
      calculation
- [x] T008 `anomalies_detector/series_anomalies.py`: STL (`robust=False`, reusing Phase 3's
      `MIN_STABLE_MAD=0.2` floor) + modified z-score (`|z|>3.5` flags, severity=min(|z|/3.5,5.0))
      over sales/discount/margin weekly series per branch/segment (DS-ANO-001); hand-implemented
      generalized ESD test (ADR-017, Rosner 1983) run on the same residuals, both scores always
      persisted regardless of ESD outcome (DS-ANO-002)
- [x] T009 Unit tests: z-score detector against a hand-constructed toy series with a known
      injected outlier; GESD implementation validated directly against Rosner (1983)'s published
      worked example (same inputs, same expected outlier count) per ADR-017
- [x] T010 `anomalies_detector/transaction_anomalies.py`: flag orders where
      `negotiated_price < list_price - k*σ(historical discount for that model)`, k configurable
      (default 3); models with <5 historical orders skipped (mirrors Phase 3's
      `MIN_ORDERS_FOR_PRICING_STATS=5`) (DS-ANO-003)
- [x] T011 Unit test: transaction anomaly detector against a hand-computed discount-distribution
      fixture, including the <5-orders skip path
- [x] T012 `apps/api/src/dealeriq_api/domain/models/inventory_intel.py`: `InventoryIntel`,
      `UnitRisk`, `Anomaly` SQLAlchemy models (schema per SRS §7 verbatim column names)
- [x] T013 Alembic migration: `inventory_intel`, `unit_risk`, `anomalies` tables + indices, all
      FK'd to `analytics_runs.id`; no new permission keys needed (reuses `jobs:trigger`/
      `forecasts:view`-equivalent - add `inventory:view` granted to admin/manager/analyst per the
      SRS role table's existing analytics-facing pattern)
- [x] T014 `apps/api/src/dealeriq_api/domain/inventory_job.py`: orchestration - reads
      orders/vehicle_units/stock_movements + Phase 4's latest succeeded forecast run, calls
      `packages/analytics` inventory + anomaly modules, writes
      run/inventory_intel/unit_risk/anomalies inside the run's transaction
      (running→succeeded/failed lifecycle, mirroring `forecast_job.py` exactly)
- [x] T015 `apps/api/src/dealeriq_api/jobs/inventory.py`: register the job so it's addressable by
      `job_name="inventory"` (mirrors `jobs/forecast.py`'s pattern)
- [x] T016 `apps/api/src/dealeriq_api/routes/jobs.py`: add `"inventory"` to `KNOWN_JOBS` (the
      existing `POST /jobs/{job_name}/run` / `GET /jobs/{job_name}/runs` routes already generalize
      to any registered job - no new route code needed, just the registry entry)
- [x] T017 `apps/api/src/dealeriq_api/routes/inventory_intel.py` +
      `apps/api/src/dealeriq_api/schemas/inventory_intel.py`: `GET /inventory/abc-xyz` (heatmap,
      latest succeeded run by default), `GET /inventory/units` (aging/risk list, filterable by
      past-threshold/worst-decile), `GET /anomalies` (list, filterable by scope/severity/status)
- [x] T018 Integration tests (testcontainers-python, ADR-013): full inventory job run persists
      `inventory_intel`/`unit_risk`/`anomalies` rows for a seeded dataset; a second trigger while
      one is `running` is rejected (409); a run that raises mid-job ends `failed`, not `running`
      forever; a run triggered before any Phase 4 forecast run exists skips reorder-point rows
      with a recorded reason rather than failing the whole run
- [x] T019 Regenerate `packages/api-client` against the new endpoints
- [x] T020 `apps/web/app/(authenticated)/inventory-intel/page.tsx`: ABC/XYZ heatmap (9 cells,
      each showing member models) + anomaly list (filterable by scope/severity), consuming only
      the generated client
- [x] T021 `apps/web/app/(authenticated)/inventory-intel/[modelId]/page.tsx`: per-model
      drill-down - reorder point + safety stock, aging units list, survival-curve-derived 30-day
      sale probabilities for that model's units
- [x] T022 Sidebar nav: add an Inventory Intelligence entry, gated on `inventory:view`
- [x] T023 `packages/analytics/tests/test_qa003b_scientific_validation.py`: run the anomaly
      detector against Phase 3's real generator output in-memory (same ground truth
      `inject_demand_shocks`/`find_near_miss_points`/`_inject_pricing_errors` produce) and assert
      recovery rate ≥80% at false-positive rate ≤10%; wire as a CI-blocking pytest from this
      point forward (constitution Principle VII, spec.md Assumptions on QA-003(b) scope)
- [x] T024 Run the full inventory job against the real Phase 3/4 dataset (after triggering a
      Phase 4 forecast run first); verify every model with order history has an ABC/XYZ cell and
      every (model,branch) with a succeeded forecast has a reorder point (SC-001, SC-002)
- [x] T025 Verify SC-003 directly: every in-stock unit has a `unit_risk` row with a plausible
      `days_on_lot`; units past threshold are flagged - a real DB query, not just unit-test
      assertions
- [x] T026 Verify SC-004/QA-003(b) directly against the real seeded database's known-injected
      anomalies (cross-check T023's in-memory result against the DB-backed run's actual detected
      anomalies, the same double-verification pattern Phase 4 used for QA-003a)
- [x] T027 Verify SC-005 in a real browser: trigger a run, watch the ABC/XYZ heatmap and anomaly
      list render real data from it; drill into at least one model's detail page
- [x] T028 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci` (now
      including the new CI-blocking QA-003b test alongside QA-003a)
