"""Syntetos-Boylan-Croston demand-pattern classification (DS-FC-002).

Pulled forward from Phase 4 (see specs/004-synthetic-data/spec.md Assumptions): the generator
needs this to validate its own SBC-class coverage (GEN-002) before Phase 4's forecasting
pipeline is built. Only the classification math is pulled forward — no forecasting methods, no
CV harness.

ADI (average inter-demand interval) = total periods / number of periods with nonzero demand.
CV² = squared coefficient of variation of the *nonzero* demand values.
Cutoffs (Syntetos, Boylan & Croston 2005): ADI = 1.32, CV² = 0.49.
"""

import enum

import numpy as np
from numpy.typing import NDArray

ADI_CUTOFF = 1.32
CV2_CUTOFF = 0.49


class SbcClass(enum.StrEnum):
    SMOOTH = "smooth"
    ERRATIC = "erratic"
    INTERMITTENT = "intermittent"
    LUMPY = "lumpy"


class DegenerateSeriesError(ValueError):
    """Raised when a series has no nonzero periods at all — ADI/CV² are undefined."""


def compute_adi(series: NDArray[np.float64]) -> float:
    nonzero_count = int(np.count_nonzero(series))
    if nonzero_count == 0:
        raise DegenerateSeriesError("Series has no nonzero periods; ADI is undefined.")
    return len(series) / nonzero_count


def compute_cv2(series: NDArray[np.float64]) -> float:
    nonzero = series[series != 0]
    if nonzero.size == 0:
        raise DegenerateSeriesError("Series has no nonzero periods; CV² is undefined.")
    mean = float(np.mean(nonzero))
    if mean == 0:
        raise DegenerateSeriesError("Nonzero values have zero mean; CV² is undefined.")
    std = float(np.std(nonzero))
    return (std / mean) ** 2


def classify(series: NDArray[np.float64]) -> SbcClass:
    adi = compute_adi(series)
    cv2 = compute_cv2(series)
    if adi < ADI_CUTOFF and cv2 < CV2_CUTOFF:
        return SbcClass.SMOOTH
    if adi < ADI_CUTOFF and cv2 >= CV2_CUTOFF:
        return SbcClass.ERRATIC
    if adi >= ADI_CUTOFF and cv2 < CV2_CUTOFF:
        return SbcClass.INTERMITTENT
    return SbcClass.LUMPY


def classify_with_stats(series: NDArray[np.float64]) -> tuple[SbcClass, float, float]:
    adi = compute_adi(series)
    cv2 = compute_cv2(series)
    return classify(series), adi, cv2
