"""The order lifecycle: create (draft) -> submit (auto-approve or pending_approval) -> approve
(atomic unit reservation) -> deliver (unit sold) -> cancel (releases a reservation, mandatory
reason). FR-040..045.

Approving an order and reserving its unit happen in one DB transaction, with the unit row
locked (`SELECT ... FOR UPDATE`) so two concurrent approval attempts on the same unit cannot
both succeed — the loser gets a 409 conflict, never a double-booked unit.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.auth.ownership import assert_owner_or_permission
from dealeriq_api.core.config import get_settings
from dealeriq_api.core.errors import bad_request, conflict, not_found
from dealeriq_api.domain.alert_rules import evaluate_discount_approval
from dealeriq_api.domain.audit import write_audit_row
from dealeriq_api.domain.models.order import Order, OrderEvent, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import (
    MovementType,
    StockMovement,
    UnitStatus,
    VehicleModel,
    VehicleUnit,
)


def create_order(
    db: Session,
    *,
    actor_id: uuid.UUID,
    customer_id: uuid.UUID,
    unit_id: uuid.UUID,
    salesperson_id: uuid.UUID,
    negotiated_price: float,
    discount: float,
    payment_type: PaymentType,
    ip: str | None,
) -> Order:
    unit = db.get(VehicleUnit, unit_id)
    if unit is None:
        raise bad_request(f"Unknown vehicle unit '{unit_id}'.")
    if unit.status != UnitStatus.IN_STOCK:
        raise conflict(f"Unit is not available for order (status: {unit.status.value}).")

    order = Order(
        customer_id=customer_id,
        unit_id=unit_id,
        salesperson_id=salesperson_id,
        negotiated_price=negotiated_price,
        discount=discount,
        payment_type=payment_type,
        status=OrderStatus.DRAFT,
    )
    db.add(order)
    db.flush()
    db.add(
        OrderEvent(
            order_id=order.id,
            from_status="",
            to_status=OrderStatus.DRAFT.value,
            actor_id=actor_id,
            at=datetime.now(UTC),
        )
    )
    write_audit_row(
        db,
        actor_id=actor_id,
        action="order.created",
        entity_type="order",
        entity_id=str(order.id),
        after={"unit_id": str(unit_id), "negotiated_price": str(negotiated_price)},
        ip=ip,
    )
    db.commit()
    return order


def _discount_fraction(db: Session, order: Order) -> float:
    unit = db.get(VehicleUnit, order.unit_id)
    model = db.get(VehicleModel, unit.model_id) if unit else None
    list_price = float(model.list_price) if model else 0.0
    if list_price <= 0:
        return 0.0
    return float(order.discount) / list_price


def _reserve_unit(db: Session, *, order: Order, actor_id: uuid.UUID) -> None:
    """Locks the unit row, verifies it's still available, reserves it, and writes the ledger
    row — all inside the caller's transaction."""
    unit = db.execute(
        select(VehicleUnit).where(VehicleUnit.id == order.unit_id).with_for_update()
    ).scalar_one()
    if unit.status != UnitStatus.IN_STOCK:
        raise conflict(
            f"Unit is no longer available (status: {unit.status.value}) — cannot approve."
        )
    unit.status = UnitStatus.RESERVED
    db.add(
        StockMovement(
            unit_id=unit.id,
            type=MovementType.RESERVATION,
            actor_id=actor_id,
            occurred_at=datetime.now(UTC),
        )
    )


def submit_order(db: Session, *, current_user: User, order_id: uuid.UUID, ip: str | None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    assert_owner_or_permission(
        db=db,
        current_user=current_user,
        any_permission_key="orders:manage_any",
        owner_id=order.salesperson_id,
    )
    if order.status != OrderStatus.DRAFT:
        raise bad_request(f"Only a draft order can be submitted (current: {order.status.value}).")

    settings = get_settings()
    fraction = _discount_fraction(db, order)
    before = order.status
    now = datetime.now(UTC)

    if fraction <= settings.order_approval_discount_threshold:
        order.status = OrderStatus.APPROVED
        _reserve_unit(db, order=order, actor_id=current_user.id)
    else:
        order.status = OrderStatus.PENDING_APPROVAL
        # FR-060's transactional trigger case: rule (e) fires inline, in this same
        # transaction, reusing the exact fraction/threshold comparison above (spec.md's
        # Assumptions) so the alert and the approval requirement can never drift apart.
        evaluate_discount_approval(db, order, fraction)

    db.add(
        OrderEvent(
            order_id=order.id,
            from_status=before.value,
            to_status=order.status.value,
            actor_id=current_user.id,
            at=now,
        )
    )
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="order.submitted",
        entity_type="order",
        entity_id=str(order.id),
        before={"status": before.value},
        after={"status": order.status.value, "discount_fraction": fraction},
        ip=ip,
    )
    db.commit()
    return order


