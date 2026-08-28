"""Inventory intelligence & anomaly detection job orchestration (DS-INV-001..004,
DS-ANO-001..004). Reads orders/vehicle_units/stock_movements/Phase 4's latest succeeded forecast
run, calls `dealeriq_analytics`'s inventory + anomaly modules (pure, DB-free computation), and
writes run/inventory_intel/unit_risk/anomalies - reusing Phase 4's `AnalyticsRun` run-tracking
table rather than a parallel mechanism (FR-070 already covers "every analytics execution").

Reorder points depend on Phase 4's persisted champion forecasts (DS-INV-002) - a (model, branch)
with no succeeded forecast run yet gets an `InventoryIntel` row with `abc`/`xyz` still populated
(those don't depend on forecasts) but `reorder_point`/`safety_stock` left null and
`skipped_reason` recorded, never a fabricated value (spec.md User Story 2).

Survival analysis (DS-INV-004) only includes IN_STOCK/RESERVED units (right-censored, still on
lot) and SOLD units (the observed event, timed by their `StockMovement(type=SALE)` row) -
TRANSFERRED units are excluded from the risk pool entirely, since they didn't sell from this
branch and their fate afterward isn't this phase's concern (a documented simplification).
"""

import importlib.metadata
import uuid
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_analytics.anomalies_detector.series_anomalies import (
    UnstableSeriesError,
    detect_series_anomalies,
)
from dealeriq_analytics.anomalies_detector.transaction_anomalies import (
    OrderRecord as AnomalyOrderRecord,
)
from dealeriq_analytics.anomalies_detector.transaction_anomalies import (
    detect_transaction_anomalies,
)
from dealeriq_analytics.forecasting.champion import ForecastPoint
from dealeriq_analytics.forecasting.series import (
    build_weekly_mean_series,
    build_weekly_series,
    compute_week_start,
)
from dealeriq_analytics.inventory.abc_xyz import classify_abc_xyz
from dealeriq_analytics.inventory.reorder import NoForecastError, compute_reorder_point
from dealeriq_analytics.inventory.survival import (
    TimeToSaleObservation,
    fit_survival_curve,
    is_aging,
    sale_probability_within,
)
from dealeriq_analytics.inventory.survival import (
    days_on_lot as compute_days_on_lot,
)
from dealeriq_api.domain.jobs.job_lifecycle import begin_run
from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus
from dealeriq_api.domain.models.inventory_intel import (
    ANOMALY_STATUS_NEW,
    Anomaly,
    InventoryIntel,
    UnitRisk,
)
from dealeriq_api.domain.models.order import Order
from dealeriq_api.domain.models.vehicle import (
    MovementType,
    StockMovement,
    UnitStatus,
    VehicleModel,
    VehicleUnit,
)

JOB_NAME = "inventory"
FORECAST_JOB_NAME = "forecast"

DEFAULT_AGING_THRESHOLD_DAYS = 90
DEFAULT_DISCOUNT_K = 3.0
MIN_OBSERVATIONS_FOR_SURVIVAL = 5
"""A segment's Kaplan-Meier curve needs at least this many time-to-sale observations (sold or
still-in-stock) to be worth fitting at all - below this, p_sale_30d/risk_decile are left null
rather than fit to a near-empty, meaningless curve."""


