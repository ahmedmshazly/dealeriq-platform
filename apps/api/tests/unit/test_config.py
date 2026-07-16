"""Settings validation (insecure JWT rejected outside development)."""

import pytest
from pydantic import ValidationError

from dealeriq_api.core.config import INSECURE_JWT_PLACEHOLDER, Settings


def test_development_allows_placeholder_jwt_secret() -> None:
    settings = Settings(app_env="development", jwt_secret_key=INSECURE_JWT_PLACEHOLDER)
    assert settings.jwt_secret_key == INSECURE_JWT_PLACEHOLDER


def test_production_rejects_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(app_env="production", jwt_secret_key=INSECURE_JWT_PLACEHOLDER)


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(app_env="production", jwt_secret_key="too-short-to-be-safe")


def test_production_accepts_strong_jwt_secret() -> None:
    secret = "a" * 48
    settings = Settings(app_env="production", jwt_secret_key=secret)
    assert settings.jwt_secret_key == secret
