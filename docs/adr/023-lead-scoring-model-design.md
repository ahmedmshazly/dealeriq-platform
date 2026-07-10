# ADR-023: Lead-scoring model — isotonic calibration, retrain-fresh-per-run, inline drift check

- Status: Accepted
- Date: 2026-07-11
- Requirement refs: DS-CUST-002, DS-CUST-003, DS-CUST-005, FR-074

## Context

DS-CUST-003 requires a calibrated L2-regularized logistic-regression baseline (Platt or isotonic
calibration — the SRS doesn't pick one) and permits, but doesn't require, a gradient-boosted
challenger. DS-CUST-005 requires a temporal train/validation split and class-imbalance handling
via weights, not resampling. FR-074 requires PSI-based drift monitoring but doesn't specify what
the drift "reference" distribution is relative to, since no earlier phase persists a trained
model artifact across runs.

## Decision

1. **Calibration method: isotonic regression** (`sklearn.calibration.CalibratedClassifierCV(...,
   method="isotonic")`), not Platt/sigmoid. Isotonic is the better choice once the calibration set
   is reasonably large (conventionally >~1000 samples) since it makes no parametric assumption
   about the miscalibration shape; the seeded dataset's ~6000 leads comfortably clears that bar.
2. **Class imbalance via `class_weight="balanced"`** on the `LogisticRegression` estimator — never
   via oversampling/undersampling the training or validation set (DS-CUST-005's literal
   requirement).
3. **Temporal split**: leads are ordered by `created_at`; the earliest ~80% (by count, among
   leads that have reached a terminal `won`/`lost` status) form the training set, the most recent
   ~20% form the validation set used for DS-CUST-003's reported ROC-AUC/PR-AUC/calibration
   metrics. No shuffling.
4. **The gradient-boosted (`HistGradientBoostingClassifier`) challenger is deferred to
   `docs/backlog.md`** — DS-CUST-003 says it "MAY be promoted," making it explicitly optional; the
   logistic-regression baseline alone satisfies every P0 requirement in this phase's scope.
5. **No trained model artifact is persisted between job runs.** Consistent with Phase 4/5's
   convention of full recomputation per `AnalyticsRun` (no persisted forecast-model binaries
   either), the lead-scoring job retrains a fresh model from all currently-resolved leads on every
   run, then scores all currently-open leads with it. This avoids introducing new
   model-serialization infrastructure (pickling, versioned artifact storage) for a training cost
   that's cheap at this data scale.
6. **FR-074's drift reference is this run's own training-set feature distribution**, compared via
   Population Stability Index against this run's own scoring-population (open leads) feature
   distribution — not a distribution frozen at some earlier "deployment" time, since no earlier
   time's distribution is persisted anywhere (per point 5). A `lead_score_drift` warning alert
   opens (reusing Phase 6's rule_key-agnostic `open_alert()` machinery) when any monitored
   feature's PSI exceeds 0.25.

## Consequences

- Isotonic calibration is a real, standard choice appropriate to the dataset size, not an
  arbitrary pick — documented here so a future phase revisiting calibration with less data
  (e.g. a single dealership's real production volume) knows to reconsider Platt scaling instead.
- Retraining fresh every run means "drift" is measured run-over-run as train-vs-score population
  divergence within a single run, not model-staleness in the traditional sense (comparing to a
  fixed historical deployment baseline) — a deliberate, disclosed simplification consistent with
  this project's broader choice not to persist model binaries across runs.
- The GBM challenger's deferral is recorded in `docs/backlog.md` as a P1 item, not silently
  dropped.
