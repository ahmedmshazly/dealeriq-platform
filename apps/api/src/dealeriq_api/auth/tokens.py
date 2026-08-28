"""JWT access tokens (PyJWT, ADR-010) and opaque rotating refresh tokens (ADR-019).

Access token claims are minimal per NFR-002: `sub` (user id), `role` (role key), `exp`, `jti`.
The `kid` header names the signing key so rotation is possible later without invalidating
already-issued tokens signed under a previous key (only one key exists today - `core.config`'s
`jwt_key_id`/`jwt_secret_key` - but the lookup is already keyed by `kid` rather than assuming a
single global secret, per ADR-010).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from dealeriq_api.core.config import get_settings

ALGORITHM = "HS256"


class TokenError(Exception):
    pass


def _signing_keys() -> dict[str, str]:
    settings = get_settings()
    return {settings.jwt_key_id: settings.jwt_secret_key}


def create_access_token(*, user_id: uuid.UUID, role_key: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role_key,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        claims,
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
        headers={"kid": settings.jwt_key_id},
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise TokenError("Malformed token.") from exc

    kid = unverified_header.get("kid")
    key = _signing_keys().get(kid) if kid else None
    if key is None:
        raise TokenError("Unknown signing key.")

    try:
        return jwt.decode(token, key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token.") from exc


@dataclass
class IssuedRefreshToken:
    raw: str
    token_hash: str
    expires_at: datetime


def issue_refresh_token() -> IssuedRefreshToken:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    return IssuedRefreshToken(
        raw=raw,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
    )


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
