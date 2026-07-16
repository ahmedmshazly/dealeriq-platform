"""Application configuration, read from environment variables / .env.

See .env.example for the full documented list of variables (NFR-009).
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Intentionally obvious placeholder — allowed only when app_env == "development".
INSECURE_JWT_PLACEHOLDER = "dev-only-insecure-secret-change-me"
_MIN_JWT_SECRET_LENGTH = 32


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
    jwt_secret_key: str = INSECURE_JWT_PLACEHOLDER
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

    # Orders (FR-041): discount above this fraction of list price requires Manager+ approval.
    order_approval_discount_threshold: float = 0.05

    # Digest email (FR-064): SMTP defaults match MailHog's own listener
    # (infra/docker-compose.yml) — zero paid email service for local dev.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from_address: str = "alerts@dealeriq.dev"

    # Sales dashboard "vs. target" (FR-051, ADR-024): a single default applied uniformly to
    # every Salesperson — not a per-salesperson quota system, which is backlogged (P2).
    default_monthly_sales_target: float = 150000.0

    # DS-OPS-001 cron scheduling (ADR-004). Defaults OFF: scheduled jobs open their own DB
    # session directly from `core.db.engine`, bypassing FastAPI's `get_db` dependency-override
    # mechanism the test suite relies on to redirect every request to the ephemeral
    # testcontainers Postgres (ADR-013) — a real scheduler firing during a test run would hit
    # the *real* dev database, not the test one. Only `make dev` (and real deployments) opt in
    # via the `ENABLE_SCHEDULER=true` environment variable; the test suite never sets it, so
    # this is safe by default rather than relying on every test file remembering to disable it.
    enable_scheduler: bool = False

    @model_validator(mode="after")
    def _reject_insecure_jwt_outside_development(self) -> "Settings":
        if self.app_env == "development":
            return self
        if (
            self.jwt_secret_key == INSECURE_JWT_PLACEHOLDER
            or len(self.jwt_secret_key) < _MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong secret (length >= 32, not the "
                "dev placeholder) when APP_ENV is not 'development'."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
