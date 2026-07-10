"""Customer — FR-030."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class Customer(IdMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    city: Mapped[str | None] = mapped_column(String(100), default=None)
    source_channel: Mapped[str | None] = mapped_column(String(60), default=None)
