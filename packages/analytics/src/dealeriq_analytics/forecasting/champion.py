"""Per-series champion selection (DS-FC-006) and final forecast assembly (DS-FC-007).

Champion = the method with the lowest mean MASE across its valid CV folds, but only if it beats
Seasonal Naive's mean MASE on that same series - otherwise Seasonal Naive itself is champion.
An exact tie against Seasonal Naive resolves to Seasonal Naive (the simplest sufficient
explanation, not an arbitrary pick). A method with zero valid folds for a series (every fold
failed to converge) is never eligible for champion on that series.

MASE's in-sample scale is computed once per series from the *full* 156-week history (not
re-sliced per CV fold) - a standard, practical simplification of Hyndman & Koehler's per-fold
definition that still scores "how hard is this series to beat with seasonal naive," just with
one fixed reference instead of 24 slightly-different ones.
"""

import dataclasses

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from statsforecast import StatsForecast

from dealeriq_analytics.forecasting.cv import (
    HORIZON,
    SEASON_LENGTH,
    run_cross_validation,
    series_key_to_id,
)
from dealeriq_analytics.forecasting.methods import SEASONAL_NAIVE_ALIAS, build_method_pool
from dealeriq_analytics.forecasting.metrics import coverage, mase, pinball_loss, smape


@dataclasses.dataclass(frozen=True)
class MethodMetrics:
    mase: float
    smape: float
    pinball_q10: float
    pinball_q50: float
    pinball_q90: float
    coverage80: float
    n_folds: int


@dataclasses.dataclass(frozen=True)
class ForecastPoint:
    week_start: pd.Timestamp
    yhat: float
    yhat_lo80: float
    yhat_hi80: float


@dataclasses.dataclass(frozen=True)
class SeriesForecastResult:
    series_key: tuple[str, ...]
    champion_method: str
    forecast: list[ForecastPoint]
    metrics_by_method: dict[str, MethodMetrics]


def _method_point_column(cv_df: pd.DataFrame) -> str:
    reserved = {"unique_id", "ds", "cutoff", "y"}
    candidates = [
        str(c) for c in cv_df.columns if c not in reserved and "-lo-" not in c and "-hi-" not in c
    ]
    return candidates[0]


def _compute_series_metrics(
    cv_results: dict[str, pd.DataFrame],
    unique_id: str,
    y_train: NDArray[np.float64],
) -> dict[str, MethodMetrics]:
    metrics_by_method: dict[str, MethodMetrics] = {}
    for alias, cv_df in cv_results.items():
        sub = cv_df[cv_df["unique_id"] == unique_id]
        if sub.empty:
            continue
        point_col = _method_point_column(sub)
        lo_col, hi_col = f"{point_col}-lo-80", f"{point_col}-hi-80"
        valid_mask = sub[point_col].notna() & sub[lo_col].notna() & sub[hi_col].notna()
        valid = sub[valid_mask]
        if valid.empty:
            continue
        y_true = valid["y"].to_numpy(dtype=float)
        y_pred = valid[point_col].to_numpy(dtype=float)
        lo = valid[lo_col].to_numpy(dtype=float)
        hi = valid[hi_col].to_numpy(dtype=float)
        metrics_by_method[alias] = MethodMetrics(
            mase=mase(y_true, y_pred, y_train, SEASON_LENGTH),
            smape=smape(y_true, y_pred),
            pinball_q10=pinball_loss(y_true, lo, q=0.1),
            pinball_q50=pinball_loss(y_true, y_pred, q=0.5),
            pinball_q90=pinball_loss(y_true, hi, q=0.9),
            coverage80=coverage(y_true, lo, hi),
            n_folds=len(valid),
        )
    return metrics_by_method


def select_champion(metrics_by_method: dict[str, MethodMetrics]) -> str:
    """DS-FC-006: lowest mean MASE, but never a method that loses to Seasonal Naive. An exact
    tie against Seasonal Naive resolves to Seasonal Naive."""
    if SEASONAL_NAIVE_ALIAS not in metrics_by_method:
        raise ValueError(
            "Seasonal Naive has no valid folds for this series — cannot select a champion "
            "without the mandatory floor baseline present."
        )
    best_alias = SEASONAL_NAIVE_ALIAS
    best_mase = metrics_by_method[SEASONAL_NAIVE_ALIAS].mase
    for alias, method_metrics in metrics_by_method.items():
        if alias == SEASONAL_NAIVE_ALIAS:
            continue
        if method_metrics.mase < best_mase:
            best_alias = alias
            best_mase = method_metrics.mase
    return best_alias


def _refit_champion_forecast(champion_alias: str, series: pd.Series) -> list[ForecastPoint]:
    """Refits the champion method on the FULL history (not a CV fold) to produce the actual
    persisted 12-week point forecast + 80% interval. The lower bound is clamped at 0 for display
    (vehicle demand can't be negative) - the raw, unclamped CV interval is what pinball loss and
    coverage were computed against, so clamping here doesn't retroactively change any metric."""
    model = next(
        m for m in build_method_pool(SEASON_LENGTH, HORIZON) if str(m.alias) == champion_alias
    )
    long_df = pd.DataFrame(
        {"unique_id": "target", "ds": series.index, "y": series.to_numpy(dtype=float)}
    )
    sf = StatsForecast(models=[model], freq="W-MON", n_jobs=1)
    forecast_df = sf.forecast(df=long_df, h=HORIZON, level=[80])
    points = []
    for _, row in forecast_df.iterrows():
        points.append(
            ForecastPoint(
                week_start=row["ds"],
                yhat=float(row[champion_alias]),
                yhat_lo80=max(0.0, float(row[f"{champion_alias}-lo-80"])),
                yhat_hi80=float(row[f"{champion_alias}-hi-80"]),
            )
        )
    return points


def run_forecast_pipeline(
    series_by_key: dict[tuple[str, ...], pd.Series],
) -> dict[tuple[str, ...], SeriesForecastResult]:
    cv_results = run_cross_validation(series_by_key)
    results: dict[tuple[str, ...], SeriesForecastResult] = {}
    for key, series in series_by_key.items():
        unique_id = series_key_to_id(key)
        y_train = series.to_numpy(dtype=float)
        metrics_by_method = _compute_series_metrics(cv_results, unique_id, y_train)
        champion = select_champion(metrics_by_method)
        forecast = _refit_champion_forecast(champion, series)
        results[key] = SeriesForecastResult(
            series_key=key,
            champion_method=champion,
            forecast=forecast,
            metrics_by_method=metrics_by_method,
        )
    return results
