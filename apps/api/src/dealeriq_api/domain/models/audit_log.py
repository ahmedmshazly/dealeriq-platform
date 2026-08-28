"""AuditLog - append-only (constitution Principle IV, DAT-003, FR-080/081).

Rows are inserted, never mutated or deleted. No `updated_at` column - there is no such thing as
updating an audit row.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity_type_at", "entity_type", "at"),
        Index("ix_audit_log_actor_id_at", "actor_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(64), default=None)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    ip: Mapped[str | None] = mapped_column(String(45), default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
