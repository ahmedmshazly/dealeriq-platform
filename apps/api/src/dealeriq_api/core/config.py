"""Application configuration, read from environment variables / .env.

See .env.example for the full documented list of variables (NFR-009).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://dealeriq:dealeriq@localhost:5432/dealeriq"

    cors_origins: str = "http://localhost:3000"

    # Auth (FR-001..006, ADR-009/010/019/020). jwt_secret_key MUST be overridden via .env for
    # anything beyond local dev — the default here is intentionally an obvious placeholder.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_key_id: str = "dev-1"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    refresh_cookie_name: str = "dealeriq_refresh"
    lockout_max_attempts: int = 5
    lockout_window_minutes: int = 15
    lockout_duration_minutes: int = 15

    # Bootstrap Admin (seeded by Alembic migration 0001_auth_rbac — self-registration is
    # disabled per FR-004, so a first account must exist some other way).
    bootstrap_admin_email: str = "admin@dealeriq.dev"
    bootstrap_admin_password: str = "ChangeMe123!"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
