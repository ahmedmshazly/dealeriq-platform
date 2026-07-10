"""SQLAlchemy 2.0 typed declarative base shared by every domain model (ADR-011).

Alembic's autogenerate (ADR-011: draft-then-review policy) targets `Base.metadata` via
alembic/env.py.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdMixin:
    """UUID primary key + created_at/updated_at, per SRS §7 ("all tables have id UUID,
    created_at, updated_at")."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
