# Tasks: Customer Analytics

**Input**: plan.md from `specs/008-customer-analytics-rfm/`

## Task list

- [x] T001 `apps/api/src/dealeriq_api/domain/models/customer_analytics.py`: `CustomerRfmProfile`,
      `LeadScore` SQLAlchemy models, both `run_id`-tagged per the established Forecast/
      InventoryIntel/Anomaly convention
- [x] T002 Alembic migration: `customer_rfm_profiles`, `lead_scores` tables + indices (per-run,
      per-customer/lead lookups); no new columns on `customers`/`leads` (DAT-003 separation); no
      new permissions (reuses existing `customers:view`/`leads:view`); verified via
      `alembic upgrade head` + `alembic check` (empty diff) + a downgrade/upgrade round-trip
      against the real dev Postgres
- [x] T003 `packages/analytics/src/dealeriq_analytics/customer/rfm.py`: per-customer R/F/M
      quintile scoring (population-relative, per run) + ADR-022's four ordered segment rules +
      the explicit zero-order "New" case; pure pandas/dataclasses, no DB imports
- [x] T004 `packages/analytics/tests/test_rfm.py`: hand-constructed fixtures for each of ADR-022's
      four segment rules plus the zero-order "New" edge case, boundary quintile values (also
      fixed a real bug found while writing these: the original rule order checked Loyal before
      At Risk, so a customer who was frequent/valuable but not recent got mislabeled "Loyal" —
      reordered so At Risk is checked first; ADR-022 updated to match)
- [x] T005 `packages/analytics/src/dealeriq_analytics/customer/psi.py`: Population Stability Index
      — a small, hand-implemented primitive (binned-distribution divergence sum)
- [x] T006 `packages/analytics/tests/test_psi.py`: PSI validated against a hand-computed fixture
      (known bin counts → known PSI value; an engineered shift exceeds 0.25, an unchanged
      distribution does not) before PSI is wired into the drift-alert pipeline
- [x] T007 `packages/analytics/src/dealeriq_analytics/customer/lead_scoring.py`: feature
      engineering (channel, budget band, model segment, days-since-creation, interaction count,
      customer RFM, cyclical seasonality) from plain records; DS-CUST-005's temporal train/val
      split; `LogisticRegression(class_weight="balanced")` (L2 is sklearn's default; the explicit
      `penalty="l2"` spelling is deprecated as of sklearn 1.8) wrapped in
      `CalibratedClassifierCV(method="isotonic")` (ADR-023); top-3 contribution extraction with
      human-readable feature labels (DS-CUST-004)
- [x] T008 `packages/analytics/tests/test_lead_scoring.py`: feature-engineering correctness,
      temporal-split no-leakage (a lead created after the cutoff never appears in the training
      fold), top-3 contribution extraction against a hand-computed fixture; added a mypy override
      for `sklearn.*` (no py.typed marker), matching the project's established pattern
