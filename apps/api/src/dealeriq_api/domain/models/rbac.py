"""Role/Permission/RolePermission/User - the RBAC core (FR-004, FR-010..013).

Permissions are granular strings grouped into roles via RolePermission, not hardcoded per-role
branches in application code, so custom roles remain possible later without a schema change
(NFR-020) - `roles.key` is a plain unique string, not a CHECK-constrained enum, deliberately.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dealeriq_api.domain.base import Base, IdMixin


class Role(IdMixin, Base):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))

    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role")


class Permission(IdMixin, Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(String(255))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE")
    )

    role: Mapped[Role] = relationship(back_populates="permissions")
    permission: Mapped[Permission] = relationship()


class User(IdMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    must_change_password: Mapped[bool] = mapped_column(default=False)
    failed_login_count: Mapped[int] = mapped_column(default=0)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    role: Mapped[Role] = relationship()
