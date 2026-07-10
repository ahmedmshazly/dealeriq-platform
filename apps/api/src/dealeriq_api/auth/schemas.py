"""Pydantic request/response models for auth, users, roles, permissions, audit log."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserCreateRequest(BaseModel):
    email: EmailStr
    role_key: str


class UserCreateResponse(BaseModel):
    id: uuid.UUID
    email: str
    role_key: str
    temporary_password: str


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    role_key: str | None = None
    unlock: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role_key: str
    is_active: bool
    must_change_password: bool
    locked_until: datetime | None

    @classmethod
    def from_model(cls, user: Any) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            role_key=user.role.key,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            locked_until=user.locked_until,
        )


class RoleResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str


class PermissionMatrixEntry(BaseModel):
    role_key: str
    role_name: str
    permissions: list[str]


class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
