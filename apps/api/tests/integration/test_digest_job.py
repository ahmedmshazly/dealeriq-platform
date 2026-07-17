"""Integration test: the daily digest job sends a real email via SMTP to MailHog —
verified against MailHog's own `GET /api/v2/search` HTTP API, not a mocked `smtplib.SMTP`
(FR-064).

MailHog is started with testcontainers (same pattern as Postgres in `conftest.py`) so CI
runners where GHA service-container port publishing is unreachable still exercise a real
SMTP round-trip. Local `docker compose` MailHog is unused by these tests.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.core.container import DockerContainer

from dealeriq_api.core.config import get_settings
from dealeriq_api.domain.alerts.alert_rules import open_alert
from dealeriq_api.domain.jobs.digest_job import run_digest_job
from dealeriq_api.domain.models.alerts import AlertSeverity, Notification
from dealeriq_api.domain.models.rbac import Role, User


@pytest.fixture(scope="module")
def mailhog_api() -> Generator[str, None, None]:
    container = DockerContainer("mailhog/mailhog:v1.0.1").with_exposed_ports(1025, 8025)
    container.start()
    try:
        host = container.get_container_host_ip()
        smtp_port = container.get_exposed_port(1025)
        api_port = container.get_exposed_port(8025)
        os.environ["SMTP_HOST"] = host
        os.environ["SMTP_PORT"] = str(smtp_port)
        get_settings.cache_clear()

        api = f"http://{host}:{api_port}/api/v2"
        for _ in range(60):
            try:
                resp = httpx.get(f"{api}/messages", timeout=2.0)
                if resp.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("MailHog did not become ready")

        yield api
    finally:
        container.stop()
        get_settings.cache_clear()


def _new_manager_user(db: Session) -> User:
    manager_role = db.execute(select(Role).where(Role.key == "manager")).scalar_one()
    user = User(
        email=f"digest-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        role_id=manager_role.id,
    )
    db.add(user)
    db.flush()
    return user


def _mailhog_messages_to(mailhog_api: str, recipient: str) -> list[dict]:
    resp = httpx.get(f"{mailhog_api}/search", params={"kind": "to", "query": recipient})
    resp.raise_for_status()
    return resp.json()["items"]


def test_digest_job_sends_one_real_email_per_subscribed_user_with_pending_alerts(
    db_session: Session,
    mailhog_api: str,
) -> None:
    user = _new_manager_user(db_session)
    alert = open_alert(
        db_session,
        rule_key="stock_reorder",
        dedup_key=f"digest-test:{uuid.uuid4()}",
        severity=AlertSeverity.WARNING,
        payload={"note": "digest test fixture"},
    )
    db_session.commit()
    assert alert is not None

    run = run_digest_job(db_session)
    assert run.status.value == "succeeded"
    assert run.metrics["emails_sent"] >= 1

    messages = _mailhog_messages_to(mailhog_api, user.email)
    assert len(messages) == 1
    assert "DealerIQ" in messages[0]["Content"]["Headers"]["Subject"][0]

    notification = db_session.execute(
        select(Notification).where(
            Notification.user_id == user.id, Notification.alert_id == alert.id
        )
    ).scalar_one()
    assert notification.emailed_at is not None


def test_digest_job_does_not_resend_to_an_already_emailed_notification(
    db_session: Session,
    mailhog_api: str,
) -> None:
    user = _new_manager_user(db_session)
    alert = open_alert(
        db_session,
        rule_key="stock_reorder",
        dedup_key=f"digest-test:{uuid.uuid4()}",
        severity=AlertSeverity.WARNING,
        payload={"note": "no-resend test fixture"},
    )
    db_session.commit()
    assert alert is not None

    run_digest_job(db_session)
    first_count = len(_mailhog_messages_to(mailhog_api, user.email))
    assert first_count == 1

    run_digest_job(db_session)
    second_count = len(_mailhog_messages_to(mailhog_api, user.email))
    assert second_count == 1  # no second email for the same, already-emailed notification


def test_digest_job_sends_no_email_for_a_user_with_zero_pending_notifications(
    db_session: Session,
    mailhog_api: str,
) -> None:
    user = _new_manager_user(db_session)
    db_session.commit()

    run_digest_job(db_session)

    assert _mailhog_messages_to(mailhog_api, user.email) == []
