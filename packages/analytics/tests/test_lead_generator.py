"""Lead funnel simulation (GEN-003) - sign-recovery validation (spec.md SC-003)."""

import numpy as np
from sklearn.linear_model import LogisticRegression

from dealeriq_analytics.generator.leads import (
    ground_truth_coefficients,
    leads_to_design_matrix,
    simulate_leads,
)

N_LEADS = 8000
N_WEEKS = 156


def _fitted_signs() -> tuple[dict[str, float], dict[str, float]]:
    rng = np.random.default_rng(42)
    leads = simulate_leads(N_LEADS, N_WEEKS, rng)
    x, y, feature_names = leads_to_design_matrix(leads)

    model = LogisticRegression(max_iter=1000)
    model.fit(x, y)
    fitted = dict(zip(feature_names, model.coef_[0], strict=True))

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
        "rfm_quintile": coeffs.rfm_quintile,
        "is_peak_season": coeffs.season,
    }
    return fitted, ground_truth


def test_simulate_leads_produces_won_and_lost_outcomes() -> None:
    rng = np.random.default_rng(42)
    leads = simulate_leads(N_LEADS, N_WEEKS, rng)
    won_count = sum(1 for lead in leads if lead.won)

    assert len(leads) == N_LEADS
    assert 0 < won_count < N_LEADS


def test_logistic_regression_recovers_every_ground_truth_coefficient_sign() -> None:
    fitted, ground_truth = _fitted_signs()

    assert fitted.keys() == ground_truth.keys()
    for feature, truth_value in ground_truth.items():
        fitted_value = fitted[feature]
        assert np.sign(fitted_value) == np.sign(truth_value), (
            f"{feature}: ground truth sign {np.sign(truth_value):+.0f}, "
            f"fitted coefficient {fitted_value:+.4f}"
        )


def test_simulate_leads_is_deterministic_given_a_seed() -> None:
    first = simulate_leads(500, N_WEEKS, np.random.default_rng(7))
    second = simulate_leads(500, N_WEEKS, np.random.default_rng(7))

    assert first == second
