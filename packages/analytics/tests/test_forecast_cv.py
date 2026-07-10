"""Rolling-origin CV harness (DS-FC-004) — fold count/boundaries against a 156-week series, and
the too-short-series failure mode."""

import numpy as np
import pandas as pd
import pytest

from dealeriq_analytics.forecasting.cv import (
    HORIZON,
    MIN_TRAINING_WEEKS,
    STEP_SIZE,
    compute_n_windows,
    run_cross_validation,
    series_key_to_id,
)
from dealeriq_analytics.forecasting.methods import SEASONAL_NAIVE_ALIAS

N_WEEKS = 156
WEEK_START = pd.Timestamp("2023-07-17")


def _make_series(n_weeks: int = N_WEEKS, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range(WEEK_START, periods=n_weeks, freq="W-MON")
    values = rng.poisson(5, size=n_weeks).astype(float)
    return pd.Series(values, index=index)


def test_derived_n_windows_matches_the_156_week_arithmetic() -> None:
    # floor((156-52-12)/4)+1 = 24
    assert compute_n_windows(156) == (156 - 52 - HORIZON) // STEP_SIZE + 1
    assert compute_n_windows(156) == 24


def test_compute_n_windows_raises_for_a_too_short_series() -> None:
    with pytest.raises(ValueError, match="at least"):
        compute_n_windows(MIN_TRAINING_WEEKS + HORIZON - 1)


def test_compute_n_windows_allows_exactly_the_minimum() -> None:
    assert compute_n_windows(MIN_TRAINING_WEEKS + HORIZON) == 1


def test_cross_validation_produces_the_expected_fold_count() -> None:
    series_by_key = {("m1", "b1"): _make_series()}
    cv_results = run_cross_validation(series_by_key)
    assert SEASONAL_NAIVE_ALIAS in cv_results
    cv_df = cv_results[SEASONAL_NAIVE_ALIAS]
    unique_id = series_key_to_id(("m1", "b1"))
    sub = cv_df[cv_df["unique_id"] == unique_id]
    assert sub["cutoff"].nunique() == 24
    assert len(sub) == 24 * HORIZON


def test_earliest_fold_training_window_is_the_52_week_minimum() -> None:
    series_by_key = {("m1", "b1"): _make_series()}
    cv_results = run_cross_validation(series_by_key)
    cv_df = cv_results[SEASONAL_NAIVE_ALIAS]
    unique_id = series_key_to_id(("m1", "b1"))
    sub = cv_df[cv_df["unique_id"] == unique_id]
    earliest_cutoff = sub["cutoff"].min()
    weeks_of_training = (earliest_cutoff - WEEK_START).days // 7 + 1
    assert weeks_of_training == 52


def test_last_fold_horizon_lands_on_the_final_week_of_history() -> None:
    series_by_key = {("m1", "b1"): _make_series()}
    cv_results = run_cross_validation(series_by_key)
    cv_df = cv_results[SEASONAL_NAIVE_ALIAS]
    unique_id = series_key_to_id(("m1", "b1"))
    sub = cv_df[cv_df["unique_id"] == unique_id]
    last_week = WEEK_START + pd.Timedelta(weeks=N_WEEKS - 1)
    assert sub["ds"].max() == last_week


def test_cross_validation_works_on_a_shorter_series_too() -> None:
    # The bug this guards against: n_windows used to be hardcoded for the 156-week dataset,
    # silently producing all-NaN folds (not an error) for any shorter series.
    n_weeks = 70
    series_by_key = {("m1", "b1"): _make_series(n_weeks=n_weeks)}
    cv_results = run_cross_validation(series_by_key)
    cv_df = cv_results[SEASONAL_NAIVE_ALIAS]
    unique_id = series_key_to_id(("m1", "b1"))
    sub = cv_df[cv_df["unique_id"] == unique_id]
    assert sub["cutoff"].nunique() == compute_n_windows(n_weeks)
    assert sub[SEASONAL_NAIVE_ALIAS].notna().all()
