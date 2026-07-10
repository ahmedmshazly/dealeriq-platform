"""Lead + LeadEvent — the sales funnel (FR-031). Status transitions are validated by
`domain/lead_state_machine.py` before any write happens here."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dealeriq_api.domain.base import Base, IdMixin

if TYPE_CHECKING:
    from dealeriq_api.domain.models.customer import Customer


class LeadStatus(enum.StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    TEST_DRIVE = "test_drive"
    NEGOTIATING = "negotiating"
    WON = "won"
    LOST = "lost"


class Lead(IdMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_owner_id_status", "owner_id", "status"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_models.id"))
    budget_band: Mapped[str] = mapped_column(String(30))
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, native_enum=False, length=20), default=LeadStatus.NEW
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship()


class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    type: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(String(1000), default=None)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
