"""Integration tests: leads-list score/explanation display (FR-032) and customer-detail RFM
segment + purchase history (FR-033).

Test data is inserted directly via the ORM, same rationale as `test_lead_scoring_job.py`: what's
under test is the *display* of already-computed analytics output, not the job that computes it.
"""

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.customer_analytics import CustomerRfmProfile, LeadScore
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token


def _new_run(db: Session, job_name: str) -> AnalyticsRun:
    run = AnalyticsRun(
        job_name=job_name,
        params={},
        code_version="test",
        data_from=date(2024, 1, 1),
        data_to=date(2024, 1, 1),
        status=RunStatus.SUCCEEDED,
        metrics={},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    return run


def _new_model_and_branch(db: Session) -> tuple[VehicleModel, Branch]:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Toyota", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=25000.0
    )
    db.add(branch)
    db.add(model)
    db.flush()
    return model, branch


def test_leads_list_shows_conversion_probability_and_explanation(
    client: TestClient, db_session: Session
) -> None:
    model, _branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    customer = Customer(name=f"Scored Lead Customer {uuid.uuid4().hex[:6]}")
    db_session.add(customer)
    db_session.flush()
    lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.NEW,
        owner_id=owner.id,
        last_activity_at=datetime.now(UTC),
    )
    db_session.add(lead)
    db_session.flush()

    run = _new_run(db_session, "lead_scoring")
    db_session.add(
        LeadScore(
            run_id=run.id,
            lead_id=lead.id,
            conversion_probability=0.73,
            top_features=[{"label": "Referral source", "contribution": 0.42}],
        )
    )
    db_session.add(
        CustomerRfmProfile(
            run_id=run.id,
            customer_id=customer.id,
            recency_score=4,
            frequency_score=3,
            monetary_score=5,
            segment="Loyal Customers",
        )
    )
    db_session.commit()

    token = admin_token(client)
    resp = client.get(
        "/api/v1/leads", params={"limit": 200}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    row = next(i for i in resp.json()["items"] if i["id"] == str(lead.id))
    assert row["conversion_probability"] == 0.73
    assert row["rfm_segment"] == "Loyal Customers"
    assert row["top_features"] == [{"label": "Referral source", "contribution": 0.42}]


def test_leads_list_shows_null_for_a_not_yet_scored_lead(
    client: TestClient, db_session: Session
) -> None:
    model, _branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    customer = Customer(name=f"Unscored Lead Customer {uuid.uuid4().hex[:6]}")
    db_session.add(customer)
    db_session.flush()
    lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.NEW,
        owner_id=owner.id,
        last_activity_at=datetime.now(UTC),
    )
    db_session.add(lead)
    db_session.commit()

    token = admin_token(client)
    resp = client.get(
        "/api/v1/leads", params={"limit": 200}, headers={"Authorization": f"Bearer {token}"}
    )
    row = next(i for i in resp.json()["items"] if i["id"] == str(lead.id))
    assert row["conversion_probability"] is None
    assert row["rfm_segment"] is None
    assert row["top_features"] == []


def test_customer_detail_shows_rfm_segment_and_purchase_history(
    client: TestClient, db_session: Session
) -> None:
    model, branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    customer = Customer(name=f"Detail Test Customer {uuid.uuid4().hex[:6]}")
    db_session.add(customer)
    db_session.flush()

    unit = VehicleUnit(
        vin=f"DETAILTEST{uuid.uuid4().hex[:6].upper()}"[:17],
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.SOLD,
        acquisition_date=date(2025, 1, 1),
        acquisition_cost=15000.0,
    )
    db_session.add(unit)
    db_session.flush()
    db_session.add(
        Order(
            customer_id=customer.id,
            unit_id=unit.id,
            salesperson_id=owner.id,
            negotiated_price=21000.0,
            discount=0,
            payment_type=PaymentType.CASH,
            status=OrderStatus.DELIVERED,
            created_at=datetime.now(UTC),
        )
    )

    run = _new_run(db_session, "lead_scoring")
    db_session.add(
        CustomerRfmProfile(
            run_id=run.id,
            customer_id=customer.id,
            recency_score=5,
            frequency_score=4,
            monetary_score=4,
            segment="Champions",
        )
    )
    db_session.commit()

    token = admin_token(client)
    resp = client.get(
        f"/api/v1/customers/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rfm_segment"] == "Champions"
    assert body["recency_score"] == 5
    assert len(body["orders"]) == 1
    assert body["orders"][0]["model_name"] == f"{model.make} {model.model}"
    assert body["orders"][0]["negotiated_price"] == 21000.0
    assert body["orders"][0]["status"] == "delivered"


def test_customer_detail_for_zero_order_customer_has_empty_purchase_history(
    client: TestClient, db_session: Session
) -> None:
    customer = Customer(name=f"Zero Order Customer {uuid.uuid4().hex[:6]}")
    db_session.add(customer)
    db_session.commit()

    token = admin_token(client)
    resp = client.get(
        f"/api/v1/customers/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["orders"] == []


def test_customer_detail_returns_404_for_unknown_customer(client: TestClient) -> None:
    token = admin_token(client)
    resp = client.get(
        f"/api/v1/customers/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
