"""Integration tests: the full order lifecycle, threshold-based approval, atomic reservation,
margin visibility, and cancellation (FR-040..045)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from tests.helpers import admin_token, create_user, login


def _create_branch(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/branches",
        json={"name": f"Branch {uuid.uuid4().hex[:6]}", "city": "Springfield"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_model(client: TestClient, token: str, list_price: float = 20000.0) -> str:
    resp = client.post(
        "/api/v1/vehicle-models",
        json={"make": "Toyota", "model": "Camry", "segment": "sedan", "list_price": list_price},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_unit(client: TestClient, token: str, model_id: str, branch_id: str) -> str:
    resp = client.post(
        "/api/v1/vehicle-units",
        json={
            "vin": f"2HG{uuid.uuid4().hex[:14].upper()}",
            "model_id": model_id,
            "branch_id": branch_id,
            "acquisition_date": date.today().isoformat(),
            "acquisition_cost": 17000.00,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_customer(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/customers",
        json={"name": f"Buyer {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["customer"]["id"]


def _setup(client: TestClient, token: str, *, list_price: float = 20000.0):
    branch_id = _create_branch(client, token)
    model_id = _create_model(client, token, list_price=list_price)
    unit_id = _create_unit(client, token, model_id, branch_id)
    customer_id = _create_customer(client, token)
    return unit_id, customer_id, model_id


def test_low_discount_order_auto_approves_and_reserves_the_unit(client: TestClient) -> None:
    token = admin_token(client)
    sales_id, sales_email, sales_password = create_user(client, token, "sales")
    sales_bearer = login(client, sales_email, sales_password).json()["access_token"]

    unit_id, customer_id, model_id = _setup(client, token, list_price=20000.0)

    create_resp = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "unit_id": unit_id,
            "salesperson_id": sales_id,
            "negotiated_price": 19500.0,
            "discount": 500.0,  # 2.5% of list price, under the 5% threshold
            "payment_type": "cash",
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert create_resp.status_code == 201
    order = create_resp.json()
    assert order["status"] == "draft"
    assert order["margin"] is None  # Sales lacks orders:view_margin

    submit_resp = client.post(
        f"/api/v1/orders/{order['id']}/submit",
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "approved"

    unit_resp = client.get(
        "/api/v1/vehicle-units",
        params={"model_id": model_id},
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    unit = next(u for u in unit_resp.json()["items"] if u["id"] == unit_id)
    assert unit["status"] == "reserved"

    deliver_resp = client.post(
        f"/api/v1/orders/{order['id']}/deliver",
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert deliver_resp.status_code == 200
    assert deliver_resp.json()["status"] == "delivered"

    unit_resp_2 = client.get(
        "/api/v1/vehicle-units",
        params={"model_id": model_id},
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    unit_2 = next(u for u in unit_resp_2.json()["items"] if u["id"] == unit_id)
    assert unit_2["status"] == "sold"


def test_high_discount_order_requires_manager_approval(client: TestClient) -> None:
    token = admin_token(client)
    sales_id, sales_email, sales_password = create_user(client, token, "sales")
    sales_bearer = login(client, sales_email, sales_password).json()["access_token"]
    manager_id, manager_email, manager_password = create_user(client, token, "manager")
    manager_bearer = login(client, manager_email, manager_password).json()["access_token"]

    unit_id, customer_id, _model_id = _setup(client, token, list_price=20000.0)

    create_resp = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "unit_id": unit_id,
            "salesperson_id": sales_id,
            "negotiated_price": 17000.0,
            "discount": 3000.0,  # 15% of list price, over the 5% threshold
            "payment_type": "finance",
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    order_id = create_resp.json()["id"]

    submit_resp = client.post(
        f"/api/v1/orders/{order_id}/submit", headers={"Authorization": f"Bearer {sales_bearer}"}
    )
    assert submit_resp.json()["status"] == "pending_approval"

    # Sales cannot approve their own pending order.
    sales_approve = client.post(
        f"/api/v1/orders/{order_id}/approve", headers={"Authorization": f"Bearer {sales_bearer}"}
    )
    assert sales_approve.status_code == 403

    manager_approve = client.post(
        f"/api/v1/orders/{order_id}/approve",
        headers={"Authorization": f"Bearer {manager_bearer}"},
    )
    assert manager_approve.status_code == 200
    assert manager_approve.json()["status"] == "approved"
    assert manager_approve.json()["margin"] == 17000.0 - 17000.0  # negotiated - acquisition_cost

    # Approving twice is rejected — the order is no longer pending_approval.
    second_approve = client.post(
        f"/api/v1/orders/{order_id}/approve",
        headers={"Authorization": f"Bearer {manager_bearer}"},
    )
    assert second_approve.status_code == 400


def test_cancelling_an_approved_order_releases_the_reservation_and_requires_a_reason(
    client: TestClient,
) -> None:
    token = admin_token(client)
    sales_id, sales_email, sales_password = create_user(client, token, "sales")
    sales_bearer = login(client, sales_email, sales_password).json()["access_token"]
    unit_id, customer_id, model_id = _setup(client, token)

    order_id = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "unit_id": unit_id,
            "salesperson_id": sales_id,
            "negotiated_price": 19800.0,
            "discount": 200.0,
            "payment_type": "cash",
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    ).json()["id"]
    client.post(
        f"/api/v1/orders/{order_id}/submit", headers={"Authorization": f"Bearer {sales_bearer}"}
    )

    no_reason = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert no_reason.status_code == 422  # min_length=1 on the schema itself

    cancel_resp = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "Customer backed out"},
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    unit_resp = client.get(
        "/api/v1/vehicle-units",
        params={"model_id": model_id},
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    unit = next(u for u in unit_resp.json()["items"] if u["id"] == unit_id)
    assert unit["status"] == "in_stock"


def test_order_timeline_records_every_status_change(client: TestClient) -> None:
    token = admin_token(client)
    sales_id, sales_email, sales_password = create_user(client, token, "sales")
    sales_bearer = login(client, sales_email, sales_password).json()["access_token"]
    unit_id, customer_id, _model_id = _setup(client, token)

    order_id = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "unit_id": unit_id,
            "salesperson_id": sales_id,
            "negotiated_price": 19800.0,
            "discount": 200.0,
            "payment_type": "cash",
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    ).json()["id"]
    client.post(
        f"/api/v1/orders/{order_id}/submit", headers={"Authorization": f"Bearer {sales_bearer}"}
    )
    client.post(
        f"/api/v1/orders/{order_id}/deliver", headers={"Authorization": f"Bearer {sales_bearer}"}
    )

    timeline = client.get(
        f"/api/v1/orders/{order_id}/timeline",
        headers={"Authorization": f"Bearer {sales_bearer}"},
    ).json()
    to_statuses = [e["to_status"] for e in timeline]
    assert to_statuses == ["draft", "approved", "delivered"]


def test_sales_cannot_create_an_order_for_someone_else(client: TestClient) -> None:
    token = admin_token(client)
    _sales_id, sales_email, sales_password = create_user(client, token, "sales")
    sales_bearer = login(client, sales_email, sales_password).json()["access_token"]
    other_id, _, _ = create_user(client, token, "sales")
    unit_id, customer_id, _model_id = _setup(client, token)

    resp = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "unit_id": unit_id,
            "salesperson_id": other_id,
            "negotiated_price": 19800.0,
            "discount": 200.0,
            "payment_type": "cash",
        },
        headers={"Authorization": f"Bearer {sales_bearer}"},
    )
    assert resp.status_code == 403
