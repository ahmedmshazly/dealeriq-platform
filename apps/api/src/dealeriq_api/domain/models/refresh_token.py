"""RefreshToken - rotation-with-reuse-detection (ADR-019).

Only a SHA-256 hash of the raw token is ever persisted. `replaced_by` chains a token to the one
that replaced it on rotation; reuse of an already-`revoked_at`/replaced token indicates theft and
triggers revocation of the whole family (auth/tokens.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id"), default=None
    )
