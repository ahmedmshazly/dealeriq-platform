"""GET/POST /users, PATCH /users/{id} (FR-004, FR-005 unlock, FR-013 gating)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth import service
from dealeriq_api.auth.admin_service import list_users, update_user
from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import (
    Page,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
)
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.models.rbac import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=Page[UserResponse])
def list_users_route(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> Page[UserResponse]:
    users, total = list_users(db, limit=limit, offset=offset)
    return Page(
        items=[UserResponse.from_model(u) for u in users], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=UserCreateResponse, status_code=201)
def create_user_route(
    body: UserCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserCreateResponse:
    ip = request.client.host if request.client else None
    user, temp_password = service.create_user(
        db, actor_id=current_user.id, email=body.email, role_key=body.role_key, ip=ip
    )
    return UserCreateResponse(
        id=user.id, email=user.email, role_key=body.role_key, temporary_password=temp_password
    )


@router.patch("/{user_id}", response_model=UserResponse)
def update_user_route(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserResponse:
    ip = request.client.host if request.client else None
    user = update_user(
        db,
        actor_id=current_user.id,
        target_id=user_id,
        is_active=body.is_active,
        role_key=body.role_key,
        unlock=body.unlock,
        ip=ip,
    )
    return UserResponse.from_model(user)
