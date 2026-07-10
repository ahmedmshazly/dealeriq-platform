"""AnalyticsRun, SeriesProfile, Forecast, ForecastMetric — the run-tracking backbone every
analytics job (Phase 4+) reuses (FR-070..072). Schema per SRS §7's representative-resources
list. DAT-003: these are analytics tables, never touched by transactional code, and never
mutated in place once a run completes — a re-run creates a new `run_id`, it never updates an old
run's rows.

`mase` is a plain `Float` (double precision), not `Numeric`: a degenerate series (constant
in-sample seasonal-naive error) makes MASE mathematically `inf` for an imperfect forecast
(`forecasting/metrics.py`'s own documented behavior) — Postgres `NUMERIC` cannot store infinity,
`double precision` can.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class RunStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AnalyticsRun(IdMixin, Base):
    __tablename__ = "analytics_runs"
    __table_args__ = (Index("ix_analytics_runs_job_name_status", "job_name", "status"),)

    job_name: Mapped[str] = mapped_column(String(60))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    seed: Mapped[int | None] = mapped_column(default=None)
    code_version: Mapped[str] = mapped_column(String(60))
    data_from: Mapped[date]
    data_to: Mapped[date]
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=20), default=RunStatus.RUNNING
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SeriesProfile(IdMixin, Base):
    __tablename__ = "series_profiles"
    __table_args__ = (Index("ix_series_profiles_run_id_series_key", "run_id", "series_key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    series_key: Mapped[str] = mapped_column(String(255))
    adi: Mapped[float] = mapped_column(Float)
    cv2: Mapped[float] = mapped_column(Float)
    pattern_class: Mapped[str] = mapped_column(String(20))


class Forecast(IdMixin, Base):
    __tablename__ = "forecasts"
    __table_args__ = (Index("ix_forecasts_run_id_series_key", "run_id", "series_key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    series_key: Mapped[str] = mapped_column(String(255))
    week_start: Mapped[date]
    yhat: Mapped[float] = mapped_column(Float)
    yhat_lo80: Mapped[float] = mapped_column(Float)
    yhat_hi80: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40))


class ForecastMetric(IdMixin, Base):
    __tablename__ = "forecast_metrics"
    __table_args__ = (Index("ix_forecast_metrics_run_id_series_key", "run_id", "series_key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    series_key: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(40))
    mase: Mapped[float] = mapped_column(Float)
    smape: Mapped[float] = mapped_column(Float)
    pinball_q10: Mapped[float] = mapped_column(Float)
    pinball_q50: Mapped[float] = mapped_column(Float)
    pinball_q90: Mapped[float] = mapped_column(Float)
    coverage80: Mapped[float] = mapped_column(Float)
    is_champion: Mapped[bool] = mapped_column(Boolean, default=False)
