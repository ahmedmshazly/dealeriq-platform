"""Forecast job orchestration (FR-070..072): reads orders/vehicle_units/vehicle_models/branches
from Postgres, calls `dealeriq_analytics.forecasting` (a pure, DB-free computation layer), and
writes analytics_runs/series_profiles/forecasts/forecast_metrics — all inside the run's own
lifecycle (`running` -> `succeeded`/`failed`, never left dangling).

Two series families (DS-FC-001): (model, branch) and (segment, branch). Both get the full
profile/CV/champion pipeline — DS-FC-007 asks for 12-week forecasts "per series" without
carving out an exception for the aggregate family; only the *UI* (spec.md's Assumptions)
narrows to (model, branch) for the leaderboard/fan-chart views this phase.
"""

import importlib.metadata
import uuid
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_analytics.forecasting.champion import run_forecast_pipeline
from dealeriq_analytics.forecasting.series import build_weekly_series, compute_week_start
from dealeriq_analytics.sbc import DegenerateSeriesError, classify_with_stats
from dealeriq_api.domain.models.analytics import (
    AnalyticsRun,
    Forecast,
    ForecastMetric,
    RunStatus,
    SeriesProfile,
)
from dealeriq_api.domain.models.order import Order
from dealeriq_api.domain.models.vehicle import VehicleModel, VehicleUnit

JOB_NAME = "forecast"


def _code_version() -> str:
    try:
        return importlib.metadata.version("dealeriq-analytics")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _series_key_str(key: tuple[str, ...]) -> str:
    return "::".join(key)


def _prefixed_column(df: pd.DataFrame, source_col: str, prefix: str, new_col: str) -> pd.DataFrame:
    """Adds a column whose values are `prefix + source_col`, e.g. "model:<uuid>" — so the
    (model,branch) and (segment,branch) series families can share one combined dict of series
    without key collisions, and a `forecasts.series_key` string is self-describing (an API
    caller can tell which family a series belongs to just by reading the key)."""
    out = df.copy()
    out[new_col] = prefix + out[source_col].astype(str)
    return out


def _load_orders_frame(db: Session) -> pd.DataFrame:
    rows = db.execute(
        select(
            VehicleModel.id.label("model_id"),
            VehicleModel.segment.label("segment"),
            VehicleUnit.branch_id.label("branch_id"),
            Order.created_at.label("at"),
        )
        .select_from(Order)
        .join(VehicleUnit, VehicleUnit.id == Order.unit_id)
        .join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
    ).all()
    return pd.DataFrame(
        [
            {
                "model_id": str(r.model_id),
                "segment": r.segment,
                "branch_id": str(r.branch_id),
                "at": r.at,
            }
            for r in rows
        ]
    )


