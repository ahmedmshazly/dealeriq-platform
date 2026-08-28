"""Monthly sales/margin aggregation (FR-050, FR-051, FR-054). `Order` itself has no
`delivered_at` column - delivery date is read from `OrderEvent` where `to_status="delivered"`,
matching the existing order-timeline convention (`order_service.order_timeline`) and how
`infra/seed/generate.py` itself records delivery for seeded orders.
"""

import dataclasses
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.order import Order, OrderEvent, OrderStatus
from dealeriq_api.domain.models.vehicle import VehicleModel, VehicleUnit

DELIVERED_TO_STATUS = OrderStatus.DELIVERED.value


def month_bounds(month: date) -> tuple[date, date]:
    """Returns `[start, end)` - the first day of `month`'s month and the first day of the next
    month, so a half-open `>=`/`<` range never double-counts a boundary timestamp."""
    start = month.replace(day=1)
    end = date(start.year + (1 if start.month == 12 else 0), (start.month % 12) + 1, 1)
    return start, end


@dataclasses.dataclass(frozen=True)
class ModelRevenue:
    model_id: uuid.UUID
    display_name: str
    revenue: float


def _delivered_orders_in_range(
    db: Session, start: date, end: date
) -> list[tuple[Order, VehicleUnit]]:
    rows = db.execute(
        select(Order, VehicleUnit)
        .join(OrderEvent, OrderEvent.order_id == Order.id)
        .join(VehicleUnit, VehicleUnit.id == Order.unit_id)
        .where(
            OrderEvent.to_status == DELIVERED_TO_STATUS,
            OrderEvent.at >= start,
            OrderEvent.at < end,
            Order.status == OrderStatus.DELIVERED,
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


def monthly_sales_by_branch(db: Session, month: date) -> dict[uuid.UUID, float]:
    start, end = month_bounds(month)
    totals: dict[uuid.UUID, float] = {}
    for order, unit in _delivered_orders_in_range(db, start, end):
        totals[unit.branch_id] = totals.get(unit.branch_id, 0.0) + float(order.negotiated_price)
    return totals


def monthly_sales_by_salesperson(db: Session, salesperson_id: uuid.UUID, month: date) -> float:
    start, end = month_bounds(month)
    total = db.execute(
        select(func.sum(Order.negotiated_price))
        .select_from(Order)
        .join(OrderEvent, OrderEvent.order_id == Order.id)
        .where(
            Order.salesperson_id == salesperson_id,
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.to_status == DELIVERED_TO_STATUS,
            OrderEvent.at >= start,
            OrderEvent.at < end,
        )
    ).scalar_one_or_none()
    return float(total) if total is not None else 0.0


def monthly_sales_and_margin(db: Session, month: date) -> tuple[float, float]:
    """Total revenue and total margin (`negotiated_price - acquisition_cost`) for every order
    delivered in `month`, dealership-wide - the two totals FR-054's monthly report needs."""
    start, end = month_bounds(month)
    revenue = 0.0
    margin = 0.0
    for order, unit in _delivered_orders_in_range(db, start, end):
        price = float(order.negotiated_price)
        revenue += price
        margin += price - float(unit.acquisition_cost)
    return revenue, margin


def top_bottom_models(
    db: Session, *, window_start: date, window_end: date, n: int = 5
) -> tuple[list[ModelRevenue], list[ModelRevenue]]:
    """Ranked by delivered revenue within `[window_start, window_end)`. A model with zero
    deliveries in the window is excluded entirely - it isn't "bottom," it's simply unranked."""
    rows = db.execute(
        select(
            VehicleModel.id, VehicleModel.make, VehicleModel.model, func.sum(Order.negotiated_price)
        )
        .select_from(Order)
        .join(OrderEvent, OrderEvent.order_id == Order.id)
        .join(VehicleUnit, VehicleUnit.id == Order.unit_id)
        .join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.to_status == DELIVERED_TO_STATUS,
            OrderEvent.at >= window_start,
            OrderEvent.at < window_end,
        )
        .group_by(VehicleModel.id, VehicleModel.make, VehicleModel.model)
    ).all()

    ranked = sorted(
        (
            ModelRevenue(model_id=row[0], display_name=f"{row[1]} {row[2]}", revenue=float(row[3]))
            for row in rows
        ),
        key=lambda m: m.revenue,
        reverse=True,
    )
    top = ranked[:n]
    bottom = list(reversed(ranked[-n:])) if len(ranked) > n else []
    return top, bottom
