"""Champion selection (DS-FC-006) - the Seasonal-Naive-floor invariant and tie-breaking, tested
directly against hand-built MethodMetrics (no statsforecast/CV dependency needed here)."""

import pytest

from dealeriq_analytics.forecasting.champion import MethodMetrics, select_champion
from dealeriq_analytics.forecasting.methods import SEASONAL_NAIVE_ALIAS


def _metrics(mase_value: float, n_folds: int = 24) -> MethodMetrics:
    return MethodMetrics(
        mase=mase_value,
        smape=0.0,
        pinball_q10=0.0,
        pinball_q50=0.0,
        pinball_q90=0.0,
        coverage80=0.8,
        n_folds=n_folds,
    )


def test_champion_is_the_lowest_mase_method_when_it_beats_seasonal_naive() -> None:
    metrics = {
        SEASONAL_NAIVE_ALIAS: _metrics(2.0),
        "AutoETS": _metrics(1.2),
        "Naive": _metrics(3.0),
    }
    assert select_champion(metrics) == "AutoETS"


def test_seasonal_naive_wins_when_nothing_beats_it() -> None:
    metrics = {
        SEASONAL_NAIVE_ALIAS: _metrics(1.0),
        "AutoETS": _metrics(1.5),
        "AutoARIMA": _metrics(2.0),
    }
    assert select_champion(metrics) == SEASONAL_NAIVE_ALIAS


def test_exact_tie_against_seasonal_naive_resolves_to_seasonal_naive() -> None:
    metrics = {
        SEASONAL_NAIVE_ALIAS: _metrics(1.0),
        "AutoETS": _metrics(1.0),
    }
    assert select_champion(metrics) == SEASONAL_NAIVE_ALIAS


def test_method_with_no_valid_folds_is_never_champion() -> None:
    # AutoARIMA isn't even in the dict (every fold failed to converge for this series);
    # champion selection must not crash or accidentally prefer it.
    metrics = {
        SEASONAL_NAIVE_ALIAS: _metrics(1.0),
        "Naive": _metrics(5.0),
    }
    assert select_champion(metrics) == SEASONAL_NAIVE_ALIAS


def test_missing_seasonal_naive_raises_rather_than_silently_picking_a_champion() -> None:
    metrics = {"AutoETS": _metrics(1.0)}
    with pytest.raises(ValueError, match="Seasonal Naive"):
        select_champion(metrics)
