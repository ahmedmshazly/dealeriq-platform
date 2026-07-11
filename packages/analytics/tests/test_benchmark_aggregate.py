"""Benchmark aggregation (DS-OPS-004) against a hand-constructed fixture, verified before
trusting it on a real multi-dataset run (QA-002 discipline).

The Wilcoxon statistic/p-value below are not reverse-engineered from the implementation: for 5
paired, non-tied, same-signed differences, the exact two-sided p-value under the null hypothesis
is derived from first principles -- of the 2**5=32 equally-likely sign assignments a rank-sum
permutation test considers, exactly 1 assigns every rank to the same side (all differences
negative), giving a one-sided exact p of 1/32 and a two-sided p of 2/32 = 0.0625, with the
positive-rank-sum statistic at its minimum, 0. Independently confirmed against scipy directly
before being encoded here (scipy is the trusted, independently-implemented oracle, exactly as
mase()'s own fixtures use the formula, not the implementation, as ground truth).
"""

import pytest

from dealeriq_analytics.benchmark.aggregate import build_leaderboard
from dealeriq_analytics.benchmark.runner import PerSeriesResult


def _row(
    *,
    seed: int,
    series: str,
    sbc_class: str,
    method: str,
    mase: float,
    is_champion: bool,
    is_seasonal_naive: bool,
) -> PerSeriesResult:
    return PerSeriesResult(
        dataset_seed=seed,
        series_key=series,
        sbc_class=sbc_class,
        method=method,
        mase=mase,
        smape=0.0,
        pinball_q10=0.0,
        pinball_q50=0.0,
        pinball_q90=0.0,
        coverage80=0.8,
        is_champion=is_champion,
        is_seasonal_naive=is_seasonal_naive,
    )


def _smooth_class_rows() -> list[PerSeriesResult]:
    # 5 series; champion (a stand-in "AutoARIMA") strictly beats Seasonal Naive (fixed at 1.0)
    # on every one, by increasing margins -- see the module docstring for the exact Wilcoxon
    # derivation this produces.
    champion_mase_values = [0.5, 0.6, 0.7, 0.8, 0.9]
    rows = []
    for i, champion_mase in enumerate(champion_mase_values):
        series = f"smooth-{i}"
        rows.append(
            _row(
                seed=1,
                series=series,
                sbc_class="smooth",
                method="AutoARIMA",
                mase=champion_mase,
                is_champion=True,
                is_seasonal_naive=False,
            )
        )
        rows.append(
            _row(
                seed=1,
                series=series,
                sbc_class="smooth",
                method="SeasonalNaive",
                mase=1.0,
                is_champion=False,
                is_seasonal_naive=True,
            )
        )
    return rows


def _degenerate_row() -> PerSeriesResult:
    return _row(
        seed=1,
        series="degenerate-0",
        sbc_class="degenerate",
        method="SeasonalNaive",
        mase=0.0,
        is_champion=True,
        is_seasonal_naive=True,
    )


def test_leaderboard_mean_mase_and_win_rate_match_hand_computation() -> None:
    leaderboard = build_leaderboard(_smooth_class_rows() + [_degenerate_row()])

    summaries = {(s.sbc_class, s.method): s for s in leaderboard.method_class_summaries}
    assert set(summaries) == {("smooth", "AutoARIMA"), ("smooth", "SeasonalNaive")}
    assert summaries[("smooth", "AutoARIMA")].n_series == 5
    assert summaries[("smooth", "AutoARIMA")].mean_mase == pytest.approx(0.7)
    assert summaries[("smooth", "SeasonalNaive")].mean_mase == pytest.approx(1.0)

    # The degenerate series is counted, never silently dropped, but excluded from the real-class
    # rollup entirely (spec.md's Edge Cases).
    assert leaderboard.n_total_series == 6
    assert leaderboard.n_degenerate_series == 1


def test_wilcoxon_matches_the_exact_hand_derived_value_for_n5_all_same_sign() -> None:
    leaderboard = build_leaderboard(_smooth_class_rows() + [_degenerate_row()])

    smooth_result = next(w for w in leaderboard.wilcoxon_results if w.sbc_class == "smooth")
    assert smooth_result.n_pairs == 5
    assert smooth_result.champion_win_rate == pytest.approx(1.0)
    assert smooth_result.statistic == pytest.approx(0.0)
    assert smooth_result.p_value == pytest.approx(0.0625)


def test_sbc_class_with_zero_pairs_is_reported_without_crashing() -> None:
    leaderboard = build_leaderboard(_smooth_class_rows())

    intermittent_result = next(
        w for w in leaderboard.wilcoxon_results if w.sbc_class == "intermittent"
    )
    assert intermittent_result.n_pairs == 0
    assert intermittent_result.statistic is None
    assert intermittent_result.p_value is None
    assert intermittent_result.champion_win_rate == 0.0
