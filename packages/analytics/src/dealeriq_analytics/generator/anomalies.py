"""Anomaly injection (GEN-004): demand shocks (spikes/drops) sized to a target robust z-score
range, plus identification of naturally-occurring near-miss points.

Robust (modified) z-score, the same statistic DS-ANO-001's detector will use:
`z = 0.6745 * (residual - median(residuals)) / MAD(residuals)`, residuals from an STL
decomposition (ADR-018: statsmodels is used for STL only, nothing else). Shocks target
z in [5, 8] — comfortably past DS-ANO-001's 3.5 detection threshold. A handful of
naturally-occurring near-miss points (z in [2, 3], *not* injected — just found in the
unmodified series) are also identified, so Phase 5's false-positive-rate check
(QA-003b) has real "should NOT be flagged" cases to test against, not just true positives.

IMPORTANT for whoever builds DS-ANO-001's real detector (Phase 5): STL is called here with
`robust=False`, deliberately. With only 3 yearly cycles (156 weeks / period 52), STL's seasonal
sub-series smoothing has just 3 points per phase; `robust=True`'s iterative downweighting
converges to essentially interpolating through those 3 points on most series (empirically
verified: median residual MAD was <0.01 — often exactly 0 — on 66/66 generated series with
robust=True, vs. a healthy 0.01-1.3 range, median 0.31, with robust=False). A median/MAD
z-score computed on robust=True residuals is numerically meaningless on data shaped like this.
This is a property of the (STL, period=52, 3-cycle) combination, not of this generator's data
specifically — the real detector will hit the same degeneracy if it also uses robust=True.
"""

import dataclasses

import numpy as np
from numpy.typing import NDArray
from statsmodels.tsa.seasonal import STL

from dealeriq_analytics.generator.demand import GeneratedDemand, SeriesParams, compute_mu

STL_PERIOD = 52
MODIFIED_Z_CONSTANT = 0.6745

SHOCK_Z_MIN = 5.0
SHOCK_Z_MAX = 8.0
NEAR_MISS_Z_MIN = 2.0
NEAR_MISS_Z_MAX = 3.0


@dataclasses.dataclass(frozen=True)
class AnomalyRecord:
    series_key: str
    week_index: int
    type: str
    magnitude_multiplier: float
    expected_value: float
    injected_value: float
    implied_z: float


@dataclasses.dataclass(frozen=True)
class _SeriesResidualStats:
    deterministic: NDArray[np.float64]
    median_resid: float
    mad: float


MIN_STABLE_MAD = 0.2
"""With only 3 yearly cycles (156 weeks / period 52), STL's LOESS can fit low-count series
almost exactly, leaving a residual distribution with the majority of points at (or extremely
close to) zero — MAD then collapses towards machine epsilon and the modified z-score
`0.6745*(resid-median)/MAD` becomes numerically meaningless (blows up from floating-point noise
alone, sign included). Series/fits whose MAD falls below this floor are treated as unusable for
z-score-based injection, not as a bug to route around — this count-data-plus-short-series
degeneracy has no smaller value with the same detector this generator is targeting."""


def _residual_stats(series: NDArray[np.float64]) -> _SeriesResidualStats | None:
    if float(np.std(series)) == 0.0:
        return None
    stl = STL(series, period=STL_PERIOD, robust=False)
    residuals: NDArray[np.float64] = stl.fit().resid
    median_resid = float(np.median(residuals))
    mad = float(np.median(np.abs(residuals - median_resid)))
    if mad < MIN_STABLE_MAD:
        return None
    return _SeriesResidualStats(
        deterministic=series - residuals, median_resid=median_resid, mad=mad
    )


def _z_scores(series: NDArray[np.float64], stats: _SeriesResidualStats) -> NDArray[np.float64]:
    residuals = series - stats.deterministic
    result: NDArray[np.float64] = MODIFIED_Z_CONSTANT * (residuals - stats.median_resid) / stats.mad
    return result


