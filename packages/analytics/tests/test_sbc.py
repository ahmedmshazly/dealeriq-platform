"""SBC classification against hand-computed fixtures (QA-002) - every ADI/CV² value below was
computed by hand before being encoded here, not reverse-engineered from the implementation."""

import numpy as np
import pytest

from dealeriq_analytics.sbc import (
    ADI_CUTOFF,
    CV2_CUTOFF,
    DegenerateSeriesError,
    SbcClass,
    classify,
    compute_adi,
    compute_cv2,
)

# Nonzero every period, low size variance: mean=2.5, std=0.5 -> CV2=(0.5/2.5)^2=0.04, ADI=1.
SMOOTH = np.array([2, 3, 2, 3, 2, 3, 2, 3, 2, 3], dtype=float)

# Nonzero every period, high size variance: mean=5.5, std=4.5 -> CV2=(4.5/5.5)^2=0.6694, ADI=1.
ERRATIC = np.array([1, 10, 1, 10, 1, 10, 1, 10, 1, 10], dtype=float)

# 4/12 nonzero periods (ADI=3), constant nonzero size (CV2=0).
INTERMITTENT = np.array([0, 0, 3, 0, 0, 3, 0, 0, 3, 0, 0, 3], dtype=float)

# 4/12 nonzero periods (ADI=3), highly variable nonzero size: mean=4.25, var=9.6875 ->
# CV2=9.6875/18.0625=0.5364.
LUMPY = np.array([0, 0, 5, 0, 0, 1, 0, 0, 9, 0, 0, 2], dtype=float)


def test_smooth_fixture() -> None:
    assert compute_adi(SMOOTH) == pytest.approx(1.0)
    assert compute_cv2(SMOOTH) == pytest.approx(0.04)
    assert classify(SMOOTH) == SbcClass.SMOOTH


def test_erratic_fixture() -> None:
    assert compute_adi(ERRATIC) == pytest.approx(1.0)
    assert compute_cv2(ERRATIC) == pytest.approx(0.6694, abs=1e-3)
    assert classify(ERRATIC) == SbcClass.ERRATIC


def test_intermittent_fixture() -> None:
    assert compute_adi(INTERMITTENT) == pytest.approx(3.0)
    assert compute_cv2(INTERMITTENT) == pytest.approx(0.0)
    assert classify(INTERMITTENT) == SbcClass.INTERMITTENT


def test_lumpy_fixture() -> None:
    assert compute_adi(LUMPY) == pytest.approx(3.0)
    assert compute_cv2(LUMPY) == pytest.approx(0.5364, abs=1e-3)
    assert classify(LUMPY) == SbcClass.LUMPY


def test_cutoffs_match_the_syntetos_boylan_croston_2005_values() -> None:
    assert ADI_CUTOFF == 1.32
    assert CV2_CUTOFF == 0.49


def test_all_zero_series_raises_a_clear_error_instead_of_nan() -> None:
    with pytest.raises(DegenerateSeriesError):
        classify(np.zeros(10))
