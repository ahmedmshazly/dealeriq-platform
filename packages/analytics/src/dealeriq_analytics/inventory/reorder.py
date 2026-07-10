"""Reorder point computation (DS-INV-002): safety stock derived from the champion forecast's own
quantile of lead-time demand, not a fixed multiplier.

Phase 4's persisted forecast already carries three known points of each future week's demand
distribution: the 10th and 90th percentiles (`yhat_lo80`/`yhat_hi80`, from the champion's 80%
prediction interval) and the point forecast `yhat` (treated as the 50th percentile / median
estimate). For the default service level (90%), the reorder point uses `yhat_hi80` directly — no
interpolation needed, since that *is* the 90th percentile the pipeline already computed. For any
other configured service level, this module linearly interpolates between the three known
anchor points (0.10, 0.50, 0.90) rather than assuming a parametric (e.g. Normal) distribution
the champion method may not actually produce.

Multi-week lead-time demand uses the sum of each week's *own* quantile estimate, not a true
convolved multi-week quantile (which would require the joint distribution across weeks, not just
each week's marginal) — a standard, disclosed simplification also used in practice, consistent
with this project's existing "document the simplification" treatment of MASE's fixed in-sample
scale in Phase 4.
"""

import dataclasses

from dealeriq_analytics.forecasting.champion import ForecastPoint

DEFAULT_SERVICE_LEVEL = 0.90
DEFAULT_LEAD_TIME_WEEKS = 2

_ANCHOR_QUANTILES = (0.10, 0.50, 0.90)


@dataclasses.dataclass(frozen=True)
class ReorderPointResult:
    reorder_point: float
    safety_stock: float
    service_level: float
    lead_time_weeks: int


class NoForecastError(ValueError):
    """Raised when a reorder point is requested for a series with no persisted forecast."""


def _week_quantile(point: ForecastPoint, service_level: float) -> float:
    anchors = [
        (_ANCHOR_QUANTILES[0], point.yhat_lo80),
        (_ANCHOR_QUANTILES[1], point.yhat),
        (_ANCHOR_QUANTILES[2], point.yhat_hi80),
    ]
    if service_level <= anchors[0][0]:
        return anchors[0][1]
    if service_level >= anchors[-1][0]:
        return anchors[-1][1]
    for (q_lo, v_lo), (q_hi, v_hi) in zip(anchors, anchors[1:], strict=False):
        if q_lo <= service_level <= q_hi:
            weight = (service_level - q_lo) / (q_hi - q_lo)
            return v_lo + weight * (v_hi - v_lo)
    raise AssertionError("unreachable: service_level not covered by anchor quantiles")


def compute_reorder_point(
    forecast: list[ForecastPoint],
    *,
    service_level: float = DEFAULT_SERVICE_LEVEL,
    lead_time_weeks: int = DEFAULT_LEAD_TIME_WEEKS,
) -> ReorderPointResult:
    """`forecast` is the champion's persisted future-week points, in chronological order
    (`champion.py`'s `_refit_champion_forecast` output / the `forecasts` table rows for one
    series). Raises `NoForecastError` if there aren't enough forecast weeks to cover the
    configured lead time — callers should skip that (model, branch) with the recorded reason
    (spec.md User Story 2, Acceptance Scenario 2), not fabricate a value."""
    if len(forecast) < lead_time_weeks:
        raise NoForecastError(
            f"Forecast has {len(forecast)} weeks, need at least {lead_time_weeks} "
            f"to cover the configured lead time."
        )
    window = forecast[:lead_time_weeks]
    reorder_point = sum(_week_quantile(p, service_level) for p in window)
    expected_demand = sum(p.yhat for p in window)
    safety_stock = max(0.0, reorder_point - expected_demand)
    return ReorderPointResult(
        reorder_point=reorder_point,
        safety_stock=safety_stock,
        service_level=service_level,
        lead_time_weeks=lead_time_weeks,
    )
