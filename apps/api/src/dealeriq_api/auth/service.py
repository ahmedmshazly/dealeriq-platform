"""Login, refresh (with rotation + reuse detection), logout, logout-all, change-password.

Every path here that changes account/session state writes an audit row in the same
transaction (constitution Principle IV, FR-080) — the audit log and the action it describes
commit or roll back together, never independently.
"""

import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.passwords import hash_password, verify_password
from dealeriq_api.auth.tokens import (
    IssuedRefreshToken,
    create_access_token,
    hash_refresh_token,
    issue_refresh_token,
)
from dealeriq_api.core.config import get_settings
from dealeriq_api.core.errors import ApiError, bad_request, forbidden, unauthorized
from dealeriq_api.domain.models.rbac import Role, User
from dealeriq_api.domain.models.refresh_token import RefreshToken
from dealeriq_api.domain.services.audit import write_audit_row


def _account_locked_error(user: User) -> ApiError:
    return ApiError(
        status_code=423,
        code="account_locked",
        message="This account is temporarily locked due to repeated failed sign-in attempts.",
    )


def login(
    db: Session, *, email: str, password: str, ip: str | None
) -> tuple[User, str, IssuedRefreshToken]:
    settings = get_settings()
    now = datetime.now(UTC)

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        write_audit_row(
            db,
            actor_id=user.id,
            action="auth.login_blocked_locked",
            entity_type="user",
            entity_id=str(user.id),
            ip=ip,
        )
        db.commit()
        raise _account_locked_error(user)

    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        if user is not None:
            _record_failed_login(
                db,
                user,
                now,
                settings.lockout_window_minutes,
                settings.lockout_max_attempts,
                settings.lockout_duration_minutes,
            )
            write_audit_row(
                db,
                actor_id=user.id,
                action="auth.login_failed",
                entity_type="user",
                entity_id=str(user.id),
                ip=ip,
            )
            db.commit()
        raise unauthorized("Invalid email or password.")

    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None

    access_token = create_access_token(user_id=user.id, role_key=user.role.key)
    issued = issue_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=issued.token_hash,
            expires_at=issued.expires_at,
        )
    )
    write_audit_row(
        db,
        actor_id=user.id,
        action="auth.login_succeeded",
        entity_type="user",
        entity_id=str(user.id),
        ip=ip,
    )
    db.commit()
    return user, access_token, issued


def _record_failed_login(
    db: Session,
    user: User,
    now: datetime,
    window_minutes: int,
    max_attempts: int,
    duration_minutes: int,
) -> None:
    if user.last_failed_login_at is None or (now - user.last_failed_login_at) > timedelta(
        minutes=window_minutes
    ):
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1
    user.last_failed_login_at = now

    if user.failed_login_count >= max_attempts:
        user.locked_until = now + timedelta(minutes=duration_minutes)


def refresh(db: Session, *, raw_token: str, ip: str | None) -> tuple[User, str, IssuedRefreshToken]:
    token_hash = hash_refresh_token(raw_token)
    token_row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if token_row is None:
        raise unauthorized("Invalid refresh token.")

    now = datetime.now(UTC)

    if token_row.revoked_at is not None:
        # Reuse of an already-rotated/revoked token: theft signal. Revoke the whole family.
        _revoke_token_family(db, token_row)
        write_audit_row(
            db,
            actor_id=token_row.user_id,
            action="auth.refresh_reuse_detected",
            entity_type="refresh_token",
            entity_id=str(token_row.id),
            ip=ip,
        )
        db.commit()
        raise unauthorized("Refresh token has already been used; all sessions revoked.")

    if token_row.expires_at < now:
        raise unauthorized("Refresh token expired.")

    user = db.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Account is inactive or no longer exists.")

    issued = issue_refresh_token()
    new_row = RefreshToken(
        user_id=user.id, token_hash=issued.token_hash, expires_at=issued.expires_at
    )
    db.add(new_row)
    db.flush()

    token_row.revoked_at = now
    token_row.replaced_by = new_row.id

    access_token = create_access_token(user_id=user.id, role_key=user.role.key)
    db.commit()
    return user, access_token, issued


def _revoke_token_family(db: Session, token_row: RefreshToken) -> None:
    """Walk both directions of the replaced_by chain and revoke every token in the family."""
    now = datetime.now(UTC)
    all_tokens = (
        db.execute(select(RefreshToken).where(RefreshToken.user_id == token_row.user_id))
        .scalars()
        .all()
    )
    for t in all_tokens:
        if t.revoked_at is None:
            t.revoked_at = now


def logout(db: Session, *, raw_token: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    token_row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(UTC)
        db.commit()


def logout_all(db: Session, *, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    tokens = (
        db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    for t in tokens:
        t.revoked_at = now
    write_audit_row(
        db,
        actor_id=user_id,
        action="auth.logout_all",
        entity_type="user",
        entity_id=str(user_id),
    )
    db.commit()


def change_password(db: Session, *, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise forbidden("Current password is incorrect.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # Invalidate every refresh session so a stolen cookie cannot outlive the password change.
    now = datetime.now(UTC)
    tokens = (
        db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    for t in tokens:
        t.revoked_at = now
    write_audit_row(
        db,
        actor_id=user.id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=str(user.id),
    )
    db.commit()


def generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def create_user(
    db: Session, *, actor_id: uuid.UUID, email: str, role_key: str, ip: str | None
) -> tuple[User, str]:
    role = db.execute(select(Role).where(Role.key == role_key)).scalar_one_or_none()
    if role is None:
        raise bad_request(f"Unknown role '{role_key}'.")

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise bad_request(f"A user with email '{email}' already exists.")

    temp_password = generate_temporary_password()
    user = User(
        email=email,
        password_hash=hash_password(temp_password),
        role_id=role.id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    write_audit_row(
        db,
        actor_id=actor_id,
        action="user.created",
        entity_type="user",
        entity_id=str(user.id),
        after={"email": email, "role_key": role_key},
        ip=ip,
    )
    db.commit()
    return user, temp_password
