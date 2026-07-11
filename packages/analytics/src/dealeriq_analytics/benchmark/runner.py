"""Runs the existing, already-validated generate -> classify -> CV -> champion pipeline
(unchanged) across every seed in a BenchmarkConfig. The conversion from the generator's raw
integer arrays to weekly pd.Series is the exact pattern already proven in
test_qa003a_scientific_validation.py -- this module doesn't introduce a new one."""

import dataclasses

import pandas as pd

from dealeriq_analytics.benchmark.config import BenchmarkConfig
from dealeriq_analytics.forecasting.champion import run_forecast_pipeline
from dealeriq_analytics.forecasting.methods import SEASONAL_NAIVE_ALIAS
from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import generate_demand
from dealeriq_analytics.sbc import DegenerateSeriesError, classify_with_stats

DEGENERATE_CLASS = "degenerate"


@dataclasses.dataclass(frozen=True)
class PerSeriesResult:
    dataset_seed: int
    series_key: str
    sbc_class: str
    method: str
    mase: float
    smape: float
    pinball_q10: float
    pinball_q50: float
    pinball_q90: float
    coverage80: float
    is_champion: bool
    is_seasonal_naive: bool


def _series_key_str(key: tuple[str, ...]) -> str:
    return "::".join(key)


def run_benchmark(config: BenchmarkConfig) -> list[PerSeriesResult]:
    results: list[PerSeriesResult] = []
    for seed in config.seeds():
        demand = generate_demand(GeneratorConfig(seed=seed))

        sbc_class_by_key: dict[tuple[str, ...], str] = {}
        weekly_series: dict[tuple[str, ...], pd.Series] = {}
        for key, series in demand.series.items():
            float_series = series.astype(float)
            try:
                sbc_class, _adi, _cv2 = classify_with_stats(float_series)
                sbc_class_by_key[key] = sbc_class.value
            except DegenerateSeriesError:
                sbc_class_by_key[key] = DEGENERATE_CLASS
            calendar = pd.date_range(config.week_start, periods=len(float_series), freq="W-MON")
            weekly_series[key] = pd.Series(float_series, index=calendar)

        pipeline_results = run_forecast_pipeline(weekly_series)

        for series_key_tuple, series_result in pipeline_results.items():
            for method, metrics in series_result.metrics_by_method.items():
                results.append(
                    PerSeriesResult(
                        dataset_seed=seed,
                        series_key=_series_key_str(series_key_tuple),
                        sbc_class=sbc_class_by_key[series_key_tuple],
                        method=method,
                        mase=metrics.mase,
                        smape=metrics.smape,
                        pinball_q10=metrics.pinball_q10,
                        pinball_q50=metrics.pinball_q50,
                        pinball_q90=metrics.pinball_q90,
                        coverage80=metrics.coverage80,
                        is_champion=(method == series_result.champion_method),
                        is_seasonal_naive=(method == SEASONAL_NAIVE_ALIAS),
                    )
                )
    return results
