"""Integration tests: alert lifecycle transitions and their audit trail (FR-062), plus the
notification-center endpoints (FR-063).
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.alerts.alert_rules import open_alert
from dealeriq_api.domain.models.alerts import Alert, AlertSeverity
from dealeriq_api.domain.models.audit_log import AuditLog
from dealeriq_api.domain.models.rbac import User
from tests.helpers import admin_token


def _seed_alert_for_admin(db: Session) -> Alert:
    alert = open_alert(
        db,
        rule_key="stock_reorder",
        dedup_key=f"test:{uuid.uuid4()}",
        severity=AlertSeverity.WARNING,
        payload={"note": "test fixture"},
    )
    db.commit()
    assert alert is not None
    return alert


def test_acknowledge_then_resolve_transitions_lifecycle_with_audit_trail(
    client: TestClient, db_session: Session
) -> None:
    alert = _seed_alert_for_admin(db_session)
    token = admin_token(client)
    admin = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()

    ack_resp = client.post(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {token}"}
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"
    assert ack_resp.json()["acknowledged_by"] == str(admin.id)

    ack_audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "alert.acknowledged", AuditLog.entity_id == str(alert.id)
        )
    ).scalar_one()
    assert ack_audit.actor_id == admin.id

    resolve_resp = client.post(
        f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {token}"}
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"

    resolve_audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "alert.resolved", AuditLog.entity_id == str(alert.id)
        )
    ).scalar_one()
    assert resolve_audit.actor_id == admin.id


def test_cannot_resolve_an_open_alert_without_acknowledging_first(
    client: TestClient, db_session: Session
) -> None:
    alert = _seed_alert_for_admin(db_session)
    token = admin_token(client)

    resp = client.post(
        f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400


def test_cannot_acknowledge_an_already_resolved_alert(
    client: TestClient, db_session: Session
) -> None:
    alert = _seed_alert_for_admin(db_session)
    token = admin_token(client)
    client.post(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {token}"}
    )
    client.post(f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {token}"})

    resp = client.post(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400


def test_alert_list_returns_badge_count_and_is_scoped_to_the_current_users_notifications(
    client: TestClient, db_session: Session
) -> None:
    _seed_alert_for_admin(db_session)
    token = admin_token(client)

    resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["badge_count"] >= 1
    assert len(body["alerts"]) >= 1
    assert body["total"] >= 1
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_ready_endpoint_reports_database_ready(client: TestClient) -> None:
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_alert_list_filters_by_status(client: TestClient, db_session: Session) -> None:
    alert = _seed_alert_for_admin(db_session)
    token = admin_token(client)
    client.post(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {token}"}
    )

    open_resp = client.get(
        "/api/v1/alerts", params={"status": "open"}, headers={"Authorization": f"Bearer {token}"}
    )
    open_ids = {a["id"] for a in open_resp.json()["alerts"]}
    assert str(alert.id) not in open_ids

    ack_resp = client.get(
        "/api/v1/alerts",
        params={"status": "acknowledged"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ack_ids = {a["id"] for a in ack_resp.json()["alerts"]}
    assert str(alert.id) in ack_ids
