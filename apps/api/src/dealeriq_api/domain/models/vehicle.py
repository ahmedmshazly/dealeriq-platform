"""VehicleModel, VehicleUnit, and the append-only StockMovement ledger (FR-020/021, DAT-003).

Unit status is DERIVED from the ledger by application code (inventory_service.py) - the
`status` column is a materialized convenience for fast filtering, but the ledger is the source
of truth; every status change is accompanied by a stock_movements row in the same transaction.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dealeriq_api.domain.base import Base, IdMixin


class UnitStatus(enum.StrEnum):
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    SOLD = "sold"
    TRANSFERRED = "transferred"


class MovementType(enum.StrEnum):
    RECEIPT = "receipt"
    RESERVATION = "reservation"
    SALE = "sale"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class VehicleModel(IdMixin, Base):
    __tablename__ = "vehicle_models"

    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60))
    trim: Mapped[str | None] = mapped_column(String(60), default=None)
    segment: Mapped[str] = mapped_column(String(40))
    list_price: Mapped[float] = mapped_column(Numeric(10, 2))


class VehicleUnit(IdMixin, Base):
    __tablename__ = "vehicle_units"

    vin: Mapped[str] = mapped_column(String(17), unique=True)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_models.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[UnitStatus] = mapped_column(
        Enum(UnitStatus, native_enum=False, length=20), default=UnitStatus.IN_STOCK
    )
    acquisition_date: Mapped[date]
    acquisition_cost: Mapped[float] = mapped_column(Numeric(10, 2))

    model: Mapped[VehicleModel] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_unit_id_occurred_at", "unit_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_units.id"))
    type: Mapped[MovementType] = mapped_column(Enum(MovementType, native_enum=False, length=20))
    from_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id"), default=None
    )
    to_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), default=None)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    reason: Mapped[str | None] = mapped_column(String(500), default=None)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
