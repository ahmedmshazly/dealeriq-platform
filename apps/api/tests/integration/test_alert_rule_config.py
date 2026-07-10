"""Integration test: FR-065 admin rule-parameter configuration — versioned, audit-logged, and
the next evaluation uses the new parameter.

Both tests that disable `unit_aging` restore it to `enabled=True` afterward — this rule's default
state is depended on by `test_alert_rules.py`'s own dedicated test, and all integration tests
share one session-scoped testcontainers Postgres (ADR-013), so leaving it disabled would break
whichever test happens to run after this file.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.alert_rules import evaluate_unit_aging
from dealeriq_api.domain.models.alerts import AlertRule
from dealeriq_api.domain.models.audit_log import AuditLog
from tests.helpers import admin_token


def _restore_unit_aging_enabled(client: TestClient, token: str) -> None:
    client.patch(
        "/api/v1/alert-rules/unit_aging",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_updating_a_rule_threshold_is_versioned_and_audit_logged(
    client: TestClient, db_session: Session
) -> None:
    token = admin_token(client)
    before = db_session.execute(select(AlertRule).where(AlertRule.key == "unit_aging")).scalar_one()
    before_version = before.version

    resp = client.patch(
        "/api/v1/alert-rules/unit_aging",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["version"] == before_version + 1

        audit = db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "alert_rule.updated", AuditLog.entity_id == "unit_aging"
            )
        ).scalar_one()
        assert audit.before_json is not None
        assert audit.after_json is not None
        assert audit.after_json["enabled"] is False
    finally:
        _restore_unit_aging_enabled(client, token)


def test_disabling_a_rule_via_admin_config_stops_it_from_firing(
    client: TestClient, db_session: Session
) -> None:
    token = admin_token(client)
    client.patch(
        "/api/v1/alert-rules/unit_aging",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        # Any run_id is fine -- evaluate_unit_aging returns 0 immediately once the rule is
        # disabled, never touching the DB for UnitRisk rows.
        count = evaluate_unit_aging(db_session, uuid.uuid4())
        assert count == 0
    finally:
        _restore_unit_aging_enabled(client, token)


def test_unknown_rule_key_returns_404(client: TestClient) -> None:
    token = admin_token(client)
    resp = client.patch(
        "/api/v1/alert-rules/not_a_real_rule",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
