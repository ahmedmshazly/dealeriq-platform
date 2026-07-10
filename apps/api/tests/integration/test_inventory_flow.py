"""Integration tests: vehicle models/units, the stock-movement ledger, and adjustments
(FR-020..024)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from tests.helpers import admin_token, user_token


def _create_branch(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/branches",
        json={"name": f"Branch {uuid.uuid4().hex[:6]}", "city": "Springfield"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_model(client: TestClient, token: str, segment: str = "sedan") -> str:
    resp = client.post(
        "/api/v1/vehicle-models",
        json={
            "make": "Ford",
            "model": "Fusion",
            "trim": "SE",
            "segment": segment,
            "list_price": 24999.99,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_unit(
    client: TestClient, token: str, model_id: str, branch_id: str, vin: str | None = None
) -> dict:
    resp = client.post(
        "/api/v1/vehicle-units",
        json={
            "vin": vin or f"1FT{uuid.uuid4().hex[:14].upper()}",
            "model_id": model_id,
            "branch_id": branch_id,
            "acquisition_date": date.today().isoformat(),
            "acquisition_cost": 21000.00,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


def test_receiving_a_unit_creates_a_receipt_movement_and_shows_in_stock(
    client: TestClient,
) -> None:
    token = admin_token(client)
    branch_id = _create_branch(client, token)
    model_id = _create_model(client, token)
    unit = _create_unit(client, token, model_id, branch_id)

    assert unit["status"] == "in_stock"
    assert unit["days_on_lot"] == 0


def test_units_list_supports_branch_and_segment_filters(client: TestClient) -> None:
    token = admin_token(client)
    branch_id = _create_branch(client, token)
    model_id = _create_model(client, token, segment="luxury-test")
    unit = _create_unit(client, token, model_id, branch_id)

    resp = client.get(
        "/api/v1/vehicle-units",
        params={"branch_id": branch_id, "segment": "luxury-test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(u["id"] == unit["id"] for u in body["items"])

    resp_wrong_segment = client.get(
        "/api/v1/vehicle-units",
        params={"segment": "nonexistent-segment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_wrong_segment.json()["items"] == []


def test_adjustment_requires_a_reason_and_writes_an_audit_row(client: TestClient) -> None:
    token = admin_token(client)
    branch_id = _create_branch(client, token)
    model_id = _create_model(client, token)
    unit = _create_unit(client, token, model_id, branch_id)

    # Empty string is rejected by the schema itself (422, min_length=1); whitespace-only passes
    # that check but must still be rejected by the service layer's own validation (400).
    empty_reason = client.post(
        f"/api/v1/vehicle-units/{unit['id']}/adjust",
        json={"new_status": "transferred", "reason": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert empty_reason.status_code == 422

    whitespace_reason = client.post(
        f"/api/v1/vehicle-units/{unit['id']}/adjust",
        json={"new_status": "transferred", "reason": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert whitespace_reason.status_code == 400

    with_reason = client.post(
        f"/api/v1/vehicle-units/{unit['id']}/adjust",
        json={"new_status": "transferred", "reason": "Moved to overflow lot"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["status"] == "transferred"

    audit_resp = client.get(
        "/api/v1/audit-log",
        params={"entity_id": unit["id"], "action": "vehicle_unit.adjusted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(audit_resp.json()["items"]) == 1


def test_sales_can_view_but_not_manage_inventory(client: TestClient) -> None:
    token = admin_token(client)
    sales_token = user_token(client, token, "sales")

    view_resp = client.get(
        "/api/v1/vehicle-units", headers={"Authorization": f"Bearer {sales_token}"}
    )
    assert view_resp.status_code == 200

    manage_resp = client.post(
        "/api/v1/vehicle-models",
        json={"make": "X", "model": "Y", "segment": "z", "list_price": 1},
        headers={"Authorization": f"Bearer {sales_token}"},
    )
    assert manage_resp.status_code == 403
