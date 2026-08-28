"""NB-GLM demand generator (GEN-001, GEN-002) - determinism and SBC-class-coverage tests
(spec.md SC-002, SC-005)."""

from collections import Counter

import numpy as np

from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import generate_demand
from dealeriq_analytics.sbc import DegenerateSeriesError, classify_with_stats

MIN_SERIES_PER_CLASS = 10


def _classify_all(series_by_key: dict[tuple[str, str], np.ndarray]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for series in series_by_key.values():
        try:
            sbc_class, _adi, _cv2 = classify_with_stats(series.astype(np.float64))
            counts[sbc_class.value] += 1
        except DegenerateSeriesError:
            counts["degenerate"] += 1
    return counts


def test_generate_demand_is_deterministic_given_a_seed() -> None:
    config = GeneratorConfig()
    first = generate_demand(config)
    second = generate_demand(config)

    assert first.model_defs == second.model_defs
    assert first.series_params == second.series_params
    assert first.series.keys() == second.series.keys()
    for key in first.series:
        assert np.array_equal(first.series[key], second.series[key])


def test_generate_demand_differs_across_seeds() -> None:
    first = generate_demand(GeneratorConfig(seed=42))
    second = generate_demand(GeneratorConfig(seed=43))

    assert first.model_defs != second.model_defs
    any_series_differs = any(
        not np.array_equal(first.series[key], second.series[key])
        for key in first.series
        if key in second.series
    )
    assert any_series_differs


def test_generator_sbc_coverage() -> None:
    """SC-002: the default (seed=42) config must produce >= 10 series in each of the four SBC
    classes - see docs/adr/021-synthetic-demand-volume-vs-sbc-coverage.md for why the model
    counts and mu0 ranges in config.py look the way they do."""
    demand = generate_demand(GeneratorConfig())
    counts = _classify_all(demand.series)

    for sbc_class in ("smooth", "erratic", "intermittent", "lumpy"):
        assert counts[sbc_class] >= MIN_SERIES_PER_CLASS, (
            f"expected >= {MIN_SERIES_PER_CLASS} '{sbc_class}' series, got {counts[sbc_class]} "
            f"(full breakdown: {dict(counts)})"
        )


def test_generate_demand_series_values_are_nonnegative_integers() -> None:
    demand = generate_demand(GeneratorConfig())
    for series in demand.series.values():
        assert series.dtype == np.int64
        assert bool(np.all(series >= 0))
