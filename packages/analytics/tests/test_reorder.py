import pandas as pd
import pytest

from dealeriq_analytics.forecasting.champion import ForecastPoint
from dealeriq_analytics.inventory.reorder import (
    NoForecastError,
    compute_reorder_point,
)


def _point(week: int, yhat: float, lo: float, hi: float) -> ForecastPoint:
    return ForecastPoint(
        week_start=pd.Timestamp("2026-01-05") + pd.Timedelta(weeks=week),
        yhat=yhat,
        yhat_lo80=lo,
        yhat_hi80=hi,
    )


def test_default_service_level_uses_the_90th_percentile_directly() -> None:
    # service_level=0.90 is exactly the top anchor -> no interpolation, just yhat_hi80 per week
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0), _point(1, yhat=12.0, lo=8.0, hi=16.0)]
    result = compute_reorder_point(forecast, service_level=0.90, lead_time_weeks=2)
    assert abs(result.reorder_point - (14.0 + 16.0)) < 1e-9
    assert abs(result.safety_stock - ((14.0 + 16.0) - (10.0 + 12.0))) < 1e-9


def test_service_level_50_uses_yhat_directly() -> None:
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    result = compute_reorder_point(forecast, service_level=0.50, lead_time_weeks=1)
    assert abs(result.reorder_point - 10.0) < 1e-9
    assert abs(result.safety_stock - 0.0) < 1e-9


def test_interpolated_service_level_hand_computed() -> None:
    # q=0.70 is halfway between the 0.50 anchor (yhat=10) and 0.90 anchor (hi=14):
    # 10 + 0.5*(14-10) = 12
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    result = compute_reorder_point(forecast, service_level=0.70, lead_time_weeks=1)
    assert abs(result.reorder_point - 12.0) < 1e-9


def test_interpolated_low_service_level_hand_computed() -> None:
    # q=0.30 is halfway between the 0.10 anchor (lo=6) and 0.50 anchor (yhat=10): 6+0.5*4=8
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    result = compute_reorder_point(forecast, service_level=0.30, lead_time_weeks=1)
    assert abs(result.reorder_point - 8.0) < 1e-9


def test_service_level_below_lowest_anchor_is_clamped() -> None:
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    result = compute_reorder_point(forecast, service_level=0.01, lead_time_weeks=1)
    assert abs(result.reorder_point - 6.0) < 1e-9


def test_service_level_above_highest_anchor_is_clamped() -> None:
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    result = compute_reorder_point(forecast, service_level=0.99, lead_time_weeks=1)
    assert abs(result.reorder_point - 14.0) < 1e-9


def test_insufficient_forecast_weeks_raises_no_forecast_error() -> None:
    forecast = [_point(0, yhat=10.0, lo=6.0, hi=14.0)]
    with pytest.raises(NoForecastError):
        compute_reorder_point(forecast, lead_time_weeks=2)
