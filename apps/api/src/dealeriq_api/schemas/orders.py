"""Request/response models for orders (FR-040..045)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType


class OrderCreateRequest(BaseModel):
    customer_id: uuid.UUID
    unit_id: uuid.UUID
    salesperson_id: uuid.UUID
    negotiated_price: float = Field(gt=0)
    discount: float = Field(ge=0, default=0)
    payment_type: PaymentType


class OrderCancelRequest(BaseModel):
    reason: str = Field(min_length=1)


class OrderResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    unit_id: uuid.UUID
    salesperson_id: uuid.UUID
    negotiated_price: float
    discount: float
    payment_type: PaymentType
    status: OrderStatus
    margin: float | None = None  # only populated when the caller has orders:view_margin

    @classmethod
    def from_model(cls, order: Order, *, margin: float | None = None) -> "OrderResponse":
        return cls(
            id=order.id,
            customer_id=order.customer_id,
            unit_id=order.unit_id,
            salesperson_id=order.salesperson_id,
            negotiated_price=float(order.negotiated_price),
            discount=float(order.discount),
            payment_type=order.payment_type,
            status=order.status,
            margin=margin,
        )


class OrderEventResponse(BaseModel):
    id: uuid.UUID
    from_status: str
    to_status: str
    actor_id: uuid.UUID | None
    reason: str | None
    at: datetime
