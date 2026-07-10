"""GET/POST /orders, POST /orders/{id}/submit|approve|deliver|cancel (FR-040..045)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import get_user_permissions, require_permission
from dealeriq_api.auth.ownership import require_any_permission
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import forbidden, not_found
from dealeriq_api.domain.models.order import Order, OrderStatus
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.order_service import (
    approve_order,
    cancel_order,
    create_order,
    deliver_order,
    list_orders,
    order_margin,
    order_timeline,
    submit_order,
)
from dealeriq_api.schemas.orders import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderEventResponse,
    OrderResponse,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _to_response(db: Session, order: Order, current_user: User) -> OrderResponse:
    granted = get_user_permissions(db, current_user.role_id)
    margin = order_margin(db, order) if "orders:view_margin" in granted else None
    return OrderResponse.from_model(order, margin=margin)


@router.get("", response_model=Page[OrderResponse])
def list_orders_route(
    salesperson_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("orders:view")),
    db: Session = Depends(get_db),
) -> Page[OrderResponse]:
    orders, total = list_orders(
        db, salesperson_id=salesperson_id, status=status, limit=limit, offset=offset
    )
    return Page(
        items=[_to_response(db, o, current_user) for o in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_route(
    order_id: uuid.UUID,
    current_user: User = Depends(require_permission("orders:view")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    return _to_response(db, order, current_user)


@router.get("/{order_id}/timeline", response_model=list[OrderEventResponse])
def order_timeline_route(
    order_id: uuid.UUID,
    _current_user: User = Depends(require_permission("orders:view")),
    db: Session = Depends(get_db),
) -> list[OrderEventResponse]:
    events = order_timeline(db, order_id)
    return [
        OrderEventResponse(
            id=e.id,
            from_status=e.from_status,
            to_status=e.to_status,
            actor_id=e.actor_id,
            reason=e.reason,
            at=e.at,
        )
        for e in events
    ]


@router.post("", response_model=OrderResponse, status_code=201)
def create_order_route(
    body: OrderCreateRequest,
    request: Request,
    current_user: User = Depends(require_any_permission("orders:manage_own", "orders:manage_any")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    granted = get_user_permissions(db, current_user.role_id)
    if "orders:manage_any" not in granted and body.salesperson_id != current_user.id:
        raise forbidden("You may only create orders attributed to yourself.")

    ip = request.client.host if request.client else None
    order = create_order(
        db,
        actor_id=current_user.id,
        customer_id=body.customer_id,
        unit_id=body.unit_id,
        salesperson_id=body.salesperson_id,
        negotiated_price=body.negotiated_price,
        discount=body.discount,
        payment_type=body.payment_type,
        ip=ip,
    )
    return _to_response(db, order, current_user)


@router.post("/{order_id}/submit", response_model=OrderResponse)
def submit_order_route(
    order_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_any_permission("orders:manage_own", "orders:manage_any")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    ip = request.client.host if request.client else None
    order = submit_order(db, current_user=current_user, order_id=order_id, ip=ip)
    return _to_response(db, order, current_user)


@router.post("/{order_id}/approve", response_model=OrderResponse)
def approve_order_route(
    order_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("orders:approve")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    ip = request.client.host if request.client else None
    order = approve_order(db, current_user=current_user, order_id=order_id, ip=ip)
    return _to_response(db, order, current_user)


@router.post("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order_route(
    order_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_any_permission("orders:manage_own", "orders:manage_any")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    ip = request.client.host if request.client else None
    order = deliver_order(db, current_user=current_user, order_id=order_id, ip=ip)
    return _to_response(db, order, current_user)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order_route(
    order_id: uuid.UUID,
    body: OrderCancelRequest,
    request: Request,
    current_user: User = Depends(require_any_permission("orders:manage_own", "orders:manage_any")),
    db: Session = Depends(get_db),
) -> OrderResponse:
    ip = request.client.host if request.client else None
    order = cancel_order(
        db, current_user=current_user, order_id=order_id, reason=body.reason, ip=ip
    )
    return _to_response(db, order, current_user)
