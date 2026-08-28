"""QA-003(a) - CI-blocking scientific validation, per the constitution's Phase 4+ mandate:
champion methods must beat Seasonal Naive on >=60% of intermittent-class series.

Runs the full DS-FC-003..007 pipeline (all 8 methods x rolling-origin CV) against Phase 3's real
generator output (in-memory, seed=42 - the same 66 series the actual seeded database gets,
without the DB/HTTP round-trip). This is a genuinely slow test (~10-15 minutes: the CV harness's
own compute cost dominates, not I/O) - deliberately kept in the default suite rather than a
separate "nightly" tier, since the constitution's own language ("CI fails if these regress") is
specific about QA-003 being a blocking gate from this phase forward, not an optional extra.
"""

import pandas as pd

from dealeriq_analytics.forecasting.champion import run_forecast_pipeline
from dealeriq_analytics.forecasting.methods import SEASONAL_NAIVE_ALIAS
from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import generate_demand
from dealeriq_analytics.sbc import DegenerateSeriesError, classify_with_stats

MIN_INTERMITTENT_WIN_RATE = 0.60
WEEK_START = pd.Timestamp("2023-07-17")


def test_champion_beats_seasonal_naive_on_at_least_60_percent_of_intermittent_series() -> None:
    demand = generate_demand(GeneratorConfig())

    pattern_class_by_key: dict[tuple[str, str], str] = {}
    weekly_series: dict[tuple[str, str], pd.Series] = {}
    for key, series in demand.series.items():
        float_series = series.astype(float)
        try:
            sbc_class, _adi, _cv2 = classify_with_stats(float_series)
            pattern_class_by_key[key] = sbc_class.value
        except DegenerateSeriesError:
            pattern_class_by_key[key] = "degenerate"
        calendar = pd.date_range(WEEK_START, periods=len(float_series), freq="W-MON")
        weekly_series[key] = pd.Series(float_series, index=calendar)

    results = run_forecast_pipeline(weekly_series)

    intermittent_keys = [k for k, pc in pattern_class_by_key.items() if pc == "intermittent"]
    assert len(intermittent_keys) >= 10  # SC-002, already covered by test_demand_generator.py

    wins = 0
    for key in intermittent_keys:
        result = results[key]
        champion_mase = result.metrics_by_method[result.champion_method].mase
        naive_mase = result.metrics_by_method[SEASONAL_NAIVE_ALIAS].mase
        if champion_mase < naive_mase:
            wins += 1

    win_rate = wins / len(intermittent_keys)
    assert win_rate >= MIN_INTERMITTENT_WIN_RATE, (
        f"Champion beat Seasonal Naive on only {wins}/{len(intermittent_keys)} "
        f"({win_rate:.1%}) intermittent series — QA-003(a) requires >=60%."
    )
