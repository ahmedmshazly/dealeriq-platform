"""Integration tests: customers (dedup warning), leads (state machine + ownership, FR-012)."""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import admin_token, create_user, usable_token, user_token


def _create_customer(
    client: TestClient, token: str, *, phone: str | None = None, email: str | None = None
) -> dict:
    resp = client.post(
        "/api/v1/customers",
        json={
            "name": f"Customer {uuid.uuid4().hex[:6]}",
            "phone": phone,
            "email": email,
            "city": "Springfield",
            "source_channel": "walk-in",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_model(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/vehicle-models",
        json={"make": "Honda", "model": "Civic", "segment": "compact", "list_price": 22000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_creating_a_customer_with_a_matching_phone_warns_but_does_not_block(
    client: TestClient,
) -> None:
    token = admin_token(client)
    phone = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
    first = _create_customer(client, token, phone=phone)
    assert first["possible_duplicate_ids"] == []

    second = _create_customer(client, token, phone=phone)
    assert second["possible_duplicate_ids"] == [first["customer"]["id"]]


def test_lead_created_new_and_invalid_transition_is_rejected(client: TestClient) -> None:
    token = admin_token(client)
    customer = _create_customer(client, token)["customer"]
    model_id = _create_model(client, token)
    admin_id, _, _ = create_user(client, token, "manager")

    lead_resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": customer["id"],
            "model_id": model_id,
            "budget_band": "20k-30k",
            "owner_id": admin_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lead_resp.status_code == 201
    lead = lead_resp.json()
    assert lead["status"] == "new"

    invalid = client.post(
        f"/api/v1/leads/{lead['id']}/transition",
        json={"target_status": "won"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invalid.status_code == 400

    valid = client.post(
        f"/api/v1/leads/{lead['id']}/transition",
        json={"target_status": "contacted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert valid.status_code == 200
    assert valid.json()["status"] == "contacted"


def test_sales_user_cannot_edit_another_sales_users_lead(client: TestClient) -> None:
    admin = admin_token(client)
    customer = _create_customer(client, admin)["customer"]
    model_id = _create_model(client, admin)

    owner_id, owner_email, owner_password = create_user(client, admin, "sales")
    _other_id, other_email, other_password = create_user(client, admin, "sales")

    owner_bearer = usable_token(client, owner_email, owner_password)
    other_bearer = usable_token(client, other_email, other_password)

    lead_resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": customer["id"],
            "model_id": model_id,
            "budget_band": "20k-30k",
            "owner_id": owner_id,
        },
        headers={"Authorization": f"Bearer {owner_bearer}"},
    )
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    # The other Sales user cannot transition a lead they don't own.
    forbidden_resp = client.post(
        f"/api/v1/leads/{lead_id}/transition",
        json={"target_status": "contacted"},
        headers={"Authorization": f"Bearer {other_bearer}"},
    )
    assert forbidden_resp.status_code == 403

    # A Manager can, though.
    manager_token = user_token(client, admin, "manager")
    manager_resp = client.post(
        f"/api/v1/leads/{lead_id}/transition",
        json={"target_status": "contacted"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_resp.status_code == 200


def test_sales_user_cannot_create_a_lead_owned_by_someone_else(client: TestClient) -> None:
    admin = admin_token(client)
    customer = _create_customer(client, admin)["customer"]
    model_id = _create_model(client, admin)

    _sales_id, sales_email, sales_password = create_user(client, admin, "sales")
    other_manager_id, _, _ = create_user(client, admin, "manager")

    sales_bearer = usable_token(client, sales_email, sales_password)

    resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": customer["id"],
            "model_id": model_id,
            "budget_band": "20k-30k",
            "owner_id": other_manager_id,
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert resp.status_code == 403