def _code_version() -> str:
    try:
        return importlib.metadata.version("dealeriq-analytics")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _latest_succeeded_forecast_run_id(db: Session) -> uuid.UUID | None:
    row = db.execute(
        select(AnalyticsRun.id)
        .where(
            AnalyticsRun.job_name == FORECAST_JOB_NAME, AnalyticsRun.status == RunStatus.SUCCEEDED
        )
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def _load_forecast_points(
    db: Session, forecast_run_id: uuid.UUID
) -> dict[str, list[ForecastPoint]]:
    rows = db.execute(
        select(
            Forecast.series_key,
            Forecast.week_start,
            Forecast.yhat,
            Forecast.yhat_lo80,
            Forecast.yhat_hi80,
        )
        .where(Forecast.run_id == forecast_run_id)
        .order_by(Forecast.series_key, Forecast.week_start)
    ).all()
    points_by_key: dict[str, list[ForecastPoint]] = {}
    for series_key, week_start, yhat, lo, hi in rows:
        points_by_key.setdefault(series_key, []).append(
            ForecastPoint(
                week_start=pd.Timestamp(week_start), yhat=yhat, yhat_lo80=lo, yhat_hi80=hi
            )
        )
    return points_by_key


def _load_orders_frame(db: Session) -> pd.DataFrame:
    rows = db.execute(
        select(
            Order.id.label("order_id"),
            VehicleModel.id.label("model_id"),
            VehicleModel.segment.label("segment"),
            VehicleModel.list_price.label("list_price"),
            VehicleUnit.branch_id.label("branch_id"),
            VehicleUnit.acquisition_cost.label("acquisition_cost"),
            Order.negotiated_price.label("negotiated_price"),
            Order.created_at.label("at"),
        )
        .select_from(Order)
        .join(VehicleUnit, VehicleUnit.id == Order.unit_id)
        .join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
    ).all()
    return pd.DataFrame(
        [
            {
                "order_id": str(r.order_id),
                "model_id": str(r.model_id),
                "segment": r.segment,
                "list_price": float(r.list_price),
                "branch_id": str(r.branch_id),
                "acquisition_cost": float(r.acquisition_cost),
                "negotiated_price": float(r.negotiated_price),
                "at": r.at,
            }
            for r in rows
        ]
    )


def run_inventory_job(db: Session, *, as_of: date | None = None) -> AnalyticsRun:
    """Insert RUNNING first (FR-072), then load data and compute."""
    as_of = as_of or datetime.now(UTC).date()
    run = begin_run(
        db,
        job_name=JOB_NAME,
        code_version=_code_version(),
        params={"as_of": as_of.isoformat()},
    )

    try:
        orders_df = _load_orders_frame(db)
        if orders_df.empty:
            raise ValueError("No order data found — cannot compute inventory intelligence.")

        run.data_from = pd.Timestamp(orders_df["at"].min()).date()
        run.data_to = pd.Timestamp(orders_df["at"].max()).date()

        summary = _execute_pipeline(db, run.id, orders_df, as_of)
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.metrics = summary
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
    db: Session, run_id: uuid.UUID, orders_df: pd.DataFrame, as_of: date
) -> dict[str, int]:
    n_inventory_intel = _write_inventory_intel(db, run_id, orders_df)
    n_unit_risk = _write_unit_risk(db, run_id, as_of)
    n_series_anomalies = _write_series_anomalies(db, run_id, orders_df)
    n_transaction_anomalies = _write_transaction_anomalies(db, run_id, orders_df)
    return {
        "inventory_intel_rows": n_inventory_intel,
        "unit_risk_rows": n_unit_risk,
        "series_anomalies": n_series_anomalies,
        "transaction_anomalies": n_transaction_anomalies,
    }


