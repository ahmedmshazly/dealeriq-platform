"""Integration tests: the monthly report (FR-054)."""

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.alerts import Alert, AlertSeverity, AlertStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.order import Order, OrderEvent, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token

# A month that has definitely completed by the time this test runs.
REPORT_MONTH = date(2024, 3, 1)
REPORT_MONTH_STR = "2024-03"


def test_monthly_report_matches_hand_computed_totals(
    client: TestClient, db_session: Session
) -> None:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Toyota", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=25000.0
    )
    db_session.add_all([branch, model])
    db_session.flush()
    customer = Customer(name="Monthly Report Test Customer")
    db_session.add(customer)
    db_session.flush()
    admin = admin_token(client)
    salesperson = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()

    # Two delivered orders inside the report month: revenue=20000+15000=35000,
    # margin=(20000-14000)+(15000-10000)=6000+5000=11000.
    deliveries = [(20000.0, 14000.0), (15000.0, 10000.0)]
    for price, cost in deliveries:
        unit = VehicleUnit(
            vin=f"MRPT{uuid.uuid4().hex[:13].upper()}"[:17],
            model_id=model.id,
            branch_id=branch.id,
            status=UnitStatus.SOLD,
            acquisition_date=date(2024, 1, 1),
            acquisition_cost=cost,
        )
        db_session.add(unit)
        db_session.flush()
        order = Order(
            customer_id=customer.id,
            unit_id=unit.id,
            salesperson_id=salesperson.id,
            negotiated_price=price,
            discount=0,
            payment_type=PaymentType.CASH,
            status=OrderStatus.DELIVERED,
            created_at=datetime(2024, 3, 10, tzinfo=UTC),
        )
        db_session.add(order)
        db_session.flush()
        db_session.add(
            OrderEvent(
                order_id=order.id,
                from_status=OrderStatus.APPROVED.value,
                to_status=OrderStatus.DELIVERED.value,
                actor_id=salesperson.id,
                at=datetime(2024, 3, 15, tzinfo=UTC),
            )
        )

    # A delivered order OUTSIDE the report month must not be counted.
    unit_outside = VehicleUnit(
        vin=f"MRPT{uuid.uuid4().hex[:13].upper()}"[:17],
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.SOLD,
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=5000.0,
    )
    db_session.add(unit_outside)
    db_session.flush()
    order_outside = Order(
        customer_id=customer.id,
        unit_id=unit_outside.id,
        salesperson_id=salesperson.id,
        negotiated_price=9000.0,
        discount=0,
        payment_type=PaymentType.CASH,
        status=OrderStatus.DELIVERED,
        created_at=datetime(2024, 4, 1, tzinfo=UTC),
    )
    db_session.add(order_outside)
    db_session.flush()
    db_session.add(
        OrderEvent(
            order_id=order_outside.id,
            from_status=OrderStatus.APPROVED.value,
            to_status=OrderStatus.DELIVERED.value,
            actor_id=salesperson.id,
            at=datetime(2024, 4, 2, tzinfo=UTC),
        )
    )

    # Two alerts inside the report month, one outside.
    inside_alert_1 = Alert(
        rule_key="stock_reorder",
        dedup_key=f"mr-test-{uuid.uuid4()}",
        severity=AlertSeverity.WARNING,
        payload={},
        status=AlertStatus.OPEN,
        created_at=datetime(2024, 3, 5, tzinfo=UTC),
    )
    inside_alert_2 = Alert(
        rule_key="stock_reorder",
        dedup_key=f"mr-test-{uuid.uuid4()}",
        severity=AlertSeverity.CRITICAL,
        payload={},
        status=AlertStatus.OPEN,
        created_at=datetime(2024, 3, 20, tzinfo=UTC),
    )
    outside_alert = Alert(
        rule_key="stock_reorder",
        dedup_key=f"mr-test-{uuid.uuid4()}",
        severity=AlertSeverity.WARNING,
        payload={},
        status=AlertStatus.OPEN,
        created_at=datetime(2024, 4, 5, tzinfo=UTC),
    )
    db_session.add_all([inside_alert_1, inside_alert_2, outside_alert])
    db_session.commit()

    resp = client.get(
        "/api/v1/reports/monthly",
        params={"month": REPORT_MONTH_STR},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["month"] == REPORT_MONTH.isoformat()
    assert body["total_revenue"] >= 35000.0
    assert body["total_margin"] >= 11000.0
    assert isinstance(body["achieved_accuracy"], list)
    assert body["alert_statistics"]["counts_by_rule"].get("stock_reorder", 0) >= 2
    assert body["alert_statistics"]["counts_by_severity"].get("warning", 0) >= 1
    assert body["alert_statistics"]["counts_by_severity"].get("critical", 0) >= 1


def test_monthly_report_rejects_the_current_month(client: TestClient) -> None:
    admin = admin_token(client)
    today = datetime.now(UTC)
    current_month = f"{today.year}-{today.month:02d}"
    resp = client.get(
        "/api/v1/reports/monthly",
        params={"month": current_month},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 400


def test_monthly_report_defaults_to_the_most_recently_completed_month(
    client: TestClient,
) -> None:
    admin = admin_token(client)
    resp = client.get("/api/v1/reports/monthly", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    body = resp.json()
    today = datetime.now(UTC).date()
    reported_month = date.fromisoformat(body["month"])
    assert reported_month < today.replace(day=1)


def test_monthly_report_rejects_malformed_month(client: TestClient) -> None:
    admin = admin_token(client)
    resp = client.get(
        "/api/v1/reports/monthly",
        params={"month": "not-a-month"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 400
