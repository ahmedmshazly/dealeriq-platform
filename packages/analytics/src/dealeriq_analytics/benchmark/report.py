"""Writes the two committed benchmark artifacts: a raw results parquet and a markdown
leaderboard (DS-OPS-004)."""

import dataclasses
from pathlib import Path

import pandas as pd

from dealeriq_analytics.benchmark.aggregate import LeaderboardResult
from dealeriq_analytics.benchmark.runner import PerSeriesResult


def write_parquet(results: list[PerSeriesResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([dataclasses.asdict(r) for r in results])
    df.to_parquet(path, index=False)


def write_leaderboard_markdown(leaderboard: LeaderboardResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Benchmark Leaderboard",
        "",
        f"{leaderboard.n_total_series} total series "
        f"({leaderboard.n_degenerate_series} degenerate, excluded below).",
        "",
        "## Mean accuracy by demand pattern and method",
        "",
        "| SBC class | Method | n series | MASE | sMAPE | Pinball q10 | Pinball q50 | "
        "Pinball q90 | 80% coverage |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in leaderboard.method_class_summaries:
        lines.append(
            f"| {s.sbc_class} | {s.method} | {s.n_series} | {s.mean_mase:.3f} | "
            f"{s.mean_smape:.1f}% | {s.mean_pinball_q10:.2f} | {s.mean_pinball_q50:.2f} | "
            f"{s.mean_pinball_q90:.2f} | {s.mean_coverage80 * 100:.0f}% |"
        )

    lines += [
        "",
        "## Champion vs. Seasonal Naive (paired Wilcoxon signed-rank on MASE)",
        "",
        "| SBC class | n pairs | Champion win rate | Wilcoxon statistic | p-value |",
        "|---|---:|---:|---:|---:|",
    ]
    for w in leaderboard.wilcoxon_results:
        stat_str = f"{w.statistic:.2f}" if w.statistic is not None else "n/a"
        p_str = f"{w.p_value:.4f}" if w.p_value is not None else "n/a"
        lines.append(
            f"| {w.sbc_class} | {w.n_pairs} | {w.champion_win_rate:.1%} | {stat_str} | {p_str} |"
        )
    lines.append("")

    path.write_text("\n".join(lines))
