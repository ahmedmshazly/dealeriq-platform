"""Integration tests: each of the six FR-061 built-in rules against hand-constructed DB
fixtures, plus the shared dedup-key invariant (FR-062).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.alerts.alert_rules import (
    evaluate_forecast_stockout,
    evaluate_lead_idle,
    evaluate_lead_score_drift,
    evaluate_sales_anomaly,
    evaluate_stock_reorder,
    evaluate_unit_aging,
    open_alert,
)
from dealeriq_api.domain.models.alerts import Alert, AlertRule, AlertSeverity
from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.customer_analytics import LeadScore
from dealeriq_api.domain.models.inventory_intel import Anomaly, InventoryIntel, UnitRisk
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from dealeriq_api.domain.services.order_service import create_order, submit_order


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
        make="Toyota",
        model=f"TestModel{uuid.uuid4().hex[:6]}",
        segment="economy",
        list_price=20000.0,
    )
    db.add(branch)
    db.add(model)
    db.flush()
    return model, branch


def test_stock_reorder_fires_when_on_hand_at_or_below_reorder_point(db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    run = _new_run(db_session, "inventory")

    # 2 in-stock units, reorder point of 3 -> should fire (on_hand=2 <= 3)
    for _ in range(2):
        db_session.add(
            VehicleUnit(
                vin=uuid.uuid4().hex[:17].upper(),
                model_id=model.id,
                branch_id=branch.id,
                status=UnitStatus.IN_STOCK,
                acquisition_date=date(2024, 1, 1),
                acquisition_cost=15000.0,
            )
        )
    db_session.add(
        InventoryIntel(
            run_id=run.id,
            model_id=model.id,
            branch_id=branch.id,
            abc="A",
            xyz="X",
            revenue_share=0.5,
            demand_cv=0.2,
            reorder_point=3.0,
            safety_stock=1.0,
            service_level=0.9,
        )
    )
    db_session.commit()

    dedup_key = f"model:{model.id}::branch:{branch.id}"
    count = evaluate_stock_reorder(db_session, run.id)
    assert count == 1
    alert = db_session.execute(
        select(Alert).where(Alert.rule_key == "stock_reorder", Alert.dedup_key == dedup_key)
    ).scalar_one()
    assert alert.payload["on_hand"] == 2
    assert alert.severity == AlertSeverity.WARNING

    # Re-running the same evaluation must not open a second alert (FR-062).
    count_again = evaluate_stock_reorder(db_session, run.id)
    assert count_again == 0
    all_alerts = (
        db_session.execute(
            select(Alert).where(Alert.rule_key == "stock_reorder", Alert.dedup_key == dedup_key)
        )
        .scalars()
        .all()
    )
    assert len(all_alerts) == 1


def test_stock_reorder_does_not_fire_when_on_hand_is_above_reorder_point(
    db_session: Session,
) -> None:
    model, branch = _new_model_and_branch(db_session)
    run = _new_run(db_session, "inventory")
    for _ in range(5):
        db_session.add(
            VehicleUnit(
                vin=uuid.uuid4().hex[:17].upper(),
                model_id=model.id,
                branch_id=branch.id,
                status=UnitStatus.IN_STOCK,
                acquisition_date=date(2024, 1, 1),
                acquisition_cost=15000.0,
            )
        )
    db_session.add(
        InventoryIntel(
            run_id=run.id,
            model_id=model.id,
            branch_id=branch.id,
            abc="A",
            xyz="X",
            revenue_share=0.5,
            demand_cv=0.2,
            reorder_point=3.0,
            safety_stock=1.0,
            service_level=0.9,
        )
    )
    db_session.commit()

    assert evaluate_stock_reorder(db_session, run.id) == 0


def test_unit_aging_fires_only_for_units_flagged_by_phase5(db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    run = _new_run(db_session, "inventory")
    unit = VehicleUnit(
        vin=uuid.uuid4().hex[:17].upper(),
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.IN_STOCK,
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=15000.0,
    )
    db_session.add(unit)
    db_session.flush()
    db_session.add(UnitRisk(run_id=run.id, unit_id=unit.id, days_on_lot=120, is_aging=True))
    db_session.commit()

    assert evaluate_unit_aging(db_session, run.id) == 1
    alert = db_session.execute(
        select(Alert).where(Alert.rule_key == "unit_aging", Alert.dedup_key == f"unit:{unit.id}")
    ).scalar_one()
    assert alert.payload["unit_id"] == str(unit.id)


def test_sales_anomaly_severity_derives_from_the_anomalys_own_score(db_session: Session) -> None:
    run = _new_run(db_session, "inventory")
    entity_key = f"sales::model:{uuid.uuid4()}::branch:test"
    db_session.add(
        Anomaly(
            run_id=run.id,
            scope="series",
            entity_key=entity_key,
            week_start=date(2024, 6, 1),
            observed=100.0,
            expected=10.0,
            score=9.0,
            method="stl_zscore",
            severity=5.0,
            esd_confirmed=True,
            status="new",
        )
    )
    db_session.commit()

    dedup_key = f"series:{entity_key}:2024-06-01"
    assert evaluate_sales_anomaly(db_session, run.id) == 1
    alert = db_session.execute(
        select(Alert).where(Alert.rule_key == "sales_anomaly", Alert.dedup_key == dedup_key)
    ).scalar_one()
    assert alert.severity == AlertSeverity.CRITICAL  # score=5.0 >= 3.0 threshold


def test_forecast_stockout_fires_when_on_hand_below_expected_demand(db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    run = _new_run(db_session, "forecast")
    series_key = f"model:{model.id}::branch:{branch.id}"

    # 1 unit on hand, but the next 2 weeks' point forecast sums to 10 -> stockout risk.
    db_session.add(
        VehicleUnit(
            vin=uuid.uuid4().hex[:17].upper(),
            model_id=model.id,
            branch_id=branch.id,
            status=UnitStatus.IN_STOCK,
            acquisition_date=date(2024, 1, 1),
            acquisition_cost=15000.0,
        )
    )
    for week_offset in range(2):
        db_session.add(
            Forecast(
                run_id=run.id,
                series_key=series_key,
                week_start=date(2024, 6, 1) + timedelta(weeks=week_offset),
                yhat=5.0,
                yhat_lo80=3.0,
                yhat_hi80=7.0,
                method="AutoARIMA",
            )
        )
    db_session.commit()

    assert evaluate_forecast_stockout(db_session, run.id) == 1
    alert = db_session.execute(
        select(Alert).where(Alert.rule_key == "forecast_stockout", Alert.dedup_key == series_key)
    ).scalar_one()
    assert alert.payload["on_hand"] == 1
    assert alert.payload["expected_demand"] == 10.0


def test_lead_idle_fires_for_leads_past_the_threshold_excluding_terminal_status(
    db_session: Session,
) -> None:
    customer = Customer(name="Idle Test Customer")
    model, _branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    db_session.add(customer)
    db_session.flush()

    old_activity = datetime.now(UTC) - timedelta(days=30)
    recent_activity = datetime.now(UTC) - timedelta(days=1)

    idle_lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="mid",
        status=LeadStatus.CONTACTED,
        owner_id=owner.id,
        last_activity_at=old_activity,
    )
    fresh_lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="mid",
        status=LeadStatus.CONTACTED,
        owner_id=owner.id,
        last_activity_at=recent_activity,
    )
    won_but_idle_lead = Lead(
        customer_id=customer.id,
        model_id=model.id,
        budget_band="mid",
        status=LeadStatus.WON,
        owner_id=owner.id,
        last_activity_at=old_activity,
    )
    db_session.add_all([idle_lead, fresh_lead, won_but_idle_lead])
    db_session.commit()

    evaluate_lead_idle(db_session)
    alert = db_session.execute(
        select(Alert).where(
            Alert.rule_key == "lead_idle", Alert.dedup_key == f"lead:{idle_lead.id}"
        )
    ).scalar_one()
    assert alert.payload["lead_id"] == str(idle_lead.id)


def test_open_alert_dedup_key_prevents_a_second_open_alert(db_session: Session) -> None:
    first = open_alert(
        db_session,
        rule_key="stock_reorder",
        dedup_key="test-dedup-key",
        severity=AlertSeverity.WARNING,
        payload={},
    )
    db_session.commit()
    assert first is not None

    second = open_alert(
        db_session,
        rule_key="stock_reorder",
        dedup_key="test-dedup-key",
        severity=AlertSeverity.WARNING,
        payload={},
    )
    assert second is None


def test_discount_approval_fires_synchronously_on_high_discount_order_submission(
    db_session: Session,
) -> None:
    model, branch = _new_model_and_branch(db_session)
    customer = Customer(name="Discount Test Customer")
    salesperson = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    unit = VehicleUnit(
        vin=uuid.uuid4().hex[:17].upper(),
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.IN_STOCK,
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=15000.0,
    )
    db_session.add_all([customer, unit])
    db_session.flush()

    order = create_order(
        db_session,
        actor_id=salesperson.id,
        customer_id=customer.id,
        unit_id=unit.id,
        salesperson_id=salesperson.id,
        negotiated_price=17000.0,
        discount=3000.0,  # 15% of list price, over the 5% approval threshold
        payment_type=PaymentType.FINANCE,
        ip=None,
    )
    db_session.commit()

    submit_order(db_session, current_user=salesperson, order_id=order.id, ip=None)

    alert = db_session.execute(
        select(Alert).where(
            Alert.rule_key == "discount_approval", Alert.dedup_key == f"order:{order.id}"
        )
    ).scalar_one()
    assert alert.payload["order_id"] == str(order.id)
    assert alert.payload["discount_fraction"] == 0.15


def test_discount_approval_does_not_fire_for_a_low_discount_order(db_session: Session) -> None:
    model, branch = _new_model_and_branch(db_session)
    customer = Customer(name="Low Discount Test Customer")
    salesperson = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    unit = VehicleUnit(
        vin=uuid.uuid4().hex[:17].upper(),
        model_id=model.id,
        branch_id=branch.id,
        status=UnitStatus.IN_STOCK,
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=15000.0,
    )
    db_session.add_all([customer, unit])
    db_session.flush()

    order = create_order(
        db_session,
        actor_id=salesperson.id,
        customer_id=customer.id,
        unit_id=unit.id,
        salesperson_id=salesperson.id,
        negotiated_price=19500.0,
        discount=500.0,  # 2.5% of list price, under the 5% approval threshold
        payment_type=PaymentType.FINANCE,
        ip=None,
    )
    db_session.commit()

    submit_order(db_session, current_user=salesperson, order_id=order.id, ip=None)

    existing = db_session.execute(
        select(Alert).where(
            Alert.rule_key == "discount_approval", Alert.dedup_key == f"order:{order.id}"
        )
    ).first()
    assert existing is None


def _set_lead_idle_score_cutoff(db: Session, score_cutoff: float | None) -> None:
    rule = db.execute(select(AlertRule).where(AlertRule.key == "lead_idle")).scalar_one()
    rule.params = {**rule.params, "score_cutoff": score_cutoff}
    db.commit()


def test_lead_idle_score_cutoff_only_fires_for_promising_leads(db_session: Session) -> None:
    # lead_idle's score_cutoff is shared across the whole test suite, restore it to Phase 6's
    # default (null) afterward so this doesn't affect any other test in this session-scoped
    # container (ADR-013), matching test_alert_rule_config.py's own restore-in-finally pattern.
    model, _branch = _new_model_and_branch(db_session)
    owner = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    scoring_run = _new_run(db_session, "lead_scoring")

    old_activity = datetime.now(UTC) - timedelta(days=30)
    promising_customer = Customer(name="Promising Idle Customer")
    unpromising_customer = Customer(name="Unpromising Idle Customer")
    db_session.add_all([promising_customer, unpromising_customer])
    db_session.flush()

    promising_lead = Lead(
        customer_id=promising_customer.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.CONTACTED,
        owner_id=owner.id,
        last_activity_at=old_activity,
    )
    unpromising_lead = Lead(
        customer_id=unpromising_customer.id,
        model_id=model.id,
        budget_band="under_20k",
        status=LeadStatus.CONTACTED,
        owner_id=owner.id,
        last_activity_at=old_activity,
    )
    db_session.add_all([promising_lead, unpromising_lead])
    db_session.flush()

    db_session.add(
        LeadScore(
            run_id=scoring_run.id,
            lead_id=promising_lead.id,
            conversion_probability=0.8,
            top_features=[],
        )
    )
    db_session.add(
        LeadScore(
            run_id=scoring_run.id,
            lead_id=unpromising_lead.id,
            conversion_probability=0.2,
            top_features=[],
        )
    )
    db_session.commit()

    _set_lead_idle_score_cutoff(db_session, 0.5)
    try:
        evaluate_lead_idle(db_session)

        promising_alert = db_session.execute(
            select(Alert).where(
                Alert.rule_key == "lead_idle", Alert.dedup_key == f"lead:{promising_lead.id}"
            )
        ).first()
        assert promising_alert is not None

        unpromising_alert = db_session.execute(
            select(Alert).where(
                Alert.rule_key == "lead_idle", Alert.dedup_key == f"lead:{unpromising_lead.id}"
            )
        ).first()
        assert unpromising_alert is None
    finally:
        _set_lead_idle_score_cutoff(db_session, None)


def test_lead_score_drift_alert_fires_only_when_features_are_provided(db_session: Session) -> None:
    run_id_with_drift = uuid.uuid4()
    alert = evaluate_lead_score_drift(
        db_session, run_id_with_drift, {"budget_level": 0.42, "customer_rfm_score": 0.31}
    )
    db_session.commit()
    assert alert is not None
    assert alert.payload["drifted_features"] == {"budget_level": 0.42, "customer_rfm_score": 0.31}

    fetched = db_session.execute(
        select(Alert).where(
            Alert.rule_key == "lead_score_drift", Alert.dedup_key == f"run:{run_id_with_drift}"
        )
    ).scalar_one()
    assert fetched.severity == AlertSeverity.WARNING

    run_id_without_drift = uuid.uuid4()
    no_alert = evaluate_lead_score_drift(db_session, run_id_without_drift, {})
    assert no_alert is None
    existing = db_session.execute(
        select(Alert).where(
            Alert.rule_key == "lead_score_drift", Alert.dedup_key == f"run:{run_id_without_drift}"
        )
    ).first()
    assert existing is None
