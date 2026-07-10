# Implementation Plan: Customer Analytics

**Branch**: `008-customer-analytics-rfm` | **Date**: 2026-07-11 | **Spec**: `specs/008-customer-analytics-rfm/spec.md`

## Summary

A `packages/analytics/dealeriq_analytics/customer/` module (RFM quintile segmentation + a
calibrated logistic-regression lead-conversion model with per-lead top-3 explanations and PSI
drift monitoring), a `lead_scoring_job.py` orchestrating it against the real seeded database
following Phase 4/5/6's exact `AnalyticsRun` lifecycle pattern, completion of Phase 6's deferred
`lead_idle` score-cutoff filter, and new UI surfaces: a from-scratch customer detail page
(RFM segment + purchase history) and an explanation panel added to the existing leads list.

## Technical Context

**Language/Version**: Python 3.12 (`apps/api`, `packages/analytics`), TypeScript/Next.js 15
(`apps/web`) — unchanged.

**Primary Dependencies**: `scikit-learn` (already a dependency since Phase 5's classifier work —
`LogisticRegression`, `CalibratedClassifierCV`, `roc_auc_score`/`average_precision_score`/
`brier_score_loss` from `sklearn.metrics`) — no new package. PSI is small enough to hand-implement
in `packages/analytics` (a binned-distribution divergence sum), following the same "hand-implement
small, well-defined statistical primitives with a unit-tested fixture" precedent as Phase 5's
GESD test (ADR-017).

**Storage**: PostgreSQL 16, two new tables (`customer_rfm_profiles`, `lead_scores`) per one new
Alembic migration — both `run_id`-tagged per the established `AnalyticsRun` convention (Forecast/
ForecastMetric/InventoryIntel/UnitRisk/Anomaly all follow this shape); no new columns added to the
existing `customers`/`leads` tables, keeping analytics output separated from transactional state
(constitution Principle IV).

**Testing**: pytest for the analytics module (RFM segment-boundary fixtures against ADR-022's
rules; lead-scoring sign-recovery/calibration validated against the real seeded database,
mirroring QA-003(b)'s "validate against real seeded data" precedent from Phase 5) and
testcontainers-python integration tests (ADR-013) for the job orchestration, score-cutoff alert
completion, and new API endpoints.

**Target Platform**: unchanged — Docker Compose local dev, single-instance.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) — no new top-level project.

**Performance Goals**: RFM computation over ~2000 seeded customers and lead-model training/scoring
over ~6000 seeded leads (a small, low-dimensional feature matrix — logistic regression, not a
large ensemble) both complete in low single-digit seconds, consistent with Phase 5's inventory job
performance envelope.

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (this job is on-demand/scheduled, not part of bootstrap/seed). DS-CUST-005's temporal
split must never let a later-created lead's outcome leak into training for an earlier one.

