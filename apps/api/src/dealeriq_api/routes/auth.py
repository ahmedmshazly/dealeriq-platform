"""POST /auth/login|refresh|logout|logout-all|change-password (FR-001, FR-003, FR-005, FR-006)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from dealeriq_api.auth import service
from dealeriq_api.auth.dependencies import get_current_user
from dealeriq_api.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from dealeriq_api.core.config import get_settings
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import unauthorized
from dealeriq_api.core.limiter import limiter
from dealeriq_api.domain.models.rbac import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_refresh_cookie(response: Response, raw_token: str, expires_at: datetime) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        samesite="strict",
        secure=settings.app_env != "development",
        expires=expires_at,
        path="/api/v1/auth",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login_route(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, access_token, issued = service.login(
        db, email=body.email, password=body.password, ip=_client_ip(request)
    )
    _set_refresh_cookie(response, issued.raw, issued.expires_at)
    return TokenResponse(access_token=access_token, must_change_password=user.must_change_password)


@router.post("/refresh", response_model=TokenResponse)
def refresh_route(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise unauthorized("No refresh token presented.")

    user, access_token, issued = service.refresh(db, raw_token=raw_token, ip=_client_ip(request))
    _set_refresh_cookie(response, issued.raw, issued.expires_at)
    return TokenResponse(access_token=access_token, must_change_password=user.must_change_password)


@router.post("/logout", status_code=204)
def logout_route(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        service.logout(db, raw_token=raw_token)
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")


@router.post("/logout-all", status_code=204)
def logout_all_route(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    service.logout_all(db, user_id=current_user.id)
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")


@router.get("/me", response_model=UserResponse)
def me_route(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_model(current_user)


@router.post("/change-password", status_code=204)
def change_password_route(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service.change_password(
        db,
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
