"""Deny-by-default RBAC dependencies (FR-010, FR-011, constitution Principle III).

`require_permission("x:y")` is the ONLY sanctioned way a route declares what it needs — there is
no blanket "is Admin" bypass. A request without a valid access token gets 401; a request from an
authenticated user whose role lacks the permission gets 403 with `error.code == "forbidden"`.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.tokens import TokenError, decode_access_token
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import forbidden, password_change_required, unauthorized
from dealeriq_api.domain.models.rbac import Permission, RolePermission, User

# FR-006: accounts with must_change_password may only hit these paths until they change it.
_PASSWORD_CHANGE_ALLOWLIST = frozenset(
    {
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/me",
    }
)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise unauthorized()
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        claims = decode_access_token(token)
    except TokenError as exc:
        raise unauthorized(str(exc)) from exc

    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise unauthorized("Account is inactive or no longer exists.")

    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_ALLOWLIST:
        raise password_change_required()

    request.state.user_id = str(user.id)
    return user


def get_user_permissions(db: Session, role_id: uuid.UUID) -> set[str]:
    rows = db.execute(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    ).scalars()
    return set(rows)


def require_permission(permission_key: str) -> Callable[..., User]:
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        granted = get_user_permissions(db, current_user.role_id)
        if permission_key not in granted:
            raise forbidden(
                f"Requires permission '{permission_key}', which your role does not grant."
            )
        return current_user

    return dependency
