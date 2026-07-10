"""Forecast metrics (DS-FC-005) against hand-computed fixtures — every value below was computed
by hand before being encoded here, not reverse-engineered from the implementation."""

import numpy as np
import pytest

from dealeriq_analytics.forecasting.metrics import coverage, mase, pinball_loss, smape


def test_mase_hand_computed() -> None:
    # y_train (period=4): naive_errors = |[9,14,10,16]-[10,12,11,15]| = [1,2,1,1], mean=1.25
    y_train = np.array([10, 12, 11, 15, 9, 14, 10, 16], dtype=float)
    # numerator: |12-11|=1, |13-14|=1 -> mean=1
    y_true = np.array([12, 13], dtype=float)
    y_pred = np.array([11, 14], dtype=float)
    assert mase(y_true, y_pred, y_train, season_length=4) == pytest.approx(1.0 / 1.25)


def test_mase_perfect_forecast_with_zero_denominator_is_zero() -> None:
    y_train = np.array([5, 5, 5, 5, 5, 5, 5, 5], dtype=float)  # naive_errors all 0
    y_true = np.array([5, 5], dtype=float)
    y_pred = np.array([5, 5], dtype=float)
    assert mase(y_true, y_pred, y_train, season_length=4) == 0.0


def test_mase_imperfect_forecast_with_zero_denominator_is_infinite() -> None:
    y_train = np.array([5, 5, 5, 5, 5, 5, 5, 5], dtype=float)
    y_true = np.array([5, 5], dtype=float)
    y_pred = np.array([6, 5], dtype=float)
    assert mase(y_true, y_pred, y_train, season_length=4) == float("inf")


def test_smape_hand_computed() -> None:
    # |10-12|=2, denom=22 -> 2*2/22=0.18182; |20-18|=2, denom=38 -> 2*2/38=0.10526
    # mean=0.14354 * 100 = 14.354%
    y_true = np.array([10, 20], dtype=float)
    y_pred = np.array([12, 18], dtype=float)
    assert smape(y_true, y_pred) == pytest.approx(14.354, abs=1e-2)


def test_smape_both_zero_is_zero_not_nan() -> None:
    y_true = np.array([0.0])
    y_pred = np.array([0.0])
    assert smape(y_true, y_pred) == 0.0


def test_pinball_loss_hand_computed() -> None:
    y_true = np.array([10, 20], dtype=float)
    y_pred = np.array([12, 18], dtype=float)
    # q=0.5: diffs=-2,2 -> max(-1,1)=1, max(1,-1)=1 -> mean=1.0
    assert pinball_loss(y_true, y_pred, q=0.5) == pytest.approx(1.0)
    # q=0.1: diff=-2 -> max(-0.2,1.8)=1.8; diff=2 -> max(0.2,-1.8)=0.2 -> mean=1.0
    assert pinball_loss(y_true, y_pred, q=0.1) == pytest.approx(1.0)
    # q=0.9: diff=-2 -> max(-1.8,0.2)=0.2; diff=2 -> max(1.8,-0.2)=1.8 -> mean=1.0
    assert pinball_loss(y_true, y_pred, q=0.9) == pytest.approx(1.0)


def test_coverage_hand_computed() -> None:
    y_true = np.array([10, 20, 30], dtype=float)
    lo = np.array([8, 15, 25], dtype=float)
    hi = np.array([12, 25, 28], dtype=float)
    # 10 in [8,12] yes; 20 in [15,25] yes; 30 in [25,28] no -> 2/3
    assert coverage(y_true, lo, hi) == pytest.approx(2.0 / 3.0)
