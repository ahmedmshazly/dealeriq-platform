"""AlertRule, Alert, Notification - Phase 6's alert-rule engine (FR-060..065). Schema per SRS
§7's representative-resources list verbatim.

Unlike Phase 4/5's analytics tables (DAT-003, never touched by transactional code), `alerts` and
`notifications` are operational tables mutated by application code as alerts move through their
lifecycle - that's correct and expected, not a DAT-003 violation, since DAT-003 is specifically
about the analytics-vs-transactional boundary and these tables are neither: they're a
notification concern that reads from both sides.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class AlertSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(enum.StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertRule(IdMixin, Base):
    __tablename__ = "alert_rules"

    key: Mapped[str] = mapped_column(String(30), unique=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, native_enum=False, length=20)
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)


class Alert(IdMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_dedup_key", "status", "dedup_key"),
        # FR-062: at most one non-RESOLVED alert per (rule_key, dedup_key).
        Index(
            "uq_alerts_open_rule_dedup",
            "rule_key",
            "dedup_key",
            unique=True,
            postgresql_where=text("status <> 'RESOLVED'"),
        ),
    )

    rule_key: Mapped[str] = mapped_column(String(30))
    dedup_key: Mapped[str] = mapped_column(String(255))
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, native_enum=False, length=20)
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, native_enum=False, length=20), default=AlertStatus.OPEN
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id_read_at", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"))
    channel: Mapped[str] = mapped_column(String(20))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
