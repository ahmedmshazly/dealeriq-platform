"""QA-003(c) — CI-blocking scientific validation, per the constitution's Phase 4+ mandate (the
same standing QA-003(a)/(b) got in Phases 4/5): "lead-model recovers sign of ground-truth
coefficients."

Phase 3's own `test_lead_generator.py` already validates that a plain `LogisticRegression` fit
directly on the simulator's design matrix (`leads_to_design_matrix`) recovers every ground-truth
coefficient's sign — a check on the *simulator's* validity. This test extends the same check to
Phase 7's actual deployed pipeline: `build_feature_matrix` + standardization + the calibrated
`LogisticRegression`/`CalibratedClassifierCV` combination `train_and_score` really uses
(DS-CUST-002/003), not just the simulator's self-check.

Feature mapping from `SimulatedLead` to `LeadFeatureRow` uses the simulator's own
`days_since_creation`/`interaction_count`/`rfm_quintile` values directly (via a constructed
`created_at` and `customer_rfm_score`), not a DB-realized proxy — this test validates the *model
architecture's* ability to recover a known signal from data shaped like the ground truth, not the
real database's specific feature-realization choices (those are exercised by
`test_lead_scoring.py`'s unit tests and validated against the real seeded database, documented in
the Phase 7 report — DS-ANO-003 in Phase 5 drew the same real-database-only line for its
transaction-level detector rather than building a second in-memory reproduction).

`season_sin`/`season_cos` (continuous, month-based) has no ground-truth sign to check against —
the simulator's own seasonality signal is a binary `is_peak_season` flag on a different cadence
(week-of-year buckets), not a continuous month cycle, so the two aren't directly comparable
coefficient-for-coefficient. Every other feature has a direct, checkable ground-truth sign.

Discrimination/calibration are graded relative to two baselines computed from the *same* held-out
validation split, not fixed literals — a hardcoded AUC target is either too strict for a weak
ground-truth signal or too loose for a strong one, while "how close to the achievable ceiling" and
"better than predicting the base rate" are meaningful regardless of exactly how separable this
particular seeded population turns out to be:
  - **Ceiling ROC-AUC**: the AUC obtained by ranking on the simulator's own true `p_won` — the
    best any model could ever do on this exact validation split, since `p_won` is the literal
    probability the outcomes were drawn from.
  - **Naive Brier score**: the score of a model that always predicts the population's mean win
    rate — the naive floor a real, feature-driven model has to beat.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score

from dealeriq_analytics.customer.lead_scoring import (
    LeadFeatureRow,
    LeadScoringResult,
    temporal_split,
    train_and_score,
)
from dealeriq_analytics.generator.leads import (
    SimulatedLead,
    ground_truth_coefficients,
    simulate_leads,
)

N_LEADS = 6000
N_WEEKS = 156
SEED = 20260711
REFERENCE_DATE = datetime(2026, 7, 6, tzinfo=UTC)

MIN_FRACTION_OF_CEILING_AUC = 0.85
MAX_FRACTION_OF_NAIVE_BRIER = 0.97


def _to_feature_row(lead: SimulatedLead) -> LeadFeatureRow:
    created_at = REFERENCE_DATE - timedelta(days=lead.days_since_creation)
    return LeadFeatureRow(
        lead_id=lead.lead_key,
        channel=lead.channel,
        budget_band=lead.budget_band,
        model_segment=lead.segment,
        created_at=created_at,
        interaction_count=lead.interaction_count,
        customer_rfm_score=float(lead.rfm_quintile),
        won=lead.won,
    )


def _fit_against_ground_truth() -> tuple[LeadScoringResult, dict[str, float]]:
    rng = np.random.default_rng(SEED)
    simulated = simulate_leads(N_LEADS, N_WEEKS, rng)
    rows = [_to_feature_row(lead) for lead in simulated]

    result = train_and_score(rows, [], as_of=REFERENCE_DATE, train_fraction=0.8)

    coeffs = ground_truth_coefficients()
    ground_truth = {
        "channel__referral": coeffs.channel["referral"],
        "channel__walk_in": coeffs.channel["walk_in"],
        "channel__phone": coeffs.channel["phone"],
        "channel__social_ad": coeffs.channel["social_ad"],
        "budget_level": coeffs.budget_per_level,
        "segment__economy": coeffs.segment["economy"],
        "segment__sedan": coeffs.segment["sedan"],
        "segment__suv_truck": coeffs.segment["suv_truck"],
        "segment__commercial": coeffs.segment["commercial"],
        "days_since_creation": coeffs.days_since_creation,
        "interaction_count": coeffs.interaction_count,
        "customer_rfm_score": coeffs.rfm_quintile,
    }
    return result, ground_truth


def test_lead_model_recovers_every_ground_truth_coefficient_sign() -> None:
    result, ground_truth = _fit_against_ground_truth()
    fitted = result.explain_coefficients

    for feature, truth_value in ground_truth.items():
        assert feature in fitted, f"{feature} missing from the fitted model's feature set"
        fitted_value = fitted[feature]
        assert np.sign(fitted_value) == np.sign(truth_value), (
            f"{feature}: ground truth sign {np.sign(truth_value):+.0f}, "
            f"fitted coefficient {fitted_value:+.4f}"
        )


def test_lead_model_discriminates_near_the_achievable_ceiling_and_beats_the_naive_baseline() -> (
    None
):
    rng = np.random.default_rng(SEED)
    simulated = simulate_leads(N_LEADS, N_WEEKS, rng)
    rows = [_to_feature_row(lead) for lead in simulated]
    result = train_and_score(rows, [], as_of=REFERENCE_DATE, train_fraction=0.8)

    _train_rows, val_rows = temporal_split(rows, train_fraction=0.8)
    p_won_by_key = {lead.lead_key: lead.p_won for lead in simulated}
    y_val = np.array([1 if r.won else 0 for r in val_rows])
    p_val = np.array([p_won_by_key[r.lead_id] for r in val_rows])

    ceiling_auc = roc_auc_score(y_val, p_val)
    naive_brier = brier_score_loss(y_val, np.full_like(p_val, y_val.mean()))

    min_auc = MIN_FRACTION_OF_CEILING_AUC * ceiling_auc
    assert result.metrics.roc_auc >= min_auc, (
        f"ROC-AUC {result.metrics.roc_auc:.3f} is below {min_auc:.3f} "
        f"({MIN_FRACTION_OF_CEILING_AUC:.0%} of the {ceiling_auc:.3f} ceiling achievable using "
        "the simulator's own true p_won on this validation split)."
    )

    max_brier = MAX_FRACTION_OF_NAIVE_BRIER * naive_brier
    assert result.metrics.brier_score <= max_brier, (
        f"Brier score {result.metrics.brier_score:.3f} does not beat the naive "
        f"predict-the-base-rate baseline ({naive_brier:.3f}) by the required margin."
    )
