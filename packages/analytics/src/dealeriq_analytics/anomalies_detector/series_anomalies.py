"""Series-level anomaly detection (DS-ANO-001, DS-ANO-002): STL decomposition + robust z-score,
confirmed (or not) by the generalized ESD test.

`robust=False` is deliberate, not a default left unexamined - Phase 3's generator
(`dealeriq_analytics.generator.anomalies`) empirically verified that `robust=True` degenerates
(residual MAD collapses towards zero) on this dataset's 156-week/52-week-seasonal shape, since
STL's seasonal sub-series smoothing only has ~3 points per phase with 3 yearly cycles. This
detector reuses that same finding and the same `MIN_STABLE_MAD` floor, since it's a property of
the (STL, period=52, 3-cycle) combination, not specific to the generator.

The generalized ESD (GESD) test is hand-implemented per ADR-017 (no actively-maintained Python
package exposes it as a standalone primitive) and validated in tests directly against Rosner
(1983)'s published worked example, the same one reproduced in the NIST/SEMATECH e-Handbook of
Statistical Methods.
"""

import dataclasses

import numpy as np
from numpy.typing import NDArray
from scipy import stats
from statsmodels.tsa.seasonal import STL

STL_PERIOD = 52
MODIFIED_Z_CONSTANT = 0.6745
Z_THRESHOLD = 3.5
SEVERITY_CAP = 5.0
MIN_STABLE_MAD = 0.2
"""Same floor as `dealeriq_analytics.generator.anomalies.MIN_STABLE_MAD` - a series whose STL
residual MAD falls below this is numerically unusable for a median/MAD z-score, not a bug to
route around (see module docstring)."""

MIN_CYCLES_FOR_ESD = 3.0
"""GESD needs enough independent residuals to be meaningful; a series with less than 3 full
seasonal cycles of history doesn't get an ESD pass (DS-ANO-002: "for series with sufficient
history"). 3 cycles is also empirically where this dataset shape's STL fit first becomes stable
at all (see `MIN_STABLE_MAD` and Phase 3's `generator/anomalies.py` finding) - a series that
barely clears the stability floor at 2-3 cycles still doesn't have enough independent residuals
for GESD's own critical-value table to be meaningful."""


@dataclasses.dataclass(frozen=True)
class SeriesAnomaly:
    week_index: int
    observed: float
    expected: float
    z_score: float
    severity: float
    esd_confirmed: bool | None
    """None when the series doesn't have enough history for GESD to run at all (DS-ANO-002)."""


class UnstableSeriesError(ValueError):
    """Raised when a series' STL fit is too degenerate (MAD below floor) for z-score scoring."""


def _stl_residuals(series: NDArray[np.float64]) -> tuple[NDArray[np.float64], float, float]:
    if float(np.std(series)) == 0.0:
        raise UnstableSeriesError("Series has zero variance — no meaningful STL decomposition.")
    stl = STL(series, period=STL_PERIOD, robust=False)
    residuals: NDArray[np.float64] = stl.fit().resid
    median_resid = float(np.median(residuals))
    mad = float(np.median(np.abs(residuals - median_resid)))
    if mad < MIN_STABLE_MAD:
        raise UnstableSeriesError(
            f"Residual MAD ({mad:.4f}) is below the stability floor ({MIN_STABLE_MAD}) — "
            "z-score would be numerically meaningless on this series."
        )
    return residuals, median_resid, mad


def z_scores(series: NDArray[np.float64]) -> NDArray[np.float64]:
    residuals, median_resid, mad = _stl_residuals(series)
    result: NDArray[np.float64] = MODIFIED_Z_CONSTANT * (residuals - median_resid) / mad
    return result


def generalized_esd_test(
    data: NDArray[np.float64], alpha: float = 0.05, max_outliers: int = 10
) -> list[int]:
    """Rosner (1983)'s generalized ESD many-outlier test. Returns the indices (into `data`, as
    given) of the detected outliers, most-extreme first. `max_outliers` is capped at n-2 (the
    test needs at least 2 remaining points to compute a standard deviation)."""
    n = len(data)
    r_max = min(max_outliers, max(0, n - 2))
    working = list(enumerate(data))
    removed_order: list[tuple[int, float]] = []

    for i in range(1, r_max + 1):
        values = np.array([v for _, v in working], dtype=float)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))
        if std == 0.0:
            break
        deviations = np.abs(values - mean)
        worst_pos = int(np.argmax(deviations))
        r_stat = deviations[worst_pos] / std

        p = 1.0 - alpha / (2.0 * (n - i + 1))
        df = n - i - 1
        if df < 1:
            break
        t_p = float(stats.t.ppf(p, df))
        lambda_i = (n - i) * t_p / float(np.sqrt((df + t_p**2) * (n - i + 1)))

        removed_index, removed_value = working.pop(worst_pos)
        removed_order.append((removed_index, r_stat - lambda_i))

    num_outliers = 0
    for k in range(len(removed_order) - 1, -1, -1):
        if removed_order[k][1] > 0:
            num_outliers = k + 1
            break

    return [idx for idx, _margin in removed_order[:num_outliers]]


def detect_series_anomalies(
    series: NDArray[np.float64], *, run_esd: bool = True
) -> list[SeriesAnomaly]:
    """Raises `UnstableSeriesError` if the series' STL fit is too degenerate to score at all -
    callers skip that series with the recorded reason, per spec.md's Edge Cases."""
    residuals, median_resid, mad = _stl_residuals(series)
    deterministic = series - residuals
    z = MODIFIED_Z_CONSTANT * (residuals - median_resid) / mad

    flagged_positions = [t for t in range(len(series)) if abs(z[t]) > Z_THRESHOLD]
    if not flagged_positions:
        return []

    esd_confirmed_positions: set[int] | None = None
    n_cycles = len(series) / STL_PERIOD
    if run_esd and n_cycles >= MIN_CYCLES_FOR_ESD:
        esd_max_outliers = max(10, len(flagged_positions))
        esd_outlier_positions = generalized_esd_test(residuals, max_outliers=esd_max_outliers)
        esd_confirmed_positions = set(esd_outlier_positions)

    anomalies = []
    for t in flagged_positions:
        esd_confirmed = (
            t in esd_confirmed_positions if esd_confirmed_positions is not None else None
        )
        anomalies.append(
            SeriesAnomaly(
                week_index=t,
                observed=float(series[t]),
                expected=float(deterministic[t]),
                z_score=float(z[t]),
                severity=min(abs(float(z[t])) / Z_THRESHOLD, SEVERITY_CAP),
                esd_confirmed=esd_confirmed,
            )
        )
    return anomalies
