"""Weekly series construction (DS-FC-001) — calendar alignment and zero-fill edge cases."""

import pandas as pd

from dealeriq_analytics.forecasting.series import build_weekly_series, compute_week_start

WEEK_START = pd.Timestamp("2023-07-17")  # a Monday
N_WEEKS = 8


def test_compute_week_start_floors_to_monday() -> None:
    # 2026-07-10 is a Friday; that week's Monday is 2026-07-06.
    timestamps = pd.Series(pd.to_datetime(["2026-07-10", "2026-07-06", "2026-07-12"]))
    result = compute_week_start(timestamps)
    assert list(result) == [pd.Timestamp("2026-07-06")] * 3


def test_build_weekly_series_zero_fills_weeks_with_no_orders() -> None:
    orders = pd.DataFrame(
        {
            "model_key": ["m1", "m1"],
            "branch": ["b1", "b1"],
            "at": [WEEK_START + pd.Timedelta(days=1), WEEK_START + pd.Timedelta(weeks=3, days=2)],
        }
    )
    series = build_weekly_series(
        orders,
        group_cols=["model_key", "branch"],
        date_col="at",
        keys=[("m1", "b1")],
        week_start=WEEK_START,
        n_weeks=N_WEEKS,
    )
    result = series[("m1", "b1")]
    assert len(result) == N_WEEKS
    assert result.iloc[0] == 1
    assert result.iloc[3] == 1
    assert list(result.iloc[[1, 2, 4, 5, 6, 7]]) == [0, 0, 0, 0, 0, 0]


def test_build_weekly_series_gives_every_requested_key_a_series_even_with_no_data() -> None:
    orders = pd.DataFrame({"model_key": [], "branch": [], "at": []})
    series = build_weekly_series(
        orders,
        group_cols=["model_key", "branch"],
        date_col="at",
        keys=[("m1", "b1"), ("m2", "b2")],
        week_start=WEEK_START,
        n_weeks=N_WEEKS,
    )
    assert set(series.keys()) == {("m1", "b1"), ("m2", "b2")}
    assert (series[("m1", "b1")] == 0).all()
    assert (series[("m2", "b2")] == 0).all()


def test_build_weekly_series_key_with_partial_data_still_gets_full_calendar() -> None:
    orders = pd.DataFrame(
        {
            "model_key": ["m1"],
            "branch": ["b1"],
            "at": [WEEK_START],
        }
    )
    series = build_weekly_series(
        orders,
        group_cols=["model_key", "branch"],
        date_col="at",
        keys=[("m1", "b1"), ("m2", "b2")],
        week_start=WEEK_START,
        n_weeks=N_WEEKS,
    )
    assert len(series[("m1", "b1")]) == N_WEEKS
    assert len(series[("m2", "b2")]) == N_WEEKS
    assert (series[("m2", "b2")] == 0).all()
