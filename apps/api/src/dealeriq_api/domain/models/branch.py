"""Branch - dealership location (SRS §7)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class Branch(IdMixin, Base):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
