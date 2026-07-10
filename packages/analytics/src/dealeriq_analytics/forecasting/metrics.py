"""Forecast accuracy/interval metrics (DS-FC-005). Every function here is validated against a
hand-computed fixture in tests/test_forecast_metrics.py before being wired into the CV harness.

MASE (Hyndman & Koehler 2006): out-of-sample forecast MAE scaled by the in-sample one-step
seasonal-naive MAE computed on the *training* window — scale-free and defined even when a series
has long zero runs (unlike MAPE), which is why DS-FC-005 makes it the primary metric for a
dataset that includes intermittent/lumpy series.
"""

import numpy as np
from numpy.typing import NDArray


def mase(
    y_true: NDArray[np.float64],
    y_pred: NDArray[np.float64],
    y_train: NDArray[np.float64],
    season_length: int,
) -> float:
    numerator = float(np.mean(np.abs(y_true - y_pred)))
    naive_errors = np.abs(y_train[season_length:] - y_train[:-season_length])
    denominator = float(np.mean(naive_errors))
    if denominator == 0:
        # In-sample seasonal-naive is a perfect predictor (e.g. an exactly-repeating training
        # window) — MASE's denominator is undefined. A perfect out-of-sample forecast is then
        # the only sensible "0"; any error is unscoreable, so it's infinite rather than a
        # misleadingly finite number from a 0/0-adjacent division.
        return 0.0 if numerator == 0 else float("inf")
    return numerator / denominator


def smape(y_true: NDArray[np.float64], y_pred: NDArray[np.float64]) -> float:
    denom = np.abs(y_true) + np.abs(y_pred)
    safe_denom = np.where(denom == 0, 1.0, denom)
    ratio = np.where(denom == 0, 0.0, 2.0 * np.abs(y_true - y_pred) / safe_denom)
    return float(np.mean(ratio) * 100.0)


def pinball_loss(
    y_true: NDArray[np.float64], y_pred_quantile: NDArray[np.float64], q: float
) -> float:
    diff = y_true - y_pred_quantile
    return float(np.mean(np.maximum(q * diff, (q - 1) * diff)))


def coverage(
    y_true: NDArray[np.float64], lo: NDArray[np.float64], hi: NDArray[np.float64]
) -> float:
    return float(np.mean((y_true >= lo) & (y_true <= hi)))
