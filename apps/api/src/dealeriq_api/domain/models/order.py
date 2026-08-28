"""Order + OrderEvent - the sales order lifecycle (FR-040..045)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class OrderStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentType(enum.StrEnum):
    CASH = "cash"
    FINANCE = "finance"


class Order(IdMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_salesperson_id_status", "salesperson_id", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_units.id"))
    salesperson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    negotiated_price: Mapped[float] = mapped_column(Numeric(10, 2))
    discount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, native_enum=False, length=20)
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20), default=OrderStatus.DRAFT
    )


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    reason: Mapped[str | None] = mapped_column(String(500), default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
