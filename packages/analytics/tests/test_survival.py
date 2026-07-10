from datetime import date

from dealeriq_analytics.inventory.survival import (
    TimeToSaleObservation,
    days_on_lot,
    fit_survival_curve,
    is_aging,
    sale_probability_within,
    worst_decile_threshold,
)


def test_days_on_lot_hand_computed() -> None:
    assert days_on_lot(date(2026, 1, 1), date(2026, 1, 11)) == 10


def test_is_aging_threshold_boundary_is_inclusive() -> None:
    assert is_aging(90, threshold_days=90) is True
    assert is_aging(89, threshold_days=90) is False


def test_kaplan_meier_hand_computed_survival_function() -> None:
    # 5 units, durations [5,10,15,20,25], events [T,T,F,T,F] (same toy dataset used to sanity
    # -check lifelines' own API): standard KM step calculation —
    #   S(0)=1
    #   at t=5: 1 death out of 5 at risk -> S(5) = 1 * (4/5) = 0.8
    #   at t=10: 1 death out of 4 at risk -> S(10) = 0.8 * (3/4) = 0.6
    #   at t=15: censored, no death -> S(15) = 0.6 (unchanged)
    #   at t=20: 1 death out of 2 at risk -> S(20) = 0.6 * (1/2) = 0.3
    #   at t=25: censored -> S(25) = 0.3 (unchanged)
    observations = [
        TimeToSaleObservation(unit_id="a", duration_days=5, sold=True),
        TimeToSaleObservation(unit_id="b", duration_days=10, sold=True),
        TimeToSaleObservation(unit_id="c", duration_days=15, sold=False),
        TimeToSaleObservation(unit_id="d", duration_days=20, sold=True),
        TimeToSaleObservation(unit_id="e", duration_days=25, sold=False),
    ]
    kmf = fit_survival_curve(observations)
    assert abs(float(kmf.predict(5)) - 0.8) < 1e-9
    assert abs(float(kmf.predict(10)) - 0.6) < 1e-9
    assert abs(float(kmf.predict(15)) - 0.6) < 1e-9
    assert abs(float(kmf.predict(20)) - 0.3) < 1e-9


def test_sale_probability_within_hand_computed() -> None:
    observations = [
        TimeToSaleObservation(unit_id="a", duration_days=5, sold=True),
        TimeToSaleObservation(unit_id="b", duration_days=10, sold=True),
        TimeToSaleObservation(unit_id="c", duration_days=15, sold=False),
        TimeToSaleObservation(unit_id="d", duration_days=20, sold=True),
        TimeToSaleObservation(unit_id="e", duration_days=25, sold=False),
    ]
    kmf = fit_survival_curve(observations)
    # conditional prob of selling in [10,20] given survival to 10: 1 - S(20)/S(10) = 1-0.3/0.6 = 0.5
    prob = sale_probability_within(kmf, current_age_days=10, horizon_days=10)
    assert abs(prob - 0.5) < 1e-9


def test_sale_probability_is_zero_when_survival_already_zero() -> None:
    observations = [
        TimeToSaleObservation(unit_id="a", duration_days=5, sold=True),
        TimeToSaleObservation(unit_id="b", duration_days=10, sold=True),
    ]
    kmf = fit_survival_curve(observations)
    # S(10) = 0 (both units sold by day 10) -> conditional probability undefined -> 0.0
    prob = sale_probability_within(kmf, current_age_days=10, horizon_days=30)
    assert prob == 0.0


def test_worst_decile_threshold_hand_computed() -> None:
    probs = [float(i) for i in range(1, 101)]  # 1..100
    threshold = worst_decile_threshold(probs)
    assert abs(threshold - 10.9) < 0.5  # numpy's linear-interpolation 10th percentile of 1..100