def get_series_actuals(
    db: Session, series_key_str: str, *, week_start: date, data_to: date
) -> pd.Series | None:
    """Reconstructs one series' actual weekly values on demand (for the fan-chart view) — not
    persisted separately, since it's fully derivable from the orders table already. Returns
    `None` for a malformed key rather than raising, since this is reachable from user input
    (a `series_key` path parameter).

    The calendar is built from *this series' own* orders' date range (`subset`, filtered to the
    one model/branch or segment/branch pair), not the shared orders table's global min/max — the
    table holds every series at once, so an unrelated order for a different model or a
    different, unrelated run would otherwise silently widen this series' calendar with weeks
    that were never part of it. `week_start`/`data_to` (the specific `AnalyticsRun` being
    displayed) are only a fallback for the edge case where this series has zero orders at all,
    since there's no series-local range to derive a calendar from in that case."""
    parts = series_key_str.split("::")
    if len(parts) != 2 or not parts[1].startswith("branch:"):
        return None
    first, branch_part = parts
    branch_id = branch_part.removeprefix("branch:")

    orders_df = _load_orders_frame(db)
    if orders_df.empty:
        return None

    if first.startswith("model:"):
        model_id = first.removeprefix("model:")
        subset = orders_df[
            (orders_df["model_id"] == model_id) & (orders_df["branch_id"] == branch_id)
        ]
    elif first.startswith("segment:"):
        segment = first.removeprefix("segment:")
        subset = orders_df[
            (orders_df["segment"] == segment) & (orders_df["branch_id"] == branch_id)
        ]
    else:
        return None

    if subset.empty:
        calendar_start = compute_week_start(pd.Series([pd.Timestamp(week_start)])).iloc[0]
        calendar_end = compute_week_start(pd.Series([pd.Timestamp(data_to)])).iloc[0]
        n_weeks = int((calendar_end - calendar_start).days // 7) + 1
        calendar = pd.date_range(calendar_start, periods=n_weeks, freq="W-MON")
        return pd.Series(0, index=calendar, dtype="int64")

    calendar_start = compute_week_start(pd.Series([subset["at"].min()])).iloc[0]
    calendar_end = compute_week_start(pd.Series([subset["at"].max()])).iloc[0]
    n_weeks = int((calendar_end - calendar_start).days // 7) + 1
    calendar = pd.date_range(calendar_start, periods=n_weeks, freq="W-MON")
    weeks = compute_week_start(subset["at"])
    counts = weeks.value_counts()
    return counts.reindex(calendar, fill_value=0).astype("int64")


def is_job_running(db: Session, job_name: str) -> bool:
    existing = db.execute(
        select(AnalyticsRun.id).where(
            AnalyticsRun.job_name == job_name, AnalyticsRun.status == RunStatus.RUNNING
        )
    ).first()
    return existing is not None


def run_forecast_job(db: Session, *, seed: int | None = None) -> AnalyticsRun:
    """Caller (the route) is responsible for the FR-072 concurrency check (`is_job_running`)
    inside the same transaction that inserts this run's `running` row, so the check-then-insert
    is atomic under the DB's transaction isolation, not a race between two separate statements."""
    orders_df = _load_orders_frame(db)
    if orders_df.empty:
        raise ValueError("No order data found — cannot construct any demand series.")

    week_start = compute_week_start(pd.Series([orders_df["at"].min()])).iloc[0]
    last_week = compute_week_start(pd.Series([orders_df["at"].max()])).iloc[0]
    n_weeks = int((last_week - week_start).days // 7) + 1

    model_branch_df = _prefixed_column(
        _prefixed_column(orders_df, "model_id", "model:", "_key1"), "branch_id", "branch:", "_key2"
    )
    model_branch_keys = list(
        model_branch_df[["_key1", "_key2"]].drop_duplicates().itertuples(index=False, name=None)
    )
    model_branch_series = build_weekly_series(
        model_branch_df,
        group_cols=["_key1", "_key2"],
        date_col="at",
        keys=model_branch_keys,
        week_start=week_start,
        n_weeks=n_weeks,
    )

    segment_branch_df = _prefixed_column(
        _prefixed_column(orders_df, "segment", "segment:", "_key1"), "branch_id", "branch:", "_key2"
    )
    segment_branch_keys = list(
        segment_branch_df[["_key1", "_key2"]].drop_duplicates().itertuples(index=False, name=None)
    )
    segment_branch_series = build_weekly_series(
        segment_branch_df,
        group_cols=["_key1", "_key2"],
        date_col="at",
        keys=segment_branch_keys,
        week_start=week_start,
        n_weeks=n_weeks,
    )

    all_series = {**model_branch_series, **segment_branch_series}

    run = AnalyticsRun(
        job_name=JOB_NAME,
        params={"n_weeks": n_weeks, "series_count": len(all_series)},
        seed=seed,
        code_version=_code_version(),
        data_from=week_start.date(),
        data_to=last_week.date(),
        status=RunStatus.RUNNING,
        metrics={},
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()

    try:
        _execute_pipeline(db, run.id, all_series)
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.metrics = {"series_count": len(all_series)}
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.metrics = {"error": str(exc)}
        db.commit()
        raise

    db.commit()
    db.refresh(run)
    return run


def _execute_pipeline(
    db: Session, run_id: uuid.UUID, series_by_key: dict[tuple[str, ...], pd.Series]
) -> None:
    for key, series in series_by_key.items():
        key_str = _series_key_str(key)
        try:
            sbc_class, adi, cv2 = classify_with_stats(series.to_numpy(dtype=float))
            pattern_class = sbc_class.value
        except DegenerateSeriesError:
            adi, cv2, pattern_class = float("nan"), float("nan"), "degenerate"
        db.add(
            SeriesProfile(
                run_id=run_id, series_key=key_str, adi=adi, cv2=cv2, pattern_class=pattern_class
            )
        )

    results = run_forecast_pipeline(series_by_key)
    for key, result in results.items():
        key_str = _series_key_str(key)
        for point in result.forecast:
            db.add(
                Forecast(
                    run_id=run_id,
                    series_key=key_str,
                    week_start=point.week_start.date(),
                    yhat=point.yhat,
                    yhat_lo80=point.yhat_lo80,
                    yhat_hi80=point.yhat_hi80,
                    method=result.champion_method,
                )
            )
        for method, method_metrics in result.metrics_by_method.items():
            db.add(
                ForecastMetric(
                    run_id=run_id,
                    series_key=key_str,
                    method=method,
                    mase=method_metrics.mase,
                    smape=method_metrics.smape,
                    pinball_q10=method_metrics.pinball_q10,
                    pinball_q50=method_metrics.pinball_q50,
                    pinball_q90=method_metrics.pinball_q90,
                    coverage80=method_metrics.coverage80,
                    is_champion=(method == result.champion_method),
                )
            )
