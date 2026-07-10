"""Integration tests: the forecast job end-to-end (FR-070..072, DS-FC-006/007).

Test data is inserted directly via the ORM (not the order-lifecycle API) — what's under test
here is the forecast job itself, not order creation, and a real 64+ week order history would be
prohibitively slow to build through repeated create/submit/deliver API round-trips.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.forecast_job import run_forecast_job
from dealeriq_api.domain.models.analytics import AnalyticsRun, ForecastMetric, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token

N_WEEKS = 70  # >= 52 (min CV training window) + 12 (horizon), small buffer for a fast test


def _seed_minimal_series(db: Session) -> None:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    db.add(branch)
    model = VehicleModel(
        make="Toyota",
        model=f"TestModel{uuid.uuid4().hex[:6]}",
        segment="economy",
        list_price=20000.0,
    )
    db.add(model)
    customer = Customer(name="Test Buyer")
    db.add(customer)
    db.flush()

    admin = db.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()

    # Each call to this helper (one per test) needs its own VIN namespace — the shared
    # session-scoped container means a second test's identical week/i-based VINs would collide
    # with the first test's still-present rows.
    vin_prefix = uuid.uuid4().hex[:6].upper()

    start = date(2024, 1, 1)
    for week in range(N_WEEKS):
        count = 3 if week % 3 == 0 else 2  # varies so MASE's in-sample scale isn't degenerate
        week_date = start + timedelta(weeks=week)
        for i in range(count):
            unit = VehicleUnit(
                vin=f"{vin_prefix}{week:04d}{i}".ljust(17, "0")[:17],
                model_id=model.id,
                branch_id=branch.id,
                status=UnitStatus.SOLD,
                acquisition_date=week_date,
                acquisition_cost=15000.0,
            )
            db.add(unit)
            db.flush()
            order = Order(
                customer_id=customer.id,
                unit_id=unit.id,
                salesperson_id=admin.id,
                negotiated_price=19000.0,
                discount=1000.0,
                payment_type=PaymentType.CASH,
                status=OrderStatus.DELIVERED,
                created_at=datetime.combine(week_date, datetime.min.time(), tzinfo=UTC),
            )
            db.add(order)
    db.commit()


def test_trigger_forecast_job_succeeds_and_persists_results(
    client: TestClient, db_session: Session
) -> None:
    _seed_minimal_series(db_session)
    token = admin_token(client)

    trigger_resp = client.post(
        "/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert trigger_resp.status_code == 201
    run = trigger_resp.json()
    assert run["status"] == "succeeded"
    assert run["job_name"] == "forecast"
    assert run["finished_at"] is not None

    # Exactly one champion per series for this run.
    champions = (
        db_session.execute(
            select(ForecastMetric).where(
                ForecastMetric.run_id == uuid.UUID(run["id"]), ForecastMetric.is_champion.is_(True)
            )
        )
        .scalars()
        .all()
    )
    series_keys = {c.series_key for c in champions}
    assert len(series_keys) == len(champions)  # no series has more than one champion
    assert len(series_keys) >= 2  # at least the (model,branch) + (segment,branch) series


def test_concurrent_trigger_is_rejected_with_409(client: TestClient, db_session: Session) -> None:
    _seed_minimal_series(db_session)
    token = admin_token(client)

    in_progress = AnalyticsRun(
        job_name="forecast",
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

    resp = client.post("/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409

    # Resolve the stuck row so it doesn't permanently block "forecast" triggers for every test
    # that runs afterward in this shared, session-scoped container (ADR-013) -- this row would
    # otherwise sit at status=running forever, since nothing else in this test ever completes it.
    in_progress.status = RunStatus.FAILED
    in_progress.finished_at = datetime.now(UTC)
    db_session.commit()


def test_job_that_raises_ends_failed_not_stuck_running(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Seeds real (unique-named, so no cross-test collision) data, then forces the pipeline
    # itself to raise mid-run -- verifies the running -> failed transition without touching any
    # other test's data in this session-shared container (unlike deleting all orders would).
    _seed_minimal_series(db_session)

    def _boom(series_by_key: object) -> None:
        raise RuntimeError("simulated pipeline failure")

    monkeypatch.setattr("dealeriq_api.domain.forecast_job.run_forecast_pipeline", _boom)

    with pytest.raises(RuntimeError, match="simulated pipeline failure"):
        run_forecast_job(db_session)

    latest = (
        db_session.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == "forecast")
            .order_by(AnalyticsRun.started_at.desc())
        )
        .scalars()
        .first()
    )
    assert latest is not None
    assert latest.status == RunStatus.FAILED
    assert latest.finished_at is not None
    assert "simulated pipeline failure" in latest.metrics.get("error", "")


def test_leaderboard_and_series_detail_endpoints(client: TestClient, db_session: Session) -> None:
    _seed_minimal_series(db_session)
    token = admin_token(client)
    trigger_resp = client.post(
        "/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert trigger_resp.status_code == 201

    leaderboard_resp = client.get("/api/v1/forecasts", headers={"Authorization": f"Bearer {token}"})
    assert leaderboard_resp.status_code == 200
    entries = leaderboard_resp.json()["entries"]
    assert len(entries) >= 1

    series_key = entries[0]["series_key"]
    detail_resp = client.get(
        f"/api/v1/forecasts/{series_key}", headers={"Authorization": f"Bearer {token}"}
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["series_key"] == series_key
    assert len(detail["forecast"]) == 12  # DS-FC-007: 12-week point forecasts
    assert len(detail["actuals"]) == N_WEEKS
    assert any(m["is_champion"] for m in detail["metrics_by_method"])
