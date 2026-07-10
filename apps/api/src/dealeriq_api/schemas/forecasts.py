"""Request/response models for analytics runs and forecasts (FR-070..072, DS-FC-007)."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus


class AnalyticsRunResponse(BaseModel):
    id: uuid.UUID
    job_name: str
    status: RunStatus
    seed: int | None
    code_version: str
    data_from: date
    data_to: date
    started_at: datetime
    finished_at: datetime | None
    metrics: dict[str, Any]

    @classmethod
    def from_model(cls, run: AnalyticsRun) -> "AnalyticsRunResponse":
        return cls(
            id=run.id,
            job_name=run.job_name,
            status=run.status,
            seed=run.seed,
            code_version=run.code_version,
            data_from=run.data_from,
            data_to=run.data_to,
            started_at=run.started_at,
            finished_at=run.finished_at,
            metrics=run.metrics,
        )


class LeaderboardEntry(BaseModel):
    series_key: str
    display_name: str
    pattern_class: str
    champion_method: str
    mase: float
    smape: float
    coverage80: float


class LeaderboardResponse(BaseModel):
    run_id: uuid.UUID
    entries: list[LeaderboardEntry]


class ForecastPointResponse(BaseModel):
    week_start: date
    yhat: float
    yhat_lo80: float
    yhat_hi80: float


class ActualPointResponse(BaseModel):
    week_start: date
    y: float


class MethodMetricResponse(BaseModel):
    method: str
    mase: float
    smape: float
    pinball_q10: float
    pinball_q50: float
    pinball_q90: float
    coverage80: float
    is_champion: bool


class SeriesDetailResponse(BaseModel):
    run_id: uuid.UUID
    series_key: str
    display_name: str
    pattern_class: str
    champion_method: str
    actuals: list[ActualPointResponse]
    forecast: list[ForecastPointResponse]
    metrics_by_method: list[MethodMetricResponse]
