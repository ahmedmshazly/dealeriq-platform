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
7. **PSI monitoring is scoped to compositional features only** (`PSI_MONITORED_FEATURES`:
   channel, budget band, model segment, customer RFM) — **not** `days_since_creation`,
   `season_sin`/`season_cos`, or `interaction_count`. Running this pipeline against the real
   seeded database (§ Consequences) showed those four features have permanent, structural PSI
   drift under point 6's design: the training population (resolved leads spanning the full
   history) and the scoring population (currently-open leads, which are inherently recent and
   inherently less "walked" through their funnel) can never be distributionally similar on
   time-since-creation, seasonality, or interaction count, regardless of any real change in
   incoming lead quality — so monitoring them would make the alert fire on every single run,
   which is a false-positive machine, not a useful signal.
8. **`interaction_count` is bounded to events within `INTERACTION_COUNT_WINDOW_DAYS` (21) of a
   lead's creation, not its full lifetime `LeadEvent` count.** Running this pipeline against the
   real seeded database surfaced genuine label leakage: Phase 3's `_walk_lead_funnel` generator
   makes a resolved lead's *total* event count mechanically dependent on its own won/lost outcome
   (a won lead always completes the full state-machine path; a lost lead has a 40% chance of an
   early exit at every step), so an unbounded lifetime count is closer to "how many steps did the
   generator's own branching logic take" than a real engagement signal — using it inflated
   validation ROC-AUC to an implausible ~0.97 (see § Consequences). Bounding the count to a fixed
   early window keeps it to information that would genuinely have been available while a lead was
   still open, for training and scoring alike; ROC-AUC against the real database dropped to a more
   defensible ~0.89 after the fix — some residual advantage over the leakage-free synthetic
   ceiling test (§ Consequences) likely remains from event-spacing correlating with path length,
   disclosed rather than chased further.
9. **`compute_psi` bins a low-cardinality reference (at most 10 distinct values, e.g. a 0/1
   one-hot column) by its exact values, not by quantile edges.** Verifying SC-005 against real
   data (engineering a deliberate channel-composition shift and confirming the drift alert
   fires) surfaced a real bug: quantile-based binning on a binary column makes every quantile
   point land on the same 0 or 1, collapsing to a single `(-inf, +inf)` bin — which silently
   reports zero PSI for a channel-mix shift of *any* size, no matter how extreme. Fixed by
   detecting low-cardinality references and binning by exact value instead (one bin per value
   actually observed, in either population). Continuous features (`budget_level`,
   `customer_rfm_score`) were never affected — only the four one-hot channel/segment columns in
   `PSI_MONITORED_FEATURES` were silently blind to drift before this fix.

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
- **QA-003(c)'s CI-blocking sign-recovery gate is deliberately not run against the real seeded
  database.** `test_qa003c_lead_model_sign_recovery.py` reconstructs a clean synthetic population
  directly from `dealeriq_analytics.generator.leads.simulate_leads` (the exact ground-truth
  logit, feeding the model's own `interaction_count`/`days_since_creation` draws directly rather
  than the real database's derived proxies), giving a known theoretical ceiling to test against
  (the AUC achievable using the simulator's own true `p_won` values, ~0.68 for this seed) — the
  real database's own `LeadEvent`-derived features remain proxies with real-world-typical noise
  and residual structure (point 8), appropriate for the phase report's real-data validation
  narrative but not a fair "did the model architecture correctly recover a known signal" gate.
