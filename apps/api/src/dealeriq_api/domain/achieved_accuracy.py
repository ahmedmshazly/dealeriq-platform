"""Achieved forecast accuracy (FR-073): compares real historical forecasts to the real actuals
that have since materialized, reusing Phase 4's already-validated `mase()` metric unchanged
(ADR-024) — only the selection of which (forecast, actual) pairs to compare is new.

A given future week is typically forecast by several weekly runs at different lead times before
it arrives (DS-OPS-001: forecasting runs weekly, 12-week horizon). Deduplicated to one `yhat` per
week by taking the *earliest* run that forecast it — the longest genuine lead time, and the
strictest honest out-of-sample comparison (ADR-024).
"""

import dataclasses
from datetime import UTC, date, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_analytics.forecasting.cv import SEASON_LENGTH
from dealeriq_analytics.forecasting.metrics import mase
from dealeriq_api.domain.forecast_job import get_series_actuals
from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus

DEFAULT_WINDOW_WEEKS = 12
"""FR-073's own example: "last-3-month MASE per series"."""


@dataclasses.dataclass(frozen=True)
class AchievedAccuracyResult:
    series_key: str
    mase: float
    n_weeks_evaluated: int
    window_start: date
    window_end: date


def compute_achieved_accuracy(
    db: Session,
    series_key: str,
    *,
    as_of: datetime | None = None,
    window_weeks: int = DEFAULT_WINDOW_WEEKS,
    window_start: date | None = None,
    window_end: date | None = None,
) -> AchievedAccuracyResult | None:
    """`None` when no forecast for this series is old enough to have real actuals yet (spec.md's
    Edge Cases: "not enough history yet," never a fabricated number).

    `window_start`/`window_end` (both optional, half-open `[window_start, window_end)`) let a
    caller evaluate an exact prior calendar month (FR-054) instead of the default "last
    `window_weeks` weeks up to `as_of`" (FR-073's own rolling view)."""
    as_of = as_of or datetime.now(UTC)
    today = as_of.date()
    resolved_start = (
        window_start if window_start is not None else today - timedelta(weeks=window_weeks)
    )
    resolved_end = min(window_end, today) if window_end is not None else today
    # Never evaluate a week that hasn't happened yet, no matter what a caller passes.

    rows = db.execute(
        select(Forecast.week_start, Forecast.yhat, AnalyticsRun.finished_at)
        .join(AnalyticsRun, AnalyticsRun.id == Forecast.run_id)
        .where(Forecast.series_key == series_key, AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.asc())
    ).all()
    if not rows:
        return None

    yhat_by_week: dict[date, float] = {}
    for row in rows:
        if row.week_start >= resolved_end or row.week_start < resolved_start:
            continue
        # Rows are ordered by run.finished_at ascending, so the first row seen for a given
        # week_start is from the earliest (longest-lead-time) run.
        yhat_by_week.setdefault(row.week_start, float(row.yhat))
    if not yhat_by_week:
        return None

    full_history = get_series_actuals(db, series_key, week_start=resolved_start, data_to=today)
    if full_history is None or full_history.empty:
        return None

    weeks_sorted = sorted(yhat_by_week.keys())
    actual_by_week = {ts.date(): value for ts, value in full_history.items()}
    evaluable_weeks = [w for w in weeks_sorted if w in actual_by_week]
    if not evaluable_weeks:
        return None

    y_true = np.array([actual_by_week[w] for w in evaluable_weeks], dtype=float)
    y_pred = np.array([yhat_by_week[w] for w in evaluable_weeks], dtype=float)
    y_train = full_history.to_numpy(dtype=float)

    achieved_mase = mase(y_true, y_pred, y_train, SEASON_LENGTH)

    return AchievedAccuracyResult(
        series_key=series_key,
        mase=achieved_mase,
        n_weeks_evaluated=len(evaluable_weeks),
        window_start=evaluable_weeks[0],
        window_end=evaluable_weeks[-1],
    )
