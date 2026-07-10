"""Anomaly injection (GEN-004) — independent detectability validation (spec.md SC-004)."""

import numpy as np
from statsmodels.tsa.seasonal import STL

from dealeriq_analytics.generator.anomalies import (
    MODIFIED_Z_CONSTANT,
    NEAR_MISS_Z_MAX,
    NEAR_MISS_Z_MIN,
    STL_PERIOD,
    find_near_miss_points,
    inject_demand_shocks,
)
from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import generate_demand

DETECTION_THRESHOLD_Z = 3.5
N_SHOCKS = 20
N_NEAR_MISS = 5


def _independent_z_score(series: np.ndarray, week_index: int) -> float:
    """Recomputes the robust z-score from scratch on the given (already-injected) series — does
    not reuse any stats from the injection step, so this is a genuine independent check."""
    stl = STL(series.astype(np.float64), period=STL_PERIOD, robust=False)
    residuals = stl.fit().resid
    median_resid = np.median(residuals)
    mad = np.median(np.abs(residuals - median_resid))
    return float(MODIFIED_Z_CONSTANT * (residuals[week_index] - median_resid) / mad)


def test_anomalies_are_independently_detectable() -> None:
    demand = generate_demand(GeneratorConfig())
    rng = np.random.default_rng(42)
    mutated_series, records = inject_demand_shocks(demand, rng, n_shocks=N_SHOCKS)

    assert len(records) == N_SHOCKS

    for record in records:
        model_key, branch_name = record.series_key.split("|")
        series = mutated_series[(model_key, branch_name)]
        z = _independent_z_score(series, record.week_index)

        assert abs(z) >= DETECTION_THRESHOLD_Z, (
            f"{record.series_key} week {record.week_index}: independently recomputed z={z:.2f} "
            f"does not clear the {DETECTION_THRESHOLD_Z} detection threshold "
            f"(injection targeted z={record.implied_z})"
        )
        if record.type == "spike":
            assert z > 0
        else:
            assert z < 0


def test_near_miss_points_stay_below_the_detection_threshold() -> None:
    demand = generate_demand(GeneratorConfig())
    rng = np.random.default_rng(42)
    near_misses = find_near_miss_points(demand, rng, n_near_miss=N_NEAR_MISS)

    assert len(near_misses) == N_NEAR_MISS
    for record in near_misses:
        assert NEAR_MISS_Z_MIN <= abs(record.implied_z) < NEAR_MISS_Z_MAX
        assert abs(record.implied_z) < DETECTION_THRESHOLD_Z


def test_inject_demand_shocks_does_not_mutate_the_original_series() -> None:
    demand = generate_demand(GeneratorConfig())
    original = {key: arr.copy() for key, arr in demand.series.items()}
    rng = np.random.default_rng(42)
    inject_demand_shocks(demand, rng, n_shocks=N_SHOCKS)

    for key, arr in demand.series.items():
        assert np.array_equal(arr, original[key])


def test_inject_demand_shocks_is_deterministic_given_a_seed() -> None:
    demand = generate_demand(GeneratorConfig())
    _, first = inject_demand_shocks(demand, np.random.default_rng(11), n_shocks=N_SHOCKS)
    _, second = inject_demand_shocks(demand, np.random.default_rng(11), n_shocks=N_SHOCKS)

    assert first == second