- [x] T009 `apps/api/src/dealeriq_api/domain/lead_scoring_job.py`: orchestration —
      `AnalyticsRun` RUNNING → load customers/orders/leads/lead-events frames → RFM pass → lead-
      scoring pass (consumes this run's own RFM output) → PSI drift check against this run's own
      train-vs-score populations (ADR-023) → open `lead_score_drift` warning alert via
      `evaluate_lead_score_drift()` if any monitored feature's PSI > 0.25 → persist
      `CustomerRfmProfile`/`LeadScore` rows → SUCCEEDED/FAILED, following FR-072's
      concurrency-guard pattern; raises a clear error (DS-OPS-002 failed-run path) if too few
      resolved leads exist to train on. `interaction_count` is bounded to a lead's first 21 days
      (`INTERACTION_COUNT_WINDOW_DAYS`) — a real leakage bug found and fixed while validating
      against the real database: an unbounded `LeadEvent` count is mechanically downstream of
      Phase 3's funnel-walk outcome-dependent branching, not a real engagement signal (ADR-023).
      Verified end-to-end against the real dev database (230 open leads scored, ROC-AUC 0.889,
      Brier 0.129, well-calibrated deciles, zero spurious drift alerts).
- [x] T010 Integration test `apps/api/tests/integration/test_lead_scoring_job.py`: trigger
      succeeds and persists real `CustomerRfmProfile`/`LeadScore` rows for hand-constructed
      fixtures (a repeat-buyer customer gets a non-"New" segment; an open lead gets a
      probability + top-3 explanation); FR-072 concurrency guard; job-raises → FAILED not stuck
      RUNNING. The scientific-validation gate itself (ROC-AUC/PR-AUC/Brier vs. the achievable
      ceiling, sign recovery) is `test_qa003c_lead_model_sign_recovery.py` (CI-blocking, run
      before the model is trusted anywhere in the pipeline, constitution Principle V) — the
      too-few-resolved-leads failure path is already covered at the pure-function level
      (`test_lead_scoring.py`) and can't be reliably re-triggered once dozens of other test
      files share the session-scoped container (ADR-013). The PSI drift alert's firing behavior
      is verified directly via `evaluate_lead_score_drift` in `test_alert_rules.py` (T012) — PSI's
      own numerical correctness (engineered shift vs. unchanged) is already covered by
      `test_psi.py`'s hand-computed fixtures.
- [x] T011 `apps/api/src/dealeriq_api/domain/alert_rules.py` MODIFIED: `evaluate_lead_idle` reads
      `rule.params.get("score_cutoff")`; when non-null, additionally requires the idle lead's
      latest `LeadScore.conversion_probability >= score_cutoff` (SRS's literal "score above
      cutoff" — a promising lead going quiet); unchanged, idle-days-only behavior when null
      (no regression for Phase 6's shipped default)
- [x] T012 Integration test `apps/api/tests/integration/test_alert_rules.py` MODIFIED: a
      high-score idle lead fires with a configured cutoff, a low-score idle lead doesn't (null
      cutoff's unchanged behavior is covered by the pre-existing Phase 6 test in the same file,
      re-verified passing); `evaluate_lead_score_drift` opens an alert when given non-empty
      drifted features and stays silent when given none. Full `apps/api/tests/integration/`
      suite (68 tests) re-run together — no cross-test pollution.
- [x] T013 `apps/api/src/dealeriq_api/routes/leads.py` +
      `apps/api/src/dealeriq_api/schemas/leads.py` MODIFIED: batch-joins the latest succeeded
      run's `LeadScore`/`CustomerRfmProfile` rows to populate
      `LeadResponse.conversion_probability`/`rfm_segment`/`top_features` (new
      `FeatureContributionResponse` schema); unscored leads keep the existing `None`/"not yet
      scored" behavior
- [x] T014 `apps/api/src/dealeriq_api/routes/customers.py` MODIFIED +
      `apps/api/src/dealeriq_api/schemas/customers.py` MODIFIED: `GET /customers/{id}` — RFM
      segment membership (from the latest `CustomerRfmProfile`) + full order/purchase history
      (FR-033), reusing the existing `customers:view` permission
- [x] T015 Integration tests `test_customer_analytics_endpoints.py` (5 tests): a scored lead's
      list-row shows probability/segment/top-3 features; an unscored lead shows null/empty; a
      customer detail response shows the correct segment and order history for both a repeat
      customer and a zero-order customer; 404 for an unknown customer
- [x] T016 `apps/api/src/dealeriq_api/jobs/lead_scoring.py`: `job_name="lead_scoring"` registry
      entry, added to `routes/jobs.py`'s `KNOWN_JOBS` (mirrors forecast/inventory/alerts/digest's
      exact pattern — no new route code needed)
- [x] T017 `apps/api/src/dealeriq_api/core/scheduler.py` MODIFIED: adds the DS-OPS-001 04:00
      daily `lead_scoring` cron registration alongside Phase 6's four existing jobs
- [ ] T018 Regenerate `packages/api-client` against the new/modified endpoints
- [ ] T019 `apps/web/app/(authenticated)/customers/[id]/page.tsx` (NEW): RFM segment badge +
      purchase-history table, following the leads/inventory pages' Card/Badge/table conventions
- [ ] T020 `apps/web/app/(authenticated)/customers/page.tsx` MODIFIED: link each row to its new
      detail page
- [ ] T021 `apps/web/app/(authenticated)/leads/page.tsx` MODIFIED: expandable explanation panel
      (top-3 contributing features) per scored lead row; render the `rfm_segment` field
- [ ] T022 Verify SC-001 directly against the real seeded database: hand-pick a known high-value
      repeat customer and a known dormant/zero-order customer, confirm their segments are correct
      and distinguishable
- [ ] T023 Verify SC-002/SC-003 directly against the real seeded database: every open lead has a
      probability + top-3 explanation with no stale/fabricated scores; score-decile actual-win-
      rate tracking confirms calibration (the phase's principal scientific-validation gate)
- [ ] T024 Verify SC-004 directly against the real seeded database: configure a non-null
      `score_cutoff`, confirm only qualifying idle leads' alerts open
- [ ] T025 Verify SC-005: a deliberately drifted scoring population opens the drift alert; an
      undrifted one does not
- [ ] T026 Verify SC-006 (the phase's own exit demo) in a real browser: open the leads list,
      confirm calibrated scores with visible explanations render with zero manual steps beyond
      the initial job trigger
- [ ] T027 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
