"""FR-003 / FR-007: Sales own-only lead/order reads; Manager/Analyst see all."""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import admin_token, create_user, usable_token, user_token


def _create_customer(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/customers",
        json={"name": f"Customer {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["customer"]["id"]


def _create_model(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/vehicle-models",
        json={"make": "Honda", "model": "Civic", "segment": "compact", "list_price": 22000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_sales_list_leads_is_scoped_to_own_leads_only(client: TestClient) -> None:
    admin = admin_token(client)
    customer_id = _create_customer(client, admin)
    model_id = _create_model(client, admin)

    sales_a_id, sales_a_email, sales_a_pw = create_user(client, admin, "sales")
    sales_b_id, sales_b_email, sales_b_pw = create_user(client, admin, "sales")
    sales_a = usable_token(client, sales_a_email, sales_a_pw)
    sales_b = usable_token(client, sales_b_email, sales_b_pw)

    for owner_id, bearer in ((sales_a_id, sales_a), (sales_b_id, sales_b)):
        resp = client.post(
            "/api/v1/leads",
            json={
                "customer_id": customer_id,
                "model_id": model_id,
                "budget_band": "20k-30k",
                "owner_id": owner_id,
            },
            headers={"Authorization": f"Bearer {bearer}"},
        )
        assert resp.status_code == 201

    list_a = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {sales_a}"})
    assert list_a.status_code == 200
    owners_a = {item["owner_id"] for item in list_a.json()["items"]}
    assert owners_a == {sales_a_id}

    # Client-supplied owner_id for another salesperson must not widen Sales scope.
    widen = client.get(
        "/api/v1/leads",
        params={"owner_id": sales_b_id},
        headers={"Authorization": f"Bearer {sales_a}"},
    )
    assert widen.status_code == 200
    assert all(item["owner_id"] == sales_a_id for item in widen.json()["items"])


def test_manager_and_analyst_can_list_all_leads(client: TestClient) -> None:
    admin = admin_token(client)
    customer_id = _create_customer(client, admin)
    model_id = _create_model(client, admin)

    sales_a_id, sales_a_email, sales_a_pw = create_user(client, admin, "sales")
    sales_b_id, sales_b_email, sales_b_pw = create_user(client, admin, "sales")
    sales_a = usable_token(client, sales_a_email, sales_a_pw)
    sales_b = usable_token(client, sales_b_email, sales_b_pw)
    manager = user_token(client, admin, "manager")
    analyst = user_token(client, admin, "analyst")

    for owner_id, bearer in ((sales_a_id, sales_a), (sales_b_id, sales_b)):
        assert (
            client.post(
                "/api/v1/leads",
                json={
                    "customer_id": customer_id,
                    "model_id": model_id,
                    "budget_band": "20k-30k",
                    "owner_id": owner_id,
                },
                headers={"Authorization": f"Bearer {bearer}"},
            ).status_code
            == 201
        )

    for token in (manager, analyst):
        resp = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        owners = {item["owner_id"] for item in resp.json()["items"]}
        assert sales_a_id in owners and sales_b_id in owners


def test_sales_cannot_get_another_salespersons_order(client: TestClient) -> None:
    from datetime import date

    admin = admin_token(client)
    sales_a_id, sales_a_email, sales_a_pw = create_user(client, admin, "sales")
    sales_b_id, sales_b_email, sales_b_pw = create_user(client, admin, "sales")
    sales_a = usable_token(client, sales_a_email, sales_a_pw)
    sales_b = usable_token(client, sales_b_email, sales_b_pw)

    branch = client.post(
        "/api/v1/branches",
        json={"name": f"Branch {uuid.uuid4().hex[:6]}", "city": "X"},
        headers={"Authorization": f"Bearer {admin}"},
    ).json()["id"]
    model = client.post(
        "/api/v1/vehicle-models",
        json={"make": "Toyota", "model": "Corolla", "segment": "sedan", "list_price": 20000},
        headers={"Authorization": f"Bearer {admin}"},
    ).json()["id"]
    unit = client.post(
        "/api/v1/vehicle-units",
        json={
            "vin": f"1HG{uuid.uuid4().hex[:14].upper()}",
            "model_id": model,
            "branch_id": branch,
            "acquisition_date": date.today().isoformat(),
            "acquisition_cost": 15000,
        },
        headers={"Authorization": f"Bearer {admin}"},
    ).json()["id"]
    customer = client.post(
        "/api/v1/customers",
        json={"name": f"Buyer {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {admin}"},
    ).json()["customer"]["id"]

    order = client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer,
            "unit_id": unit,
            "salesperson_id": sales_b_id,
            "negotiated_price": 19000,
            "discount": 0,
            "payment_type": "cash",
        },
        headers={"Authorization": f"Bearer {sales_b}"},
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    denied = client.get(
        f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {sales_a}"}
    )
    assert denied.status_code == 404

    list_a = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {sales_a}"})
    assert list_a.status_code == 200
    assert all(item["salesperson_id"] == sales_a_id for item in list_a.json()["items"])
    assert order_id not in {item["id"] for item in list_a.json()["items"]}

    # Nested customer history must not leak peer negotiated prices either.
    detail = client.get(
        f"/api/v1/customers/{customer}", headers={"Authorization": f"Bearer {sales_a}"}
    )
    assert detail.status_code == 200
    assert order_id not in {o["id"] for o in detail.json()["orders"]}

    # Sales inventory list must not expose acquisition_cost (FR-043).
    units = client.get("/api/v1/vehicle-units", headers={"Authorization": f"Bearer {sales_a}"})
    assert units.status_code == 200
    assert all(item["acquisition_cost"] is None for item in units.json()["items"])

    manager = user_token(client, admin, "manager")
    manager_units = client.get(
        "/api/v1/vehicle-units", headers={"Authorization": f"Bearer {manager}"}
    )
    assert manager_units.status_code == 200
    assert any(item["acquisition_cost"] is not None for item in manager_units.json()["items"])
