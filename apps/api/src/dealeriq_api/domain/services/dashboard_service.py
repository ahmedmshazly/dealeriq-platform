"""Manager and Sales dashboard aggregation (FR-050, FR-051). Each function composes several
already-persisted analytics/operational outputs into one summary payload - purpose-built summary
queries, not calls into the existing detail-view routes, whose response shapes serve a different
need (full heatmap cell membership, full anomaly lists) than a dashboard's aggregate counts.
"""

import dataclasses
import uuid
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_analytics.forecasting.series import compute_week_start
from dealeriq_api.domain.models.alerts import Alert, AlertStatus, Notification
from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus
from dealeriq_api.domain.models.customer_analytics import LeadScore
from dealeriq_api.domain.models.inventory_intel import Anomaly, InventoryIntel, UnitRisk
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import Order, OrderEvent, OrderStatus
from dealeriq_api.domain.reports.sales_summary import (
    ModelRevenue,
    month_bounds,
    monthly_sales_by_salesperson,
    top_bottom_models,
)


def _latest_succeeded_run_id(db: Session, job_name: str) -> uuid.UUID | None:
    row = db.execute(
        select(AnalyticsRun.id)
        .where(AnalyticsRun.job_name == job_name, AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


@dataclasses.dataclass(frozen=True)
class SalesVsForecastPoint:
    week_start: date
    actual: float
    yhat: float | None
    yhat_lo80: float | None
    yhat_hi80: float | None


def _sales_vs_forecast(db: Session, month: date) -> list[SalesVsForecastPoint]:
    start, end = month_bounds(month)

    order_rows = db.execute(
        select(Order.negotiated_price, OrderEvent.at)
        .select_from(Order)
        .join(OrderEvent, OrderEvent.order_id == Order.id)
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.to_status == OrderStatus.DELIVERED.value,
            OrderEvent.at >= start,
            OrderEvent.at < end,
        )
    ).all()
    actual_by_week: dict[date, float] = {}
    if order_rows:
        df = pd.DataFrame([{"price": float(r.negotiated_price), "at": r.at} for r in order_rows])
        df["week"] = compute_week_start(df["at"])
        weekly = df.groupby("week")["price"].sum()
        actual_by_week = {ts.date(): float(v) for ts, v in weekly.items()}

    forecast_by_week: dict[date, tuple[float, float, float]] = {}
    forecast_run_id = _latest_succeeded_run_id(db, "forecast")
    if forecast_run_id is not None:
        forecast_rows = db.execute(
            select(
                Forecast.week_start,
                func.sum(Forecast.yhat),
                func.sum(Forecast.yhat_lo80),
                func.sum(Forecast.yhat_hi80),
            )
            .where(
                Forecast.run_id == forecast_run_id,
                Forecast.series_key.like("model:%"),
                Forecast.week_start >= start,
                Forecast.week_start < end,
            )
            .group_by(Forecast.week_start)
        ).all()
        forecast_by_week = {
            row[0]: (float(row[1]), float(row[2]), float(row[3])) for row in forecast_rows
        }

    all_weeks = sorted(set(actual_by_week) | set(forecast_by_week))
    points = []
    for week in all_weeks:
        forecast = forecast_by_week.get(week)
        points.append(
            SalesVsForecastPoint(
                week_start=week,
                actual=actual_by_week.get(week, 0.0),
                yhat=forecast[0] if forecast else None,
                yhat_lo80=forecast[1] if forecast else None,
                yhat_hi80=forecast[2] if forecast else None,
            )
        )
    return points


def _inventory_health_summary(db: Session) -> tuple[dict[str, int], int]:
    """Returns (ABC×XYZ cell counts, aging unit count) from the latest succeeded inventory run."""
    run_id = _latest_succeeded_run_id(db, "inventory")
    if run_id is None:
        return {}, 0
    cell_rows = db.execute(
        select(InventoryIntel.abc, InventoryIntel.xyz, func.count())
        .where(InventoryIntel.run_id == run_id)
        .group_by(InventoryIntel.abc, InventoryIntel.xyz)
    ).all()
    cells = {f"{row[0]}-{row[1]}": row[2] for row in cell_rows}
    aging_count = db.execute(
        select(func.count())
        .select_from(UnitRisk)
        .where(UnitRisk.run_id == run_id, UnitRisk.is_aging.is_(True))
    ).scalar_one()
    return cells, aging_count


def _open_anomaly_count(db: Session) -> int:
    run_id = _latest_succeeded_run_id(db, "inventory")
    if run_id is None:
        return 0
    return db.execute(
        select(func.count())
        .select_from(Anomaly)
        .where(Anomaly.run_id == run_id, Anomaly.status == "new")
    ).scalar_one()


def _unacknowledged_alert_count(db: Session, user_id: uuid.UUID) -> int:
    """Mirrors `routes/alerts.py`'s own per-user notification scoping exactly - the same query
    shape, purpose-built here to avoid an internal HTTP round-trip."""
    return db.execute(
        select(func.count())
        .select_from(Alert)
        .join(Notification, Notification.alert_id == Alert.id)
        .where(Notification.user_id == user_id, Alert.status == AlertStatus.OPEN)
    ).scalar_one()


@dataclasses.dataclass(frozen=True)
class ManagerDashboard:
    month: date
    sales_vs_forecast: list[SalesVsForecastPoint]
    top_models: list[ModelRevenue]
    bottom_models: list[ModelRevenue]
    inventory_abc_xyz_counts: dict[str, int]
    aging_unit_count: int
    open_anomaly_count: int
    unacknowledged_alert_count: int


def manager_dashboard(
    db: Session, user_id: uuid.UUID, *, as_of: datetime | None = None
) -> ManagerDashboard:
    as_of = as_of or datetime.now(UTC)
    month = as_of.date()
    start, end = month_bounds(month)

    top_models, bottom_models = top_bottom_models(db, window_start=start, window_end=end)
    cells, aging_count = _inventory_health_summary(db)

    return ManagerDashboard(
        month=start,
        sales_vs_forecast=_sales_vs_forecast(db, month),
        top_models=top_models,
        bottom_models=bottom_models,
        inventory_abc_xyz_counts=cells,
        aging_unit_count=aging_count,
        open_anomaly_count=_open_anomaly_count(db),
        unacknowledged_alert_count=_unacknowledged_alert_count(db, user_id),
    )


@dataclasses.dataclass(frozen=True)
class RankedLead:
    lead_id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    status: str
    conversion_probability: float | None


@dataclasses.dataclass(frozen=True)
class SalesDashboard:
    open_leads: list[RankedLead]
    my_sales_this_month: float
    my_target: float
    unacknowledged_alert_count: int


def sales_dashboard(
    db: Session,
    user_id: uuid.UUID,
    *,
    default_target: float,
    as_of: datetime | None = None,
) -> SalesDashboard:
    as_of = as_of or datetime.now(UTC)
    month = as_of.date()

    latest_scoring_run_id = _latest_succeeded_run_id(db, "lead_scoring")
    scores_by_lead_id: dict[uuid.UUID, float] = {}
    if latest_scoring_run_id is not None:
        score_rows = db.execute(
            select(LeadScore.lead_id, LeadScore.conversion_probability).where(
                LeadScore.run_id == latest_scoring_run_id
            )
        ).all()
        scores_by_lead_id = {row.lead_id: row.conversion_probability for row in score_rows}

    lead_rows = (
        db.execute(
            select(Lead).where(
                Lead.owner_id == user_id, Lead.status.notin_([LeadStatus.WON, LeadStatus.LOST])
            )
        )
        .scalars()
        .all()
    )
    ranked = sorted(
        (
            RankedLead(
                lead_id=lead.id,
                customer_id=lead.customer_id,
                model_id=lead.model_id,
                status=lead.status.value,
                conversion_probability=scores_by_lead_id.get(lead.id),
            )
            for lead in lead_rows
        ),
        key=lambda r: (r.conversion_probability is None, -(r.conversion_probability or 0.0)),
    )

    return SalesDashboard(
        open_leads=ranked,
        my_sales_this_month=monthly_sales_by_salesperson(db, user_id, month),
        my_target=default_target,
        unacknowledged_alert_count=_unacknowledged_alert_count(db, user_id),
    )
