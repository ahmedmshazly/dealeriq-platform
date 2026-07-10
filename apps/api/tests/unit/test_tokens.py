import time
import uuid

import jwt
import pytest

from dealeriq_api.auth.tokens import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    issue_refresh_token,
)
from dealeriq_api.core.config import get_settings


def test_access_token_round_trips_claims() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role_key="admin")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "admin"
    assert "jti" in claims
    assert "exp" in claims


def test_access_token_carries_kid_header_for_rotation() -> None:
    token = create_access_token(user_id=uuid.uuid4(), role_key="admin")
    header = jwt.get_unverified_header(token)
    assert header["kid"] == get_settings().jwt_key_id


def test_decode_rejects_a_token_signed_with_an_unknown_key() -> None:
    bad_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "admin"},
        "some-other-secret-that-is-long-enough-to-avoid-a-warning",
        algorithm="HS256",
        headers={"kid": "not-a-real-key"},
    )
    with pytest.raises(TokenError):
        decode_access_token(bad_token)


def test_decode_rejects_an_expired_token() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "admin", "exp": time.time() - 10},
        settings.jwt_secret_key,
        algorithm="HS256",
        headers={"kid": settings.jwt_key_id},
    )
    with pytest.raises(TokenError):
        decode_access_token(expired)


def test_decode_rejects_a_malformed_token() -> None:
    with pytest.raises(TokenError):
        decode_access_token("not-a-jwt-at-all")


def test_refresh_token_hash_is_deterministic_and_never_equals_the_raw_value() -> None:
    issued = issue_refresh_token()
    assert hash_refresh_token(issued.raw) == issued.token_hash
    assert issued.token_hash != issued.raw


def test_refresh_tokens_are_unique() -> None:
    a = issue_refresh_token()
    b = issue_refresh_token()
    assert a.raw != b.raw
    assert a.token_hash != b.token_hash
