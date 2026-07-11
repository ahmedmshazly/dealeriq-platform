"""Monthly report (FR-054): sales, margin, forecast accuracy achieved, and alert statistics for
one completed calendar month — composes `sales_summary` and `achieved_accuracy` (FR-073's own
computation, narrowed to an exact month) plus a straightforward `Alert` aggregate.
"""

import dataclasses
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.domain.achieved_accuracy import compute_achieved_accuracy
from dealeriq_api.domain.models.alerts import Alert
from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus
from dealeriq_api.domain.sales_summary import month_bounds, monthly_sales_and_margin


class CurrentMonthNotAllowed(ValueError):
    """The current, in-progress month is never presented as "the month's totals" — its data is
    necessarily incomplete (spec.md's Edge Cases)."""


@dataclasses.dataclass(frozen=True)
class SeriesAccuracy:
    series_key: str
    mase: float
    n_weeks_evaluated: int


@dataclasses.dataclass(frozen=True)
class AlertStatistics:
    counts_by_rule: dict[str, int]
    counts_by_severity: dict[str, int]
    total: int


@dataclasses.dataclass(frozen=True)
class MonthlyReportResult:
    month: date
    total_revenue: float
    total_margin: float
    achieved_accuracy: list[SeriesAccuracy]
    alert_statistics: AlertStatistics


def most_recently_completed_month(as_of: datetime | None = None) -> date:
    as_of = as_of or datetime.now(UTC)
    first_of_this_month = as_of.date().replace(day=1)
    if first_of_this_month.month == 1:
        return date(first_of_this_month.year - 1, 12, 1)
    return date(first_of_this_month.year, first_of_this_month.month - 1, 1)


def _alert_statistics(db: Session, start: date, end: date) -> AlertStatistics:
    rows = db.execute(
        select(Alert.rule_key, Alert.severity, func.count())
        .where(Alert.created_at >= start, Alert.created_at < end)
        .group_by(Alert.rule_key, Alert.severity)
    ).all()
    by_rule: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    total = 0
    for rule_key, severity, count in rows:
        by_rule[rule_key] = by_rule.get(rule_key, 0) + count
        severity_key = severity.value
        by_severity[severity_key] = by_severity.get(severity_key, 0) + count
        total += count
    return AlertStatistics(counts_by_rule=by_rule, counts_by_severity=by_severity, total=total)


def _series_with_forecasts(db: Session) -> list[str]:
    run_id = db.execute(
        select(AnalyticsRun.id)
        .where(AnalyticsRun.job_name == "forecast", AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run_id is None:
        return []
    rows = db.execute(
        select(Forecast.series_key)
        .where(Forecast.run_id == run_id, Forecast.series_key.like("model:%"))
        .distinct()
    ).all()
    return [row[0] for row in rows]


def compute_monthly_report(
    db: Session, month: date, *, as_of: datetime | None = None
) -> MonthlyReportResult:
    as_of = as_of or datetime.now(UTC)
    today = as_of.date()
    if month.year == today.year and month.month == today.month:
        raise CurrentMonthNotAllowed(
            "The current, in-progress month cannot be reported on — its data is necessarily "
            "incomplete."
        )

    start, end = month_bounds(month)
    revenue, margin = monthly_sales_and_margin(db, month)

    accuracy_results = []
    for series_key in _series_with_forecasts(db):
        result = compute_achieved_accuracy(
            db, series_key, as_of=as_of, window_start=start, window_end=end
        )
        if result is not None:
            accuracy_results.append(
                SeriesAccuracy(
                    series_key=series_key,
                    mase=result.mase,
                    n_weeks_evaluated=result.n_weeks_evaluated,
                )
            )

    return MonthlyReportResult(
        month=start,
        total_revenue=revenue,
        total_margin=margin,
        achieved_accuracy=accuracy_results,
        alert_statistics=_alert_statistics(db, start, end),
    )