def _write_inventory_intel(db: Session, run_id: uuid.UUID, orders_df: pd.DataFrame) -> int:
    revenue_by_model = orders_df.groupby("model_id")["negotiated_price"].sum().to_dict()

    week_start = compute_week_start(pd.Series([orders_df["at"].min()])).iloc[0]
    last_week = compute_week_start(pd.Series([orders_df["at"].max()])).iloc[0]
    n_weeks = int((last_week - week_start).days // 7) + 1
    model_ids = list(revenue_by_model.keys())
    weekly_demand_by_model_tup = build_weekly_series(
        orders_df,
        group_cols=["model_id"],
        date_col="at",
        keys=[(m,) for m in model_ids],
        week_start=week_start,
        n_weeks=n_weeks,
    )
    weekly_demand_by_model = {k[0]: v for k, v in weekly_demand_by_model_tup.items()}

    classification = classify_abc_xyz(revenue_by_model, weekly_demand_by_model)

    forecast_run_id = _latest_succeeded_forecast_run_id(db)
    forecast_points_by_key = (
        _load_forecast_points(db, forecast_run_id) if forecast_run_id is not None else {}
    )

    model_branch_pairs = (
        orders_df[["model_id", "branch_id"]].drop_duplicates().itertuples(index=False, name=None)
    )
    count = 0
    for model_id, branch_id in model_branch_pairs:
        result = classification[model_id]
        series_key = f"model:{model_id}::branch:{branch_id}"
        forecast_points = forecast_points_by_key.get(series_key)

        reorder_point = safety_stock = service_level = None
        skipped_reason = None
        if forecast_run_id is None:
            skipped_reason = "No succeeded forecast run exists yet."
        elif not forecast_points:
            skipped_reason = "No persisted forecast for this series in the latest run."
        else:
            try:
                reorder_result = compute_reorder_point(forecast_points)
                reorder_point = reorder_result.reorder_point
                safety_stock = reorder_result.safety_stock
                service_level = reorder_result.service_level
            except NoForecastError as exc:
                skipped_reason = str(exc)

        db.add(
            InventoryIntel(
                run_id=run_id,
                model_id=uuid.UUID(model_id),
                branch_id=uuid.UUID(branch_id),
                abc=result.abc,
                xyz=result.xyz,
                revenue_share=result.revenue_share,
                demand_cv=result.demand_cv,
                reorder_point=reorder_point,
                safety_stock=safety_stock,
                service_level=service_level,
                skipped_reason=skipped_reason,
            )
        )
        count += 1
    return count


def _write_unit_risk(db: Session, run_id: uuid.UUID, as_of: date) -> int:
    unit_rows = db.execute(
        select(
            VehicleUnit.id,
            VehicleUnit.status,
            VehicleUnit.acquisition_date,
            VehicleModel.segment,
        ).join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
    ).all()

    sale_events: dict[uuid.UUID, datetime] = dict(
        db.execute(
            select(StockMovement.unit_id, StockMovement.occurred_at).where(
                StockMovement.type == MovementType.SALE
            )
        ).all()  # type: ignore[arg-type]
    )

    observations_by_segment: dict[str, list[TimeToSaleObservation]] = {}
    at_risk_units: list[tuple[uuid.UUID, str, date]] = []
    for unit_id, status, acquisition_date, segment in unit_rows:
        if status == UnitStatus.TRANSFERRED:
            continue
        sold_at = sale_events.get(unit_id)
        if sold_at is not None:
            duration = (sold_at.date() - acquisition_date).days
            sold = True
        else:
            duration = (as_of - acquisition_date).days
            sold = False
        observations_by_segment.setdefault(segment, []).append(
            TimeToSaleObservation(unit_id=str(unit_id), duration_days=max(0, duration), sold=sold)
        )
        if status in (UnitStatus.IN_STOCK, UnitStatus.RESERVED):
            at_risk_units.append((unit_id, segment, acquisition_date))

    curves = {
        segment: fit_survival_curve(obs)
        for segment, obs in observations_by_segment.items()
        if len(obs) >= MIN_OBSERVATIONS_FOR_SURVIVAL
    }

    probabilities: dict[uuid.UUID, float] = {}
    days_on_lot_by_unit: dict[uuid.UUID, int] = {}
    for unit_id, segment, acquisition_date in at_risk_units:
        days = compute_days_on_lot(acquisition_date, as_of)
        days_on_lot_by_unit[unit_id] = days
        curve = curves.get(segment)
        if curve is not None:
            probabilities[unit_id] = sale_probability_within(curve, days)

    deciles = _assign_risk_deciles(probabilities)

    count = 0
    for unit_id, _segment, _acq in at_risk_units:
        days = days_on_lot_by_unit[unit_id]
        db.add(
            UnitRisk(
                run_id=run_id,
                unit_id=unit_id,
                days_on_lot=days,
                is_aging=is_aging(days, DEFAULT_AGING_THRESHOLD_DAYS),
                p_sale_30d=probabilities.get(unit_id),
                risk_decile=deciles.get(unit_id),
            )
        )
        count += 1
    return count


def _assign_risk_deciles(probabilities: dict[uuid.UUID, float]) -> dict[uuid.UUID, int]:
    """1 = worst decile (lowest 30-day sale probability), 10 = best."""
    if not probabilities:
        return {}
    ranked = sorted(probabilities.items(), key=lambda kv: kv[1])
    n = len(ranked)
    return {
        unit_id: min(10, int((rank / n) * 10) + 1) for rank, (unit_id, _prob) in enumerate(ranked)
    }


def _write_series_anomalies(db: Session, run_id: uuid.UUID, orders_df: pd.DataFrame) -> int:
    """Monitors sales at *both* granularities DS-ANO-001's "per branch/segment" wording admits:
    (model, branch) - the same granularity Phase 3's demand shocks were injected into and Phase
    4's champion forecasts are keyed by, so this is what actually catches that ground truth - and
    (segment, branch) aggregates, for average-discount/average-margin operational monitoring
    where a per-model series would be too sparse to be meaningful."""
    week_start = compute_week_start(pd.Series([orders_df["at"].min()])).iloc[0]
    last_week = compute_week_start(pd.Series([orders_df["at"].max()])).iloc[0]
    n_weeks = int((last_week - week_start).days // 7) + 1
    calendar = pd.date_range(week_start, periods=n_weeks, freq="W-MON")

    orders_df = orders_df.assign(
        discount_fraction=1.0 - orders_df["negotiated_price"] / orders_df["list_price"],
        margin=orders_df["negotiated_price"] - orders_df["acquisition_cost"],
    )

    count = 0

    model_branch_pairs = list(
        orders_df[["model_id", "branch_id"]].drop_duplicates().itertuples(index=False, name=None)
    )
    if model_branch_pairs:
        model_branch_sales = build_weekly_series(
            orders_df, ["model_id", "branch_id"], "at", model_branch_pairs, week_start, n_weeks
        )
        for (model_id, branch_id), series in model_branch_sales.items():
            entity_key = f"sales::model:{model_id}::branch:{branch_id}"
            count += _detect_and_persist(db, run_id, entity_key, series, calendar)

    segment_branch_pairs = list(
        orders_df[["segment", "branch_id"]].drop_duplicates().itertuples(index=False, name=None)
    )
    if segment_branch_pairs:
        discount_series = build_weekly_mean_series(
            orders_df,
            ["segment", "branch_id"],
            "at",
            "discount_fraction",
            segment_branch_pairs,
            week_start,
            n_weeks,
        )
        margin_series = build_weekly_mean_series(
            orders_df,
            ["segment", "branch_id"],
            "at",
            "margin",
            segment_branch_pairs,
            week_start,
            n_weeks,
        )
        for series_type, series_by_key in (
            ("avg_discount", discount_series),
            ("avg_margin", margin_series),
        ):
            for (segment, branch_id), series in series_by_key.items():
                if series.isna().any():
                    continue
                entity_key = f"{series_type}::segment:{segment}::branch:{branch_id}"
                count += _detect_and_persist(db, run_id, entity_key, series, calendar)

    return count


def _detect_and_persist(
    db: Session, run_id: uuid.UUID, entity_key: str, series: pd.Series, calendar: pd.DatetimeIndex
) -> int:
    try:
        anomalies = detect_series_anomalies(series.to_numpy(dtype=float))
    except UnstableSeriesError:
        return 0
    for anomaly in anomalies:
        db.add(
            Anomaly(
                run_id=run_id,
                scope="series",
                entity_key=entity_key,
                week_start=calendar[anomaly.week_index].date(),
                observed=anomaly.observed,
                expected=anomaly.expected,
                score=anomaly.z_score,
                method="stl_zscore",
                severity=anomaly.severity,
                esd_confirmed=anomaly.esd_confirmed,
                status=ANOMALY_STATUS_NEW,
            )
        )
    return len(anomalies)


def _write_transaction_anomalies(db: Session, run_id: uuid.UUID, orders_df: pd.DataFrame) -> int:
    records = [
        AnomalyOrderRecord(
            order_id=row.order_id,
            model_id=row.model_id,
            list_price=row.list_price,
            negotiated_price=row.negotiated_price,
        )
        for row in orders_df.itertuples(index=False)
    ]
    anomalies = detect_transaction_anomalies(records, k=DEFAULT_DISCOUNT_K)
    for anomaly in anomalies:
        db.add(
            Anomaly(
                run_id=run_id,
                scope="transaction",
                entity_key=anomaly.order_id,
                week_start=None,
                observed=anomaly.observed,
                expected=anomaly.expected_floor,
                score=(anomaly.observed - anomaly.expected_floor),
                method="discount_threshold",
                severity=abs(anomaly.observed - anomaly.expected_floor)
                / max(1.0, anomaly.expected_floor),
                esd_confirmed=None,
                status=ANOMALY_STATUS_NEW,
            )
        )
    return len(anomalies)
