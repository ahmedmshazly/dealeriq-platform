"""Integration tests: the Manager and Sales dashboards (FR-050, FR-051).

Test data is inserted directly via the ORM (not the order/lead-lifecycle API), same rationale as
every other job/aggregation test in this suite: what's under test is the aggregation itself.
"""

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.alerts import Alert, AlertSeverity, AlertStatus, Notification
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import Order, OrderEvent, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token, create_user, usable_token


def _new_model_and_branch(db: Session) -> tuple[VehicleModel, Branch]:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Toyota", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=25000.0
    )
    db.add(branch)
    db.add(model)
    db.flush()
    return model, branch


def _seed_delivered_order(
    db: Session, *, model: VehicleModel, branch: Branch, salesperson_id: uuid.UUID, price: float
) -> None:
    customer = Customer(name=f"Dashboard Test Customer {uuid.uuid4().hex[:6]}")
    db.add(customer)
    unit = VehicleUnit(
        vin=f"DASH{uuid.uuid4().hex[:13].upper()}"[:17],
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.SOLD,
        acquisition_date=date(2025, 1, 1),
        acquisition_cost=price * 0.8,
    )
    db.add(unit)
    db.flush()
    order = Order(
        customer_id=customer.id,
        unit_id=unit.id,
        salesperson_id=salesperson_id,
        negotiated_price=price,
        discount=0,
        payment_type=PaymentType.CASH,
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()
    db.add(
        OrderEvent(
            order_id=order.id,
            from_status=OrderStatus.APPROVED.value,
            to_status=OrderStatus.DELIVERED.value,
            actor_id=salesperson_id,
            at=datetime.now(UTC),
        )
    )


def test_manager_dashboard_shows_real_data(client: TestClient, db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    _seed_delivered_order(
        db_session, model=model, branch=branch, salesperson_id=owner.id, price=30000.0
    )
    db_session.commit()

    token = admin_token(client)
    resp = client.get("/api/v1/dashboards/manager", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["sales_vs_forecast"], list)
    assert isinstance(body["top_models"], list)
    assert isinstance(body["inventory_abc_xyz_counts"], dict)
    assert body["aging_unit_count"] >= 0
    assert body["open_anomaly_count"] >= 0
    assert body["unacknowledged_alert_count"] >= 0
    assert any(m["display_name"] == f"{model.make} {model.model}" for m in body["top_models"])


def test_sales_dashboard_never_leaks_another_salespersons_data(
    client: TestClient, db_session: Session
) -> None:
    admin = admin_token(client)
    model, branch = _new_model_and_branch(db_session)

    sales_a_id, sales_a_email, sales_a_password = create_user(client, admin, "sales")
    sales_b_id, sales_b_email, sales_b_password = create_user(client, admin, "sales")
    sales_a_id, sales_b_id = uuid.UUID(sales_a_id), uuid.UUID(sales_b_id)

    customer_a = Customer(name="Sales A Customer")
    customer_b = Customer(name="Sales B Customer")
    db_session.add_all([customer_a, customer_b])
    db_session.flush()

    lead_a = Lead(
        customer_id=customer_a.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.NEW,
        owner_id=sales_a_id,
        last_activity_at=datetime.now(UTC),
    )
    lead_b = Lead(
        customer_id=customer_b.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.NEW,
        owner_id=sales_b_id,
        last_activity_at=datetime.now(UTC),
    )
    db_session.add_all([lead_a, lead_b])

    _seed_delivered_order(
        db_session, model=model, branch=branch, salesperson_id=sales_a_id, price=40000.0
    )
    _seed_delivered_order(
        db_session, model=model, branch=branch, salesperson_id=sales_b_id, price=25000.0
    )

    alert_a = Alert(
        rule_key="test_rule",
        dedup_key=f"sales-a-{uuid.uuid4()}",
        severity=AlertSeverity.INFO,
        payload={},
        status=AlertStatus.OPEN,
    )
    db_session.add(alert_a)
    db_session.flush()
    db_session.add(Notification(user_id=sales_a_id, alert_id=alert_a.id, channel="in_app"))
    db_session.commit()

    sales_a_bearer = usable_token(client, sales_a_email, sales_a_password)
    sales_b_bearer = usable_token(client, sales_b_email, sales_b_password)

    resp_a = client.get(
        "/api/v1/dashboards/sales", headers={"Authorization": f"Bearer {sales_a_bearer}"}
    )
    resp_b = client.get(
        "/api/v1/dashboards/sales", headers={"Authorization": f"Bearer {sales_b_bearer}"}
    )
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    body_a = resp_a.json()
    body_b = resp_b.json()

    lead_ids_a = {lead["lead_id"] for lead in body_a["open_leads"]}
    lead_ids_b = {lead["lead_id"] for lead in body_b["open_leads"]}
    assert str(lead_a.id) in lead_ids_a
    assert str(lead_a.id) not in lead_ids_b
    assert str(lead_b.id) in lead_ids_b
    assert str(lead_b.id) not in lead_ids_a

    assert body_a["my_sales_this_month"] >= 40000.0
    assert body_b["my_sales_this_month"] >= 25000.0
    assert body_a["unacknowledged_alert_count"] >= 1
    assert body_b["unacknowledged_alert_count"] == 0


def test_dashboards_require_permission(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, password = create_user(client, admin, "analyst")
    analyst = usable_token(client, email, password)

    resp = client.get("/api/v1/dashboards/manager", headers={"Authorization": f"Bearer {analyst}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
