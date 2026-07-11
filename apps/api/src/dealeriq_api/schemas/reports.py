"""Response models for the monthly report (FR-054)."""

from datetime import date

from pydantic import BaseModel


class SeriesAccuracyResponse(BaseModel):
    series_key: str
    mase: float
    n_weeks_evaluated: int


class AlertStatisticsResponse(BaseModel):
    counts_by_rule: dict[str, int]
    counts_by_severity: dict[str, int]
    total: int


class MonthlyReportResponse(BaseModel):
    month: date
    total_revenue: float
    total_margin: float
    achieved_accuracy: list[SeriesAccuracyResponse]
    alert_statistics: AlertStatisticsResponse