**Scale/Scope**: one new analytics module (`customer/rfm.py`, `customer/lead_scoring.py`,
`customer/psi.py`), two new tables, one new job + on-demand trigger (`job_name="lead_scoring"`),
~3 new/modified API endpoints (customer detail, lead list score/explanation fields, score-cutoff
param), one new frontend page (customer detail) and one modified page (leads list explanation
panel), one new cron registration (DS-OPS-001's 04:00 slot), one modified alert rule
(`evaluate_lead_idle`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: RFM/lead-scoring/PSI logic lives in
  `packages/analytics` as pure, DB-free functions (Phase 4/5's established pattern — unlike
  Phase 6's alert-rule placement, this genuinely is statistical/ML computation over feature
  matrices, not a threshold comparison over already-computed rows); orchestration lives in
  `apps/api`'s domain layer, mirroring `forecast_job.py`/`inventory_job.py`. No new top-level
  package; no new runtime dependency (`scikit-learn` already present).
- **Principle II (Free, Local-First, Zero Paid Services)**: nothing here calls any external
  service — training and scoring both run against the local Postgres.
- **Principle III (Security & RBAC by Default)**: customer detail page reuses the existing
  `customers:view`-class permission already gating the customer list; no new permission keys are
  needed beyond what Phase 2 already established for customers/leads.
- **Principle IV (Migrations & Append-Only Data Integrity)**: `customer_rfm_profiles`/
  `lead_scores` are analytics-run-tagged output tables (DAT-003's analytics-vs-transactional
  separation), not mutations of `customers`/`leads` — matching Forecast/InventoryIntel/Anomaly's
  precedent exactly, never overwriting a transactional row in place.
- **Principle V (Analytics Reproducibility & Scientific Integrity, NON-NEGOTIABLE)**: every
  lead-scoring run is an `AnalyticsRun` with its seed, data-snapshot bounds, and evaluation
  metrics (ROC-AUC, PR-AUC, Brier score) recorded (DS-CUST-003, DS-OPS-002/003); the model is
  validated against real, persisted seeded data before being trusted in the pipeline (this
  phase's own QA gate, same discipline as QA-003(a)/(b)) — no fabricated metrics, ever.
- **Principle VII (Testing bar)**: RFM segment-boundary rules get hand-constructed fixture tests
  (ADR-022's four rules, evaluated in order); the lead-scoring model gets a real-seeded-data
  calibration/discrimination check (this phase's QA gate) plus a hand-constructed PSI fixture
  test (a known, engineered distribution shift must exceed 0.25; an unchanged distribution must
  not) before PSI is wired into the drift-alert pipeline.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/008-customer-analytics-rfm/
├── spec.md
├── plan.md              # this file
└── tasks.md              # Phase 2 output
```

### Source code

```text
packages/analytics/src/dealeriq_analytics/customer/
├── rfm.py                          # quintile scoring + ADR-022's segment-name mapping;
│                                    # pure pandas/dataclasses, no DB imports
├── lead_scoring.py                  # feature engineering (from plain records, not ORM rows),
│                                    # LogisticRegression + CalibratedClassifierCV(isotonic)
│                                    # (ADR-023), temporal train/val split, top-3 contribution
│                                    # extraction (DS-CUST-004)
└── psi.py                            # Population Stability Index — a small, hand-implemented,
                                       # unit-tested primitive (ADR-017's precedent)

apps/api/src/dealeriq_api/
├── domain/models/
│   └── customer_analytics.py       # CustomerRfmProfile, LeadScore SQLAlchemy models
├── domain/
│   ├── lead_scoring_job.py          # orchestration: AnalyticsRun RUNNING -> load
│   │                                # customers/orders/leads frames -> call
│   │                                # dealeriq_analytics.customer functions -> persist
│   │                                # CustomerRfmProfile/LeadScore rows -> run PSI check ->
│   │                                # open lead_score_drift alert if needed -> SUCCEEDED/FAILED
│   └── alert_rules.py                # MODIFIED: evaluate_lead_idle reads rule.params
│                                     # ["score_cutoff"]; when non-null, additionally requires
│                                     # the lead's latest conversion_probability >= cutoff
├── jobs/
│   └── lead_scoring.py                # job_name="lead_scoring" registry entry (mirrors
│                                       # forecast/inventory/alerts/digest's exact pattern)
├── core/
│   └── scheduler.py                    # MODIFIED: adds the DS-OPS-001 04:00 daily
│                                        # lead_scoring cron registration alongside Phase 6's
│                                        # four existing jobs
├── routes/
│   ├── leads.py                        # MODIFIED: joins the latest succeeded run's LeadScore
│   │                                   # row to populate conversion_probability/rfm_segment/
│   │                                   # top_features on LeadResponse
│   └── customers.py                     # NEW: GET /customers/{id} — RFM segment + order
│                                        # (purchase) history
└── schemas/
    ├── leads.py                        # MODIFIED: LeadResponse.top_features: list[FeatureContribution]
    └── customers.py                     # NEW: CustomerDetailResponse

apps/api/tests/integration/
├── test_lead_scoring_job.py             # calibration/discrimination against real seeded data,
│                                         # PSI fixture test, run lifecycle (idempotency,
│                                         # failed-run handling per DS-OPS-002)
└── test_alert_rules.py                   # MODIFIED: adds score-cutoff cases to the existing
                                           # lead_idle tests

packages/analytics/tests/
├── test_rfm.py                           # ADR-022's four segment rules, quintile-boundary
│                                         # edge cases, zero-order "New" case
├── test_lead_scoring.py                   # feature engineering correctness, temporal split
│                                         # correctness (no future leakage), top-3 contribution
│                                         # extraction against a hand-computed fixture
└── test_psi.py                             # PSI formula validated against a hand-computed
                                            # fixture (known bin counts -> known PSI value)

apps/api/alembic/versions/
└── <rev>_customer_analytics.py           # customer_rfm_profiles, lead_scores tables + indices

apps/web/app/(authenticated)/
├── customers/[id]/page.tsx               # NEW: RFM segment badge + purchase history table
└── leads/page.tsx                        # MODIFIED: adds an expandable explanation panel
                                          # (top-3 contributing features) per scored lead row
```

**Structure Decision**: extends the existing three-package monorepo — no new top-level
directories. Unlike Phase 6, this phase's core logic (RFM, lead scoring, PSI) lives in
`packages/analytics`, following Phase 4/5's precedent, since it is genuine DB-free statistical/ML
computation; only orchestration and the score-cutoff alert completion touch `apps/api`.

## RFM segmentation (DS-CUST-001)

Per customer: `recency = (as_of - max(Order.created_at) for that customer's delivered orders)`,
`frequency = count(delivered orders)`, `monetary = sum(negotiated_price for delivered orders)`.
Quintiles (1-5, 5 = best) are computed by ranking the customer population on each dimension per
run (pandas `qcut`-style), independent of any fixed global thresholds — consistent with a quintile
being defined relative to the current population, standard RFM practice. Customers with zero
delivered orders skip quintile scoring entirely and receive the `"New"` segment directly (never a
fabricated 0/undefined quintile). Segment-name mapping follows ADR-022's four ordered rules.

## Lead-conversion scoring (DS-CUST-002..005, FR-032)

Trained fresh each run (ADR-023) on every lead that has reached a terminal `won`/`lost` status by
the run's data-snapshot date, temporally split (earliest ~80% by `created_at` train, most recent
~20% validate — DS-CUST-005). Features, all derived from already-persisted data (no schema
changes to `Lead`/`Customer`):

- **Channel**: one-hot from `Customer.source_channel`.
- **Budget band**: an ordinal encoding over the seed data's fixed set of band strings.
- **Model segment**: one-hot from `VehicleModel.segment` (joined via `Lead.model_id`).
- **Days since creation**: `(as_of - Lead.created_at).days`.
- **Interaction count**: `count(LeadEvent) for that lead_id` — the real, already-available proxy
  for touches (spec.md's Assumptions), not a new persisted concept.
- **Customer RFM**: the customer's own average quintile score from this run's RFM pass — the
  reason RFM (this phase's other half) must compute before lead scoring in the job's own
  pipeline order.
- **Seasonality**: a cyclical (sin/cos) encoding of `Lead.created_at`'s month.

`LogisticRegression(penalty="l2", class_weight="balanced")` wrapped in
`CalibratedClassifierCV(method="isotonic", cv=5)` (ADR-023). Per-run metrics (ROC-AUC, PR-AUC,
Brier score, reliability-curve bins) are written to the run's `metrics` JSON, matching Phase
4/5's exact convention. Top-3 contributions (DS-CUST-004) come from
`|coefficient_i * standardized_feature_value_i|`, sorted descending, rendered with a
human-readable label per feature (e.g. "Referral source", "Budget band: 30k-40k") rather than raw
coefficients.

## Drift monitoring (FR-074)

`packages/analytics/customer/psi.py` computes PSI per monitored feature, comparing this run's own
training-set distribution against this run's own scoring-population (open leads) distribution
(ADR-023 — no cross-run persisted baseline). If any monitored feature's PSI exceeds 0.25, the job
opens a `lead_score_drift` warning-severity alert via Phase 6's existing rule_key-agnostic
`open_alert()` helper — no new alert-lifecycle mechanism, reusing FR-062's machinery as-is.

## Completing `lead_idle`'s score-cutoff (User Story 3)

`evaluate_lead_idle` (unchanged idle-days logic) additionally reads
`rule.params.get("score_cutoff")`; when non-null, it joins each idle lead's latest `LeadScore` row
and only opens the alert when `conversion_probability >= score_cutoff` (the SRS's literal "score
above cutoff" — a promising lead going quiet is the urgent case, not a lead that was never likely
to convert). When `score_cutoff` is null (Phase 6's shipped default), behavior is unchanged from
Phase 6 — no regression for configurations that never touch this param.

## Customer detail page (FR-033)

New route `apps/web/app/(authenticated)/customers/[id]/page.tsx` — no existing template, built
fresh following the leads/inventory pages' Card/Badge/table conventions: an RFM segment badge at
the top, and a purchase-history table (order date, model, negotiated price, status) below,
sourced from the new `GET /customers/{id}` endpoint.

## Validation sequence (proves the phase works end-to-end)

1. Run the RFM pass against real seeded customers; hand-pick a known high-value repeat customer
   and a known dormant/never-purchased customer; confirm their segments are correct and
   distinguishable (SC-001).
2. Run the lead-scoring job; confirm every open lead has a probability and top-3 explanation
   visible via the API/UI, with no stale/fabricated scores (SC-002).
3. Bucket resolved leads by score decile against real seeded data; confirm actual win rate per
   decile tracks predicted probability (SC-003) — the phase's principal scientific-validation
   gate, run before the model is trusted anywhere in the pipeline (constitution Principle V).
4. Configure a non-null `score_cutoff` on `lead_idle`; seed one high-score and one low-score idle
   lead; run alert evaluation; confirm only the high-score lead's alert opens (SC-004).
5. Engineer a deliberate feature-distribution shift in a scoring run; confirm the drift alert
   opens; run an undrifted case; confirm it doesn't (SC-005).
6. Full exit demo: open the leads list in a real browser and confirm calibrated scores with
   visible explanations render with zero manual steps beyond the job trigger (SC-006).
