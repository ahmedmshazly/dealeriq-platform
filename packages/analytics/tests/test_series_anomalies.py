import numpy as np

from dealeriq_analytics.anomalies_detector.series_anomalies import (
    UnstableSeriesError,
    detect_series_anomalies,
    generalized_esd_test,
    z_scores,
)

# The exact 54-point dataset from Rosner (1983), reproduced in the NIST/SEMATECH e-Handbook of
# Statistical Methods (section 1.3.5.17, "Detection of Outliers") as the canonical worked
# example for the generalized ESD many-outlier test. At alpha=0.05, searching up to r=10
# candidate outliers, the published result is exactly 3 outliers detected: the three largest
# values (6.01, 5.42, 5.34), in that order of extremity.
ROSNER_1983_DATA = np.array(
    [
        -0.25,
        0.68,
        0.94,
        1.15,
        1.20,
        1.26,
        1.26,
        1.34,
        1.38,
        1.43,
        1.49,
        1.49,
        1.55,
        1.56,
        1.58,
        1.65,
        1.69,
        1.70,
        1.76,
        1.77,
        1.81,
        1.91,
        1.94,
        1.96,
        1.99,
        2.06,
        2.09,
        2.10,
        2.14,
        2.15,
        2.23,
        2.24,
        2.26,
        2.35,
        2.37,
        2.40,
        2.47,
        2.54,
        2.62,
        2.64,
        2.90,
        2.92,
        2.92,
        2.93,
        3.21,
        3.26,
        3.30,
        3.59,
        3.68,
        4.30,
        4.64,
        5.34,
        5.42,
        6.01,
    ]
)


def test_generalized_esd_matches_the_published_rosner_1983_worked_example() -> None:
    outlier_indices = generalized_esd_test(ROSNER_1983_DATA, alpha=0.05, max_outliers=10)
    assert len(outlier_indices) == 3
    outlier_values = sorted(ROSNER_1983_DATA[outlier_indices], reverse=True)
    assert outlier_values == [6.01, 5.42, 5.34]


def test_generalized_esd_returns_empty_for_no_outliers() -> None:
    rng = np.random.default_rng(42)
    clean_data = rng.normal(loc=10.0, scale=1.0, size=50)
    outlier_indices = generalized_esd_test(clean_data, alpha=0.05, max_outliers=10)
    assert outlier_indices == []


def _seasonal_series_with_spike(
    spike_week: int | None, spike_value: float = 500.0, n_weeks: int = 156, seed: int = 16
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weeks = np.arange(n_weeks)
    seasonal = 20.0 + 10.0 * np.sin(2 * np.pi * weeks / 52.0)
    noise = rng.normal(0.0, 1.5, size=n_weeks)
    series = seasonal + noise
    series = np.clip(series, 0, None)
    if spike_week is not None:
        series[spike_week] = spike_value
    return series


def test_a_clear_injected_spike_is_flagged() -> None:
    series = _seasonal_series_with_spike(spike_week=80, spike_value=500.0)
    anomalies = detect_series_anomalies(series)
    flagged_weeks = {a.week_index for a in anomalies}
    assert 80 in flagged_weeks
    spike_anomaly = next(a for a in anomalies if a.week_index == 80)
    assert spike_anomaly.z_score > 3.5
    assert spike_anomaly.severity > 1.0


def test_a_clean_seasonal_series_has_no_anomalies() -> None:
    series = _seasonal_series_with_spike(spike_week=None)
    anomalies = detect_series_anomalies(series)
    assert anomalies == []


def test_zero_variance_series_raises_unstable_series_error() -> None:
    series = np.zeros(156)
    try:
        z_scores(series)
        raise AssertionError("expected UnstableSeriesError")
    except UnstableSeriesError:
        pass


def test_short_series_gets_no_esd_confirmation_but_still_flags_zscore() -> None:
    # 140 weeks (~2.69 cycles) is empirically long enough for a stable STL fit on this synthetic
    # fixture (verified: residual MAD clears MIN_STABLE_MAD here) but still short of
    # MIN_CYCLES_FOR_ESD=3.0 -> esd_confirmed must be None even though the spike still flags.
    series = _seasonal_series_with_spike(spike_week=30, spike_value=500.0, n_weeks=140, seed=16)
    anomalies = detect_series_anomalies(series)
    assert any(a.week_index == 30 for a in anomalies)
    spike = next(a for a in anomalies if a.week_index == 30)
    assert spike.esd_confirmed is None


def test_long_series_does_get_esd_confirmation() -> None:
    series = _seasonal_series_with_spike(spike_week=80, spike_value=500.0, n_weeks=156, seed=16)
    anomalies = detect_series_anomalies(series)
    spike = next(a for a in anomalies if a.week_index == 80)
    assert spike.esd_confirmed is True