def inject_demand_shocks(
    demand: GeneratedDemand,
    rng: np.random.Generator,
    n_shocks: int = 20,
) -> tuple[dict[tuple[str, str], NDArray[np.int64]], list[AnomalyRecord]]:
    """Sizes each shock against the clean series' STL stats, then *independently re-decomposes
    the mutated series* before accepting it — with only 3 yearly cycles (156 weeks / period 52),
    STL's per-phase seasonal sub-series has just 3 points, so a single outlier can occasionally
    get partially absorbed into the refit seasonal/trend estimate rather than staying in the
    residual. Verifying post-injection (not just predicting analytically) is what actually
    guarantees SC-004's "independently confirmed" detectability, and what
    `implied_z` records — the real, re-decomposed value, not the pre-injection target."""
    params_by_key: dict[tuple[str, str], SeriesParams] = {
        (p.model_key, p.branch_name): p for p in demand.series_params
    }
    mutated_series = {key: arr.copy() for key, arr in demand.series.items()}
    records: list[AnomalyRecord] = []

    # Precompute stats once per series (not per attempt) and drop series whose STL fit is
    # numerically unusable (see MIN_STABLE_MAD) — then shuffle the qualifying pool and try each
    # series in turn, rather than repeatedly re-drawing at random from the full (mostly
    # disqualified or already-used) key set, which wastes almost all attempts once a handful of
    # series are used up.
    qualifying: list[tuple[tuple[str, str], NDArray[np.float64], _SeriesResidualStats]] = []
    for key, raw_series in demand.series.items():
        clean_series = raw_series.astype(np.float64)
        stats = _residual_stats(clean_series)
        if stats is not None:
            qualifying.append((key, clean_series, stats))
    order = rng.permutation(len(qualifying))

    weeks_per_series = 40
    for idx in order:
        key, clean_series, stats = qualifying[int(idx)]
        if len(records) >= n_shocks:
            break

        accepted = False
        for _ in range(weeks_per_series):
            t = int(rng.integers(0, len(clean_series)))
            is_spike = bool(rng.uniform() < 0.5)
            target_z = float(rng.uniform(SHOCK_Z_MIN, SHOCK_Z_MAX))
            if not is_spike:
                target_z = -target_z

            injected_residual = target_z * stats.mad / MODIFIED_Z_CONSTANT + stats.median_resid
            injected_value = max(0.0, float(stats.deterministic[t] + injected_residual))
            injected_value_int = round(injected_value)

            candidate_series = clean_series.copy()
            candidate_series[t] = injected_value_int
            verify_stats = _residual_stats(candidate_series)
            if verify_stats is None:
                continue
            verified_z = float(_z_scores(candidate_series, verify_stats)[t])
            if abs(verified_z) < SHOCK_Z_MIN:
                continue
            accepted = True
            break
        if not accepted:
            continue

        params = params_by_key[key]
        mu_t = float(compute_mu(params, len(clean_series))[t])
        expected_value = float(clean_series[t])
        magnitude_multiplier = injected_value_int / mu_t if mu_t > 0 else 0.0

        mutated_series[key][t] = injected_value_int
        records.append(
            AnomalyRecord(
                series_key=f"{key[0]}|{key[1]}",
                week_index=t,
                type="spike" if is_spike else "drop",
                magnitude_multiplier=round(magnitude_multiplier, 3),
                expected_value=expected_value,
                injected_value=float(injected_value_int),
                implied_z=round(verified_z, 3),
            )
        )

    return mutated_series, records


def find_near_miss_points(
    demand: GeneratedDemand,
    rng: np.random.Generator,
    n_near_miss: int = 5,
    exclude: set[tuple[tuple[str, str], int]] | None = None,
) -> list[AnomalyRecord]:
    """Scans the *unmodified* generated series for weeks whose robust z-score already falls in
    [2, 3] by chance — real NB noise, not an injected shock. These are left in place; the point
    is to catalog them so a detector can be checked for *not* flagging them (QA-003b)."""
    exclude = exclude or set()
    candidates: list[AnomalyRecord] = []

    for key, raw_series in demand.series.items():
        series = raw_series.astype(np.float64)
        stats = _residual_stats(series)
        if stats is None:
            continue
        z_scores = _z_scores(series, stats)
        for t, z in enumerate(z_scores):
            if (key, t) in exclude:
                continue
            if NEAR_MISS_Z_MIN <= abs(z) < NEAR_MISS_Z_MAX:
                candidates.append(
                    AnomalyRecord(
                        series_key=f"{key[0]}|{key[1]}",
                        week_index=t,
                        type="near_miss",
                        magnitude_multiplier=1.0,
                        expected_value=float(stats.deterministic[t]),
                        injected_value=float(series[t]),
                        implied_z=round(float(z), 3),
                    )
                )

    if len(candidates) <= n_near_miss:
        return candidates
    chosen_idx = rng.choice(len(candidates), size=n_near_miss, replace=False)
    return [candidates[i] for i in sorted(chosen_idx)]