def approve_order(db: Session, *, current_user: User, order_id: uuid.UUID, ip: str | None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise bad_request(
            f"Only a pending_approval order can be approved (current: {order.status.value})."
        )

    before = order.status
    order.status = OrderStatus.APPROVED
    _reserve_unit(db, order=order, actor_id=current_user.id)

    db.add(
        OrderEvent(
            order_id=order.id,
            from_status=before.value,
            to_status=order.status.value,
            actor_id=current_user.id,
            at=datetime.now(UTC),
        )
    )
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="order.approved",
        entity_type="order",
        entity_id=str(order.id),
        before={"status": before.value},
        after={"status": order.status.value},
        ip=ip,
    )
    db.commit()
    return order


def deliver_order(db: Session, *, current_user: User, order_id: uuid.UUID, ip: str | None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    assert_owner_or_permission(
        db=db,
        current_user=current_user,
        any_permission_key="orders:manage_any",
        owner_id=order.salesperson_id,
    )
    if order.status != OrderStatus.APPROVED:
        raise bad_request(
            f"Only an approved order can be delivered (current: {order.status.value})."
        )

    unit = db.execute(
        select(VehicleUnit).where(VehicleUnit.id == order.unit_id).with_for_update()
    ).scalar_one()
    before = order.status
    now = datetime.now(UTC)
    unit.status = UnitStatus.SOLD
    order.status = OrderStatus.DELIVERED
    db.add(
        StockMovement(
            unit_id=unit.id, type=MovementType.SALE, actor_id=current_user.id, occurred_at=now
        )
    )
    db.add(
        OrderEvent(
            order_id=order.id,
            from_status=before.value,
            to_status=order.status.value,
            actor_id=current_user.id,
            at=now,
        )
    )
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="order.delivered",
        entity_type="order",
        entity_id=str(order.id),
        before={"status": before.value},
        after={"status": order.status.value},
        ip=ip,
    )
    db.commit()
    return order


def cancel_order(
    db: Session,
    *,
    current_user: User,
    order_id: uuid.UUID,
    reason: str,
    ip: str | None,
) -> Order:
    if not reason or not reason.strip():
        raise bad_request("A reason is required to cancel an order (FR-045).")

    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    assert_owner_or_permission(
        db=db,
        current_user=current_user,
        any_permission_key="orders:manage_any",
        owner_id=order.salesperson_id,
    )
    if order.status not in (OrderStatus.APPROVED, OrderStatus.PENDING_APPROVAL):
        raise bad_request(f"Cannot cancel an order in status '{order.status.value}'.")

    before = order.status
    now = datetime.now(UTC)

    if order.status == OrderStatus.APPROVED:
        unit = db.execute(
            select(VehicleUnit).where(VehicleUnit.id == order.unit_id).with_for_update()
        ).scalar_one()
        unit.status = UnitStatus.IN_STOCK
        db.add(
            StockMovement(
                unit_id=unit.id,
                type=MovementType.ADJUSTMENT,
                actor_id=current_user.id,
                reason=f"Order cancelled: {reason}",
                occurred_at=now,
            )
        )

    order.status = OrderStatus.CANCELLED
    db.add(
        OrderEvent(
            order_id=order.id,
            from_status=before.value,
            to_status=order.status.value,
            actor_id=current_user.id,
            reason=reason,
            at=now,
        )
    )
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="order.cancelled",
        entity_type="order",
        entity_id=str(order.id),
        before={"status": before.value},
        after={"status": order.status.value, "reason": reason},
        ip=ip,
    )
    db.commit()
    return order


def list_orders(
    db: Session,
    *,
    salesperson_id: uuid.UUID | None,
    status: OrderStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Order], int]:
    stmt = select(Order)
    count_stmt = select(func.count()).select_from(Order)
    if salesperson_id is not None:
        stmt = stmt.where(Order.salesperson_id == salesperson_id)
        count_stmt = count_stmt.where(Order.salesperson_id == salesperson_id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
        count_stmt = count_stmt.where(Order.status == status)

    total = db.execute(count_stmt).scalar_one()
    rows = (
        db.execute(stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(rows), total


def order_margin(db: Session, order: Order) -> float:
    unit = db.get(VehicleUnit, order.unit_id)
    acquisition_cost = float(unit.acquisition_cost) if unit else 0.0
    return float(order.negotiated_price) - acquisition_cost


def order_timeline(db: Session, order_id: uuid.UUID) -> list[OrderEvent]:
    """FR-044: status changes, actor, timestamp — chronological."""
    return list(
        db.execute(
            select(OrderEvent).where(OrderEvent.order_id == order_id).order_by(OrderEvent.at)
        )
        .scalars()
        .all()
    )
