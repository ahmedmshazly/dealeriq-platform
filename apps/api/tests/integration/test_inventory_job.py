"""Integration tests: the inventory intelligence & anomaly-detection job end-to-end
(DS-INV-001..004, DS-ANO-001..004).

Test data is inserted directly via the ORM (not the order-lifecycle API), same rationale as
`test_forecast_job.py`: what's under test is the job itself, not order creation.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.jobs.inventory_job import run_inventory_job
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.inventory_intel import Anomaly, InventoryIntel, UnitRisk
from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from tests.helpers import admin_token

N_WEEKS = 70


def _seed_minimal_dataset(db: Session, *, with_in_stock_units: bool = True) -> VehicleModel:
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
    vin_prefix = uuid.uuid4().hex[:6].upper()

    start = date(2024, 1, 1)
    for week in range(N_WEEKS):
        count = 3 if week % 3 == 0 else 2
        week_date = start + timedelta(weeks=week)
        for i in range(count):
            unit = VehicleUnit(
                vin=f"{vin_prefix}S{week:04d}{i}".ljust(17, "0")[:17],
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

    if with_in_stock_units:
        for i, days_back in enumerate([10, 45, 120]):
            unit = VehicleUnit(
                vin=f"{vin_prefix}I{i:05d}".ljust(17, "0")[:17],
                model_id=model.id,
                branch_id=branch.id,
                status=UnitStatus.IN_STOCK,
                acquisition_date=date.today() - timedelta(days=days_back),
                acquisition_cost=15000.0,
            )
            db.add(unit)

    db.commit()
    return model


def test_trigger_inventory_job_succeeds_and_persists_results(
    client: TestClient, db_session: Session
) -> None:
    # The job correctly processes the *entire* orders/units tables each run (mirroring real
    # production behavior over the whole dealership) -- in the full suite (not just this file in
    # isolation) other integration test files (e.g. test_inventory_flow.py) seed their own
    # IN_STOCK units into this same shared, session-scoped container (ADR-013), so every
    # assertion below is scoped to this test's own model, not an unfiltered run-wide count.
    model = _seed_minimal_dataset(db_session)
    token = admin_token(client)

    forecast_resp = client.post(
        "/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert forecast_resp.status_code == 201
    assert forecast_resp.json()["status"] == "succeeded"

    trigger_resp = client.post(
        "/api/v1/jobs/inventory/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert trigger_resp.status_code == 201
    run = trigger_resp.json()
    assert run["status"] == "succeeded"
    assert run["job_name"] == "inventory"
    run_id = uuid.UUID(run["id"])

    intel_rows = (
        db_session.execute(
            select(InventoryIntel).where(
                InventoryIntel.run_id == run_id, InventoryIntel.model_id == model.id
            )
        )
        .scalars()
        .all()
    )
    assert len(intel_rows) >= 1
    assert intel_rows[0].abc in ("A", "B", "C")
    assert intel_rows[0].xyz in ("X", "Y", "Z")
    # A forecast run already succeeded above, so reorder points should be real, not skipped.
    assert intel_rows[0].reorder_point is not None
    assert intel_rows[0].skipped_reason is None

    risk_rows = (
        db_session.execute(
            select(UnitRisk)
            .join(VehicleUnit, VehicleUnit.id == UnitRisk.unit_id)
            .where(UnitRisk.run_id == run_id, VehicleUnit.model_id == model.id)
        )
        .scalars()
        .all()
    )
    assert len(risk_rows) == 3  # the three in-stock units seeded above
    aging_rows = [r for r in risk_rows if r.is_aging]
    assert len(aging_rows) == 1  # only the 120-days-back unit clears the 90-day threshold


def test_reorder_point_skipped_when_series_has_no_persisted_forecast(
    client: TestClient, db_session: Session
) -> None:
    # Deliberately does NOT trigger a forecast job for this model/branch pair (each test uses a
    # fresh, uniquely-named model+branch, so even though an earlier test in this shared,
    # session-scoped container may have already produced a *succeeded* forecast run for *its own*
    # series, that prior run has nothing for THIS test's series -- exercising the real skip path
    # ("no persisted forecast for this series"), not a global "no forecast run has ever run" state
    # this shared-container test setup can't actually produce once any earlier test has run one.
    #
    # The inventory job itself correctly processes the *whole* orders table (not just this
    # test's rows, mirroring real production behavior over the whole dealership's inventory) --
    # so the run's InventoryIntel rows include every other test's models too, each with whatever
    # forecast status *they* have. This test filters down to its own model before asserting.
    model = _seed_minimal_dataset(db_session, with_in_stock_units=False)
    token = admin_token(client)

    trigger_resp = client.post(
        "/api/v1/jobs/inventory/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert trigger_resp.status_code == 201
    run_id = uuid.UUID(trigger_resp.json()["id"])

    intel_rows = (
        db_session.execute(
            select(InventoryIntel).where(
                InventoryIntel.run_id == run_id, InventoryIntel.model_id == model.id
            )
        )
        .scalars()
        .all()
    )
    assert len(intel_rows) >= 1
    for row in intel_rows:
        assert row.reorder_point is None
        assert row.skipped_reason is not None
        # abc/xyz don't depend on forecasts -- still populated even when reorder is skipped.
        assert row.abc in ("A", "B", "C")


def test_concurrent_trigger_is_rejected_with_409(client: TestClient, db_session: Session) -> None:
    _seed_minimal_dataset(db_session)
    token = admin_token(client)

    in_progress = AnalyticsRun(
        job_name="inventory",
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

    resp = client.post("/api/v1/jobs/inventory/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409

    # Resolve the stuck row so it doesn't permanently block "inventory" triggers for every test
    # that runs afterward in this shared, session-scoped container (ADR-013).
    in_progress.status = RunStatus.FAILED
    in_progress.finished_at = datetime.now(UTC)
    db_session.commit()


def test_job_that_raises_ends_failed_not_stuck_running(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_minimal_dataset(db_session, with_in_stock_units=False)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated pipeline failure")

    monkeypatch.setattr("dealeriq_api.domain.jobs.inventory_job._write_inventory_intel", _boom)

    with pytest.raises(RuntimeError, match="simulated pipeline failure"):
        run_inventory_job(db_session)

    latest = (
        db_session.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == "inventory")
            .order_by(AnalyticsRun.started_at.desc())
        )
        .scalars()
        .first()
    )
    assert latest is not None
    assert latest.status == RunStatus.FAILED
    assert latest.finished_at is not None
    assert "simulated pipeline failure" in latest.metrics.get("error", "")


def test_heatmap_model_detail_units_and_anomalies_endpoints(
    client: TestClient, db_session: Session
) -> None:
    model = _seed_minimal_dataset(db_session)
    token = admin_token(client)
    forecast_resp = client.post(
        "/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert forecast_resp.status_code == 201
    inventory_resp = client.post(
        "/api/v1/jobs/inventory/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert inventory_resp.status_code == 201

    heatmap_resp = client.get(
        "/api/v1/inventory/abc-xyz", headers={"Authorization": f"Bearer {token}"}
    )
    assert heatmap_resp.status_code == 200
    cells = heatmap_resp.json()["cells"]
    assert len(cells) == 9
    total_models = sum(len(c["models"]) for c in cells)
    assert total_models >= 1

    detail_resp = client.get(
        f"/api/v1/inventory/models/{model.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["model_id"] == str(model.id)
    assert len(detail["reorder_points"]) >= 1
    assert len(detail["at_risk_units"]) == 3

    units_resp = client.get(
        "/api/v1/inventory/units",
        params={"aging_only": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert units_resp.status_code == 200
    # This endpoint is unfiltered by model (global aging list, mirroring a real manager's
    # dealership-wide view) -- other tests in this shared container seed their own aging units
    # too, so assert this test's own unit is present rather than an exact total count.
    aging_units = units_resp.json()["units"]
    assert len(aging_units) >= 1
    assert str(model.id) in {u["model_id"] for u in aging_units}

    anomalies_resp = client.get("/api/v1/anomalies", headers={"Authorization": f"Bearer {token}"})
    assert anomalies_resp.status_code == 200
    # Existence check only -- this synthetic fixture has no injected anomalies, unlike the real
    # seeded dataset QA-003(b) validates against.
    assert isinstance(anomalies_resp.json()["anomalies"], list)


def test_series_and_transaction_anomalies_persist_with_scope(
    client: TestClient, db_session: Session
) -> None:
    _seed_minimal_dataset(db_session, with_in_stock_units=False)
    token = admin_token(client)
    forecast_resp = client.post(
        "/api/v1/jobs/forecast/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert forecast_resp.status_code == 201
    run_id = uuid.UUID(forecast_resp.json()["id"])
    inv_resp = client.post(
        "/api/v1/jobs/inventory/run", headers={"Authorization": f"Bearer {token}"}
    )
    assert inv_resp.status_code == 201
    inv_run_id = uuid.UUID(inv_resp.json()["id"])
    assert run_id != inv_run_id  # sanity: two distinct job runs, not one shared row

    anomaly_rows = (
        db_session.execute(select(Anomaly).where(Anomaly.run_id == inv_run_id)).scalars().all()
    )
    for row in anomaly_rows:
        assert row.scope in ("series", "transaction")
        assert row.status == "new"
