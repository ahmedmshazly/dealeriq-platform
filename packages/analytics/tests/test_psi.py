import numpy as np
import pandas as pd

from dealeriq_analytics.customer.psi import PSI_DRIFT_THRESHOLD, compute_psi, compute_psi_report


def test_identical_distributions_have_zero_psi() -> None:
    rng = np.random.default_rng(42)
    reference = pd.Series(rng.normal(size=2000))
    assert compute_psi(reference, reference) < 1e-9


def test_hand_computed_two_bin_psi() -> None:
    # Reference: 100 values split 50/50 across two bins by the median (edges: -inf, median, inf).
    # Current: shifted so 90% falls in the upper bin, 10% in the lower, a deliberate, large
    # shift computed by hand:
    #   ref_pct = [0.5, 0.5], cur_pct = [0.1, 0.9]
    #   PSI = (0.1-0.5)*ln(0.1/0.5) + (0.9-0.5)*ln(0.9/0.5)
    #       = (-0.4)*ln(0.2) + (0.4)*ln(1.8)
    #       = (-0.4)*(-1.6094379124341003) + (0.4)*(0.5877866649021191)
    #       = 0.6437751649736401 + 0.23511466596084764
    #       = 0.8788898309344878
    reference = pd.Series([0.0] * 50 + [1.0] * 50)
    current = pd.Series([0.0] * 10 + [1.0] * 90)
    psi = compute_psi(reference, current, bins=2)
    assert abs(psi - 0.8788898309344878) < 1e-6


def test_large_engineered_shift_exceeds_drift_threshold() -> None:
    rng = np.random.default_rng(7)
    reference = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    shifted = pd.Series(rng.normal(loc=4.0, scale=1.0, size=2000))
    assert compute_psi(reference, shifted) > PSI_DRIFT_THRESHOLD


def test_unchanged_distribution_stays_under_drift_threshold() -> None:
    rng = np.random.default_rng(7)
    reference = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    unchanged = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    assert compute_psi(reference, unchanged) < PSI_DRIFT_THRESHOLD


def test_zero_variance_reference_returns_zero_not_an_error() -> None:
    reference = pd.Series([5.0] * 100)
    current = pd.Series([5.0] * 100)
    assert compute_psi(reference, current) == 0.0


def test_empty_series_returns_zero() -> None:
    assert compute_psi(pd.Series([], dtype=float), pd.Series([1.0])) == 0.0
    assert compute_psi(pd.Series([1.0]), pd.Series([], dtype=float)) == 0.0


def test_report_computes_one_psi_per_named_feature() -> None:
    reference_df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [1.0] * 5})
    current_df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [1.0] * 5})
    report = compute_psi_report(reference_df, current_df, ["a", "b", "missing"])
    assert set(report.keys()) == {"a", "b"}
    assert report["a"] < 1e-9


def test_binary_one_hot_drift_is_detected_not_silently_zero() -> None:
    # A real bug found while validating against the real seeded database: quantile-based binning
    # on a 0/1 one-hot column collapses every quantile point onto the same value, producing a
    # single (-inf, +inf) bin that reports zero PSI no matter how large the actual shift in the
    # category's proportion is. 20% of the reference population is "1" (a realistic one-hot
    # channel column); the current population is 100% "1", an unmistakable composition shift
    # that must not vanish into a degenerate single bin.
    reference = pd.Series([0.0] * 80 + [1.0] * 20)
    current = pd.Series([1.0] * 100)
    psi = compute_psi(reference, current)
    assert psi > PSI_DRIFT_THRESHOLD


def test_unchanged_binary_one_hot_column_stays_at_zero_psi() -> None:
    reference = pd.Series([0.0] * 80 + [1.0] * 20)
    current = pd.Series([0.0] * 80 + [1.0] * 20)
    assert compute_psi(reference, current) < 1e-9
