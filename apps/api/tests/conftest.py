"""Integration test infrastructure (ADR-013): a real, ephemeral Postgres via
testcontainers-python, migrated once per test session with Alembic, then a fresh SQLAlchemy
session per test. Tests use randomized/unique test data (emails, etc.) rather than relying on
an empty table per test, since the container - and its seed data (roles/permissions/bootstrap
admin) - is shared across the whole test session for speed.
"""

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

API_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16") as postgres:
        url = postgres.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
        env = os.environ.copy()
        env["DATABASE_URL"] = url
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API_ROOT,
            env=env,
            check=True,
        )
        yield url


@pytest.fixture(scope="session")
def engine(postgres_url: str):  # noqa: ANN201
    eng = create_engine(postgres_url)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:  # noqa: ANN001
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN001, ANN201
    """A TestClient wired to the testcontainers Postgres instead of the dev docker-compose
    instance, via FastAPI's dependency-override mechanism."""
    from fastapi.testclient import TestClient

    from dealeriq_api.core.db import get_db
    from dealeriq_api.core.limiter import limiter
    from dealeriq_api.main import app

    # Tests exercise login far more than 10x/minute (API-003's real-world limit); disable the
    # rate limiter for the test client rather than weakening the production limit.
    limiter.enabled = False

    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override_get_db() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
