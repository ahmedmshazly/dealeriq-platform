"""Rolling-origin cross-validation (DS-FC-004): minimum 52-week training window, 4-week step,
12-week horizon. `n_windows` is derived from the *actual* series length
(`floor((n_weeks-52-12)/4)+1`) — for Phase 3's 156-week dataset that's 24 (the first fold's
training window is exactly the 52-week minimum, each later fold advances the origin 4 weeks, and
the last fold's horizon lands on the final week of history), but it must be computed per-run, not
hardcoded: a fixed `n_windows=24` silently breaks (returns all-NaN folds, no visible error) on
any dataset shorter than the `h + (n_windows-1)*step_size = 104` weeks that figure assumes — this
was caught by a fast integration test using a deliberately short synthetic series, not the full
Phase 3 dataset, which is exactly why using a small dataset for that test mattered.

Each method runs in its own `StatsForecast` call rather than one call for the whole pool, so one
method's failure to converge doesn't affect any other method's results and can't silently
degrade into a fallback model's forecast — the resulting NaNs for a method/series that failed
are filtered out downstream (`champion.py`), not treated as a real (and misleadingly good or
bad) result.
"""

import pandas as pd
from statsforecast import StatsForecast

from dealeriq_analytics.forecasting.methods import build_method_pool

HORIZON = 12
STEP_SIZE = 4
MIN_TRAINING_WEEKS = 52
SEASON_LENGTH = 52
INTERVAL_LEVEL = 80


def series_key_to_id(key: tuple[str, ...]) -> str:
    return "::".join(key)


def compute_n_windows(n_weeks: int) -> int:
    """DS-FC-004: floor((n_weeks - 52 - 12) / 4) + 1. Raises if the series is too short for even
    one fold — a silent all-NaN result would be far worse than a clear failure here."""
    available = n_weeks - MIN_TRAINING_WEEKS - HORIZON
    if available < 0:
        raise ValueError(
            f"Series has {n_weeks} weeks of history, but rolling-origin CV needs at least "
            f"{MIN_TRAINING_WEEKS + HORIZON} ({MIN_TRAINING_WEEKS}-week minimum training window "
            f"+ {HORIZON}-week horizon) for even one fold."
        )
    return available // STEP_SIZE + 1


def build_long_frame(series_by_key: dict[tuple[str, ...], pd.Series]) -> pd.DataFrame:
    frames = [
        pd.DataFrame(
            {"unique_id": series_key_to_id(key), "ds": s.index, "y": s.to_numpy(dtype=float)}
        )
        for key, s in series_by_key.items()
    ]
    return pd.concat(frames, ignore_index=True)


def run_cross_validation(
    series_by_key: dict[tuple[str, ...], pd.Series],
) -> dict[str, pd.DataFrame]:
    """Returns {method_alias: cv_dataframe}, each in statsforecast's long format: one row per
    (unique_id, cutoff, ds), with `y` (actual), the method's point-forecast column (named after
    its alias), and `{alias}-lo-80`/`{alias}-hi-80` interval columns. Assumes every series in
    `series_by_key` shares the same calendar/length (true of both series families
    `forecast_job.py` builds, which share one run-wide week_start/n_weeks)."""
    long_df = build_long_frame(series_by_key)
    n_weeks = max(len(s) for s in series_by_key.values())
    n_windows = compute_n_windows(n_weeks)

    results: dict[str, pd.DataFrame] = {}
    for model in build_method_pool(SEASON_LENGTH):
        alias = str(model.alias)
        # n_jobs=-1: fits are independent per series, and this dataset's series count (81) is
        # what dominates runtime, not per-series cost — parallelizing across all available cores
        # is the difference between minutes and tens of minutes for AutoARIMA/AutoETS.
        sf = StatsForecast(models=[model], freq="W-MON", n_jobs=-1)
        try:
            cv_df = sf.cross_validation(
                df=long_df,
                h=HORIZON,
                n_windows=n_windows,
                step_size=STEP_SIZE,
                level=[INTERVAL_LEVEL],
            )
        except Exception:
            # Whole-pool failure for this method across every series is rare (statsforecast's
            # AutoARIMA/AutoETS normally fail per-series into NaN, not raise) — exclude just
            # this method for this run rather than losing every other method's results too.
            continue
        results[alias] = cv_df
    return results
