"""Aggregates PerSeriesResult rows into a per-(sbc_class, method) leaderboard and a paired
Wilcoxon signed-rank comparison (champion vs. Seasonal Naive MASE, paired by series) per SBC
class and overall. `degenerate`-classified series are counted but excluded from both, reported
honestly rather than silently folded into a real demand-pattern class."""

import dataclasses
import statistics

from scipy import stats

from dealeriq_analytics.benchmark.runner import DEGENERATE_CLASS, PerSeriesResult
from dealeriq_analytics.sbc import SbcClass

REAL_CLASSES = [c.value for c in SbcClass]
OVERALL_LABEL = "overall"


@dataclasses.dataclass(frozen=True)
class MethodClassSummary:
    sbc_class: str
    method: str
    n_series: int
    mean_mase: float
    mean_smape: float
    mean_pinball_q10: float
    mean_pinball_q50: float
    mean_pinball_q90: float
    mean_coverage80: float


@dataclasses.dataclass(frozen=True)
class WilcoxonResult:
    sbc_class: str  # one of REAL_CLASSES, or OVERALL_LABEL for the pooled test
    n_pairs: int
    statistic: float | None
    p_value: float | None
    champion_win_rate: float  # fraction of series where champion MASE < Seasonal Naive MASE


@dataclasses.dataclass(frozen=True)
class LeaderboardResult:
    method_class_summaries: list[MethodClassSummary]
    wilcoxon_results: list[WilcoxonResult]
    n_total_series: int
    n_degenerate_series: int


def _mean(values: list[float]) -> float:
    return statistics.fmean(values)


def _build_method_class_summaries(results: list[PerSeriesResult]) -> list[MethodClassSummary]:
    groups: dict[tuple[str, str], list[PerSeriesResult]] = {}
    for r in results:
        if r.sbc_class == DEGENERATE_CLASS:
            continue
        groups.setdefault((r.sbc_class, r.method), []).append(r)

    summaries = []
    for (sbc_class, method), rows in sorted(groups.items()):
        summaries.append(
            MethodClassSummary(
                sbc_class=sbc_class,
                method=method,
                n_series=len(rows),
                mean_mase=_mean([r.mase for r in rows]),
                mean_smape=_mean([r.smape for r in rows]),
                mean_pinball_q10=_mean([r.pinball_q10 for r in rows]),
                mean_pinball_q50=_mean([r.pinball_q50 for r in rows]),
                mean_pinball_q90=_mean([r.pinball_q90 for r in rows]),
                mean_coverage80=_mean([r.coverage80 for r in rows]),
            )
        )
    return summaries


def _paired_champion_vs_seasonal_naive(
    results: list[PerSeriesResult],
) -> dict[tuple[int, str, str], tuple[float, float]]:
    """(dataset_seed, series_key, sbc_class) -> (champion_mase, seasonal_naive_mase), one pair
    per series, the atomic unit the Wilcoxon test and the win-rate are both built from."""
    champion_mase: dict[tuple[int, str, str], float] = {}
    seasonal_naive_mase: dict[tuple[int, str, str], float] = {}
    for r in results:
        if r.sbc_class == DEGENERATE_CLASS:
            continue
        series_id = (r.dataset_seed, r.series_key, r.sbc_class)
        if r.is_champion:
            champion_mase[series_id] = r.mase
        if r.is_seasonal_naive:
            seasonal_naive_mase[series_id] = r.mase

    return {
        series_id: (champion_mase[series_id], seasonal_naive_mase[series_id])
        for series_id in champion_mase
        if series_id in seasonal_naive_mase
    }


def _wilcoxon_for_pairs(sbc_class: str, pairs: list[tuple[float, float]]) -> WilcoxonResult:
    n_pairs = len(pairs)
    if n_pairs == 0:
        return WilcoxonResult(sbc_class, 0, None, None, 0.0)

    champion_values = [c for c, _ in pairs]
    naive_values = [n for _, n in pairs]
    wins = sum(1 for c, n in pairs if c < n)
    win_rate = wins / n_pairs

    try:
        statistic, p_value = stats.wilcoxon(champion_values, naive_values)
        return WilcoxonResult(sbc_class, n_pairs, float(statistic), float(p_value), win_rate)
    except ValueError:
        # scipy raises when every paired difference is exactly zero (champion == Seasonal
        # Naive for every series in this class), a real, disclosable outcome, not a crash.
        return WilcoxonResult(sbc_class, n_pairs, None, None, win_rate)


def build_leaderboard(results: list[PerSeriesResult]) -> LeaderboardResult:
    n_total = len({(r.dataset_seed, r.series_key) for r in results})
    n_degenerate = len(
        {(r.dataset_seed, r.series_key) for r in results if r.sbc_class == DEGENERATE_CLASS}
    )

    paired_by_series = _paired_champion_vs_seasonal_naive(results)

    wilcoxon_results = []
    for sbc_class in REAL_CLASSES:
        pairs = [v for k, v in paired_by_series.items() if k[2] == sbc_class]
        wilcoxon_results.append(_wilcoxon_for_pairs(sbc_class, pairs))
    wilcoxon_results.append(_wilcoxon_for_pairs(OVERALL_LABEL, list(paired_by_series.values())))

    return LeaderboardResult(
        method_class_summaries=_build_method_class_summaries(results),
        wilcoxon_results=wilcoxon_results,
        n_total_series=n_total,
        n_degenerate_series=n_degenerate,
    )
