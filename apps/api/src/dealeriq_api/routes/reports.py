"""GET /reports/monthly (FR-054)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import bad_request
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.reports.monthly_report import (
    CurrentMonthNotAllowed,
    compute_monthly_report,
    most_recently_completed_month,
)
from dealeriq_api.schemas.reports import (
    AlertStatisticsResponse,
    MonthlyReportResponse,
    SeriesAccuracyResponse,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyReportResponse)
def monthly_report_route(
    month: str | None = Query(
        default=None, description="YYYY-MM; defaults to last completed month"
    ),
    _current_user: User = Depends(require_permission("dashboard:view_manager")),
    db: Session = Depends(get_db),
) -> MonthlyReportResponse:
    if month is None:
        target_month = most_recently_completed_month()
    else:
        try:
            year_str, month_str = month.split("-")
            target_month = date(int(year_str), int(month_str), 1)
        except (ValueError, IndexError) as exc:
            raise bad_request("month must be in YYYY-MM format.") from exc

    try:
        report = compute_monthly_report(db, target_month)
    except CurrentMonthNotAllowed as exc:
        raise bad_request(str(exc)) from exc

    return MonthlyReportResponse(
        month=report.month,
        total_revenue=report.total_revenue,
        total_margin=report.total_margin,
        achieved_accuracy=[
            SeriesAccuracyResponse(
                series_key=a.series_key, mase=a.mase, n_weeks_evaluated=a.n_weeks_evaluated
            )
            for a in report.achieved_accuracy
        ],
        alert_statistics=AlertStatisticsResponse(
            counts_by_rule=report.alert_statistics.counts_by_rule,
            counts_by_severity=report.alert_statistics.counts_by_severity,
            total=report.alert_statistics.total,
        ),
    )
