"""GET /forecasts (leaderboard), GET /forecasts/{series_key} (fan chart + metrics) - DS-FC-007.

Both default to the latest `succeeded` run (FR-071); pass `?run_id=` for a historical one.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import not_found
from dealeriq_api.domain.jobs.forecast_job import get_series_actuals
from dealeriq_api.domain.models.analytics import (
    AnalyticsRun,
    Forecast,
    ForecastMetric,
    RunStatus,
    SeriesProfile,
)
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import VehicleModel
from dealeriq_api.domain.reports.achieved_accuracy import (
    DEFAULT_WINDOW_WEEKS,
    compute_achieved_accuracy,
)
from dealeriq_api.schemas.forecasts import (
    AchievedAccuracyResponse,
    ActualPointResponse,
    ForecastPointResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    MethodMetricResponse,
    SeriesDetailResponse,
)

router = APIRouter(prefix="/api/v1/forecasts", tags=["forecasts"])


def _resolve_run(db: Session, run_id: uuid.UUID | None) -> AnalyticsRun:
    if run_id is not None:
        run = db.get(AnalyticsRun, run_id)
        if run is None:
            raise not_found("Run not found.")
        return run
    run = (
        db.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == "forecast", AnalyticsRun.status == RunStatus.SUCCEEDED)
            .order_by(AnalyticsRun.finished_at.desc())
        )
        .scalars()
        .first()
    )
    if run is None:
        raise not_found("No successful forecast run exists yet.")
    return run


def _display_name(db: Session, series_key: str) -> str:
    parts = series_key.split("::")
    if len(parts) != 2 or not parts[1].startswith("branch:"):
        return series_key
    first, branch_part = parts
    branch_id = branch_part.removeprefix("branch:")
    branch = db.get(Branch, uuid.UUID(branch_id))
    branch_name = branch.name if branch is not None else branch_id

    if first.startswith("model:"):
        model = db.get(VehicleModel, uuid.UUID(first.removeprefix("model:")))
        model_name = f"{model.make} {model.model}" if model is not None else first
        return f"{model_name} @ {branch_name}"
    if first.startswith("segment:"):
        return f"{first.removeprefix('segment:').title()} (segment) @ {branch_name}"
    return series_key


@router.get("", response_model=LeaderboardResponse)
def leaderboard_route(
    run_id: uuid.UUID | None = Query(default=None),
    pattern_class: str | None = Query(default=None),
    _current_user: User = Depends(require_permission("forecasts:view")),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    run = _resolve_run(db, run_id)

    profiles = {
        p.series_key: p.pattern_class
        for p in db.execute(select(SeriesProfile).where(SeriesProfile.run_id == run.id)).scalars()
    }
    champions = (
        db.execute(
            select(ForecastMetric).where(
                ForecastMetric.run_id == run.id, ForecastMetric.is_champion.is_(True)
            )
        )
        .scalars()
        .all()
    )

    entries = []
    for metric in champions:
        series_pattern_class = profiles.get(metric.series_key, "unknown")
        if pattern_class is not None and series_pattern_class != pattern_class:
            continue
        # Only (model, branch) series surface in the leaderboard UI this phase (spec.md's
        # Assumptions) - (segment, branch) aggregates are still profiled/forecast, just not
        # shown here.
        if not metric.series_key.startswith("model:"):
            continue
        entries.append(
            LeaderboardEntry(
                series_key=metric.series_key,
                display_name=_display_name(db, metric.series_key),
                pattern_class=series_pattern_class,
                champion_method=metric.method,
                mase=metric.mase,
                smape=metric.smape,
                coverage80=metric.coverage80,
            )
        )
    return LeaderboardResponse(run_id=run.id, entries=entries)


@router.get("/{series_key}", response_model=SeriesDetailResponse)
def series_detail_route(
    series_key: str,
    run_id: uuid.UUID | None = Query(default=None),
    _current_user: User = Depends(require_permission("forecasts:view")),
    db: Session = Depends(get_db),
) -> SeriesDetailResponse:
    run = _resolve_run(db, run_id)

    profile = db.execute(
        select(SeriesProfile).where(
            SeriesProfile.run_id == run.id, SeriesProfile.series_key == series_key
        )
    ).scalar_one_or_none()
    if profile is None:
        raise not_found("Series not found in this run.")

    forecast_rows = (
        db.execute(
            select(Forecast)
            .where(Forecast.run_id == run.id, Forecast.series_key == series_key)
            .order_by(Forecast.week_start)
        )
        .scalars()
        .all()
    )
    metric_rows = (
        db.execute(
            select(ForecastMetric).where(
                ForecastMetric.run_id == run.id, ForecastMetric.series_key == series_key
            )
        )
        .scalars()
        .all()
    )
    champion = next((m.method for m in metric_rows if m.is_champion), "")

    actuals = get_series_actuals(db, series_key, week_start=run.data_from, data_to=run.data_to)
    actual_points = (
        [ActualPointResponse(week_start=idx.date(), y=float(v)) for idx, v in actuals.items()]
        if actuals is not None
        else []
    )

    return SeriesDetailResponse(
        run_id=run.id,
        series_key=series_key,
        display_name=_display_name(db, series_key),
        pattern_class=profile.pattern_class,
        champion_method=champion,
        actuals=actual_points,
        forecast=[
            ForecastPointResponse(
                week_start=f.week_start, yhat=f.yhat, yhat_lo80=f.yhat_lo80, yhat_hi80=f.yhat_hi80
            )
            for f in forecast_rows
        ],
        metrics_by_method=[
            MethodMetricResponse(
                method=m.method,
                mase=m.mase,
                smape=m.smape,
                pinball_q10=m.pinball_q10,
                pinball_q50=m.pinball_q50,
                pinball_q90=m.pinball_q90,
                coverage80=m.coverage80,
                is_champion=m.is_champion,
            )
            for m in metric_rows
        ],
    )


@router.get("/{series_key}/achieved-accuracy", response_model=AchievedAccuracyResponse)
def achieved_accuracy_route(
    series_key: str,
    window_weeks: int = Query(default=DEFAULT_WINDOW_WEEKS, ge=1, le=52),
    _current_user: User = Depends(require_permission("forecasts:view")),
    db: Session = Depends(get_db),
) -> AchievedAccuracyResponse:
    """FR-073: real out-of-sample accuracy, distinct from the training-time cross-validation
    metrics `SeriesDetailResponse.metrics_by_method` already reports."""
    result = compute_achieved_accuracy(db, series_key, window_weeks=window_weeks)
    if result is None:
        return AchievedAccuracyResponse(
            series_key=series_key,
            mase=None,
            n_weeks_evaluated=0,
            window_start=None,
            window_end=None,
        )
    return AchievedAccuracyResponse(
        series_key=result.series_key,
        mase=result.mase,
        n_weeks_evaluated=result.n_weeks_evaluated,
        window_start=result.window_start,
        window_end=result.window_end,
    )
