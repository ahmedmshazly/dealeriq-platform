"""Integration tests: the customer-analytics job end-to-end (DS-CUST-001..005, FR-074).

Test data is inserted directly via the ORM (not the lead/order-lifecycle API), same rationale as
`test_forecast_job.py`/`test_inventory_job.py`: what's under test is the job itself. The too-few-
resolved-leads failure path (DS-OPS-002) is already covered at the pure-function level by
`packages/analytics/tests/test_lead_scoring.py` - with dozens of other test files sharing this
session-scoped testcontainers Postgres (ADR-013), the shared container always has well over
`MIN_RESOLVED_LEADS_TO_TRAIN` leads by the time this file runs, so that path can't be reliably
re-triggered here.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.jobs.lead_scoring_job import run_lead_scoring_job
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.customer_analytics import CustomerRfmProfile, LeadScore
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token

N_RESOLVED_LEADS = 40


def _new_model_and_branch(db: Session) -> tuple[VehicleModel, Branch]:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Toyota", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=25000.0
    )
    db.add(branch)
    db.add(model)
    db.flush()
    return model, branch


def _seed_rfm_customer(
    db: Session, model: VehicleModel, branch: Branch, owner_id: uuid.UUID
) -> Customer:
    """A customer with several recent, high-value delivered orders, should land in a "good"
    RFM segment (Champions/At Risk/Loyal), never the zero-order "New" segment."""
    customer = Customer(name=f"RFM Test Customer {uuid.uuid4().hex[:6]}", source_channel="referral")
    db.add(customer)
    db.flush()
    for i in range(5):
        unit = VehicleUnit(
            vin=f"RFMTEST{i:03d}{uuid.uuid4().hex[:6].upper()}"[:17],
            model_id=model.id,
            branch_id=branch.id,
            status=UnitStatus.SOLD,
            acquisition_date=date(2025, 1, 1),
            acquisition_cost=15000.0,
        )
        db.add(unit)
        db.flush()
        db.add(
            Order(
                customer_id=customer.id,
                unit_id=unit.id,
                salesperson_id=owner_id,
                negotiated_price=22000.0,
                discount=0,
                payment_type=PaymentType.CASH,
                status=OrderStatus.DELIVERED,
                created_at=datetime.now(UTC) - timedelta(days=10 * i),
            )
        )
    return customer


def _seed_resolved_leads(db: Session, model: VehicleModel, owner_id: uuid.UUID) -> None:
    """A strongly-separable population (referral leads win, social_ad leads lose) so the job has
    real, checkable signal to fit, comfortably clears MIN_RESOLVED_LEADS_TO_TRAIN regardless of
    whatever other test files have already added to the shared container."""
    now = datetime.now(UTC)
    for i in range(N_RESOLVED_LEADS):
        customer = Customer(
            name=f"Resolved Lead Customer {uuid.uuid4().hex[:6]}",
            source_channel="referral" if i % 2 == 0 else "social_ad",
        )
        db.add(customer)
        db.flush()
        created_at = now - timedelta(days=400 - i * 2)
        db.add(
            Lead(
                customer_id=customer.id,
                model_id=model.id,
                budget_band="under_20k",
                status=LeadStatus.WON if i % 2 == 0 else LeadStatus.LOST,
                owner_id=owner_id,
                last_activity_at=created_at,
                created_at=created_at,
            )
        )


def _seed_open_lead(db: Session, model: VehicleModel, owner_id: uuid.UUID) -> Lead:
    customer = Customer(
        name=f"Open Lead Customer {uuid.uuid4().hex[:6]}", source_channel="referral"
    )
    db.add(customer)
    db.flush()
    lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="55k_plus",
        status=LeadStatus.NEW,
        owner_id=owner_id,
        last_activity_at=datetime.now(UTC),
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    db.add(lead)
    return lead


def test_trigger_lead_scoring_job_succeeds_and_persists_results(
    client: TestClient, db_session: Session
) -> None:
    model, branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    rfm_customer = _seed_rfm_customer(db_session, model, branch, owner.id)
    _seed_resolved_leads(db_session, model, owner.id)
    open_lead = _seed_open_lead(db_session, model, owner.id)
    db_session.commit()

    token = admin_token(client)
    trigger_resp = client.post(
        "/api/v1/jobs/lead_scoring/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert trigger_resp.status_code == 201
    run = trigger_resp.json()
    assert run["status"] == "succeeded"
    assert run["job_name"] == "lead_scoring"

    run_id = uuid.UUID(run["id"])

    rfm_profile = db_session.execute(
        select(CustomerRfmProfile).where(
            CustomerRfmProfile.run_id == run_id, CustomerRfmProfile.customer_id == rfm_customer.id
        )
    ).scalar_one()
    assert rfm_profile.segment != "New"
    assert rfm_profile.recency_score is not None
    assert 1 <= rfm_profile.recency_score <= 5

    lead_score = db_session.execute(
        select(LeadScore).where(LeadScore.run_id == run_id, LeadScore.lead_id == open_lead.id)
    ).scalar_one()
    assert 0.0 <= lead_score.conversion_probability <= 1.0
    assert 1 <= len(lead_score.top_features) <= 3
    for feature in lead_score.top_features:
        assert "label" in feature and "contribution" in feature

    metrics = run["metrics"]
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert metrics["brier_score"] >= 0.0
    assert metrics["n_train"] > 0
    assert metrics["n_validate"] > 0


def test_concurrent_trigger_is_rejected_with_409(client: TestClient, db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    _seed_rfm_customer(db_session, model, branch, owner.id)
    _seed_resolved_leads(db_session, model, owner.id)
    db_session.commit()
    token = admin_token(client)

    in_progress = AnalyticsRun(
        job_name="lead_scoring",
        params={},
        code_version="test",
        data_from=date(2024, 1, 1),
        data_to=date(2024, 1, 1),
        status=RunStatus.RUNNING,
        metrics={},
        started_at=datetime.now(UTC),
    )
    db_session.add(in_progress)
    db_session.commit()

    resp = client.post(
        "/api/v1/jobs/lead_scoring/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409

    # Resolve the stuck row so it doesn't permanently block "lead_scoring" triggers for every
    # test that runs afterward in this shared, session-scoped container (ADR-013).
    in_progress.status = RunStatus.FAILED
    in_progress.finished_at = datetime.now(UTC)
    db_session.commit()


def test_job_that_raises_ends_failed_not_stuck_running(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    _seed_rfm_customer(db_session, model, branch, owner.id)
    _seed_resolved_leads(db_session, model, owner.id)
    db_session.commit()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated pipeline failure")

    monkeypatch.setattr("dealeriq_api.domain.jobs.lead_scoring_job._write_customer_rfm", _boom)

    with pytest.raises(RuntimeError, match="simulated pipeline failure"):
        run_lead_scoring_job(db_session)

    latest = (
        db_session.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == "lead_scoring")
            .order_by(AnalyticsRun.started_at.desc())
        )
        .scalars()
        .first()
    )
    assert latest is not None
    assert latest.status == RunStatus.FAILED
    assert latest.finished_at is not None
    assert "simulated pipeline failure" in latest.metrics.get("error", "")
