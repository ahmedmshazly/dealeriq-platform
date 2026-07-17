"""Integration test: FR-073's achieved-accuracy computation, against a hand-computed fixture.

Test data is inserted directly via the ORM (not the order-lifecycle API), same rationale as
`test_forecast_job.py`: what's under test is `achieved_accuracy.py` itself. A real `mase()`
calculation needs `SEASON_LENGTH + 1` (53) weeks of history for its naive-error denominator to be
non-empty (the same constraint `test_forecast_job.py`'s own N_WEEKS=70 works around) — the
fixture here uses exactly 53 weeks so the denominator reduces to a single, hand-computable value.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.analytics import AnalyticsRun, Forecast, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.order import Order, OrderStatus, PaymentType
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleModel, VehicleUnit
from dealeriq_api.domain.reports.achieved_accuracy import compute_achieved_accuracy

# 49 "quiet" weeks at a constant 3 orders/week, then 4 "evaluation" weeks with known, distinct
# actuals -- chosen so the full 53-week history makes mase()'s naive-error denominator collapse
# to a single value: |y_train[52] - y_train[0]| = |4 - 3| = 1.
N_QUIET_WEEKS = 49
WEEKLY_COUNTS = [3] * N_QUIET_WEEKS + [3, 5, 2, 4]
FIRST_MONDAY = date(2025, 1, 6)


def _week_start(week_index: int) -> date:
    return FIRST_MONDAY + timedelta(weeks=week_index)


def _new_run(db: Session, *, finished_at: datetime) -> AnalyticsRun:
    run = AnalyticsRun(
        job_name="forecast",
        params={},
        code_version="test",
        data_from=FIRST_MONDAY,
        data_to=FIRST_MONDAY,
        status=RunStatus.SUCCEEDED,
        metrics={},
        started_at=finished_at,
        finished_at=finished_at,
    )
    db.add(run)
    db.flush()
    return run


def test_achieved_accuracy_matches_hand_computed_mase_and_dedups_to_the_earliest_run(
    db_session: Session,
) -> None:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Toyota", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=25000.0
    )
    db_session.add_all([branch, model])
    db_session.flush()
    customer = Customer(name="Achieved Accuracy Test Customer")
    db_session.add(customer)
    db_session.flush()
    salesperson = db_session.execute(select(User).order_by(User.created_at).limit(1)).scalar_one()
    series_key = f"model:{model.id}::branch:{branch.id}"

    vin_prefix = uuid.uuid4().hex[:6].upper()
    for week_index, count in enumerate(WEEKLY_COUNTS):
        week_date = _week_start(week_index)
        for i in range(count):
            unit = VehicleUnit(
                vin=f"{vin_prefix}{week_index:04d}{i}".ljust(17, "0")[:17],
                model_id=model.id,
                branch_id=branch.id,
                status=UnitStatus.SOLD,
                acquisition_date=week_date,
                acquisition_cost=15000.0,
            )
            db_session.add(unit)
            db_session.flush()
            db_session.add(
                Order(
                    customer_id=customer.id,
                    unit_id=unit.id,
                    salesperson_id=salesperson.id,
                    negotiated_price=20000.0,
                    discount=0,
                    payment_type=PaymentType.CASH,
                    status=OrderStatus.DELIVERED,
                    created_at=datetime.combine(week_date, datetime.min.time(), tzinfo=UTC),
                )
            )
    db_session.commit()

    # Evaluation weeks are the last 4 (indices 49, 50, 51, 52): actuals [3, 5, 2, 4].
    eval_week_indices = [49, 50, 51, 52]

    # Earlier run (should win the dedup): yhat = [4, 4, 3, 5] -> |diff| = [1, 1, 1, 1].
    earlier_run = _new_run(db_session, finished_at=datetime(2026, 1, 1, tzinfo=UTC))
    earlier_yhats = [4.0, 4.0, 3.0, 5.0]
    for idx, yhat in zip(eval_week_indices, earlier_yhats, strict=True):
        db_session.add(
            Forecast(
                run_id=earlier_run.id,
                series_key=series_key,
                week_start=_week_start(idx),
                yhat=yhat,
                yhat_lo80=yhat - 1,
                yhat_hi80=yhat + 1,
                method="test",
            )
        )

    # Later run (must be ignored by the earliest-run dedup rule): yhat exactly matches actuals,
    # which would drive MASE to 0 if incorrectly used instead of the earlier run's forecast.
    later_run = _new_run(db_session, finished_at=datetime(2026, 1, 3, tzinfo=UTC))
    later_yhats = [3.0, 5.0, 2.0, 4.0]
    for idx, yhat in zip(eval_week_indices, later_yhats, strict=True):
        db_session.add(
            Forecast(
                run_id=later_run.id,
                series_key=series_key,
                week_start=_week_start(idx),
                yhat=yhat,
                yhat_lo80=yhat - 1,
                yhat_hi80=yhat + 1,
                method="test",
            )
        )
    db_session.commit()

    as_of = datetime.combine(_week_start(52), datetime.min.time(), tzinfo=UTC) + timedelta(days=3)
    result = compute_achieved_accuracy(db_session, series_key, as_of=as_of, window_weeks=4)

    assert result is not None
    assert result.n_weeks_evaluated == 4
    # Hand-computed: numerator = mean(|3-4|,|5-4|,|2-3|,|4-5|) = 1.0
    #                denominator = |y_train[52]-y_train[0]| = |4-3| = 1.0  (season_length=52)
    #                MASE = 1.0 / 1.0 = 1.0
    assert abs(result.mase - 1.0) < 1e-9


def test_achieved_accuracy_returns_none_when_no_forecast_is_old_enough(
    db_session: Session,
) -> None:
    branch = Branch(name=f"Test Branch {uuid.uuid4().hex[:6]}", city="Testville")
    model = VehicleModel(
        make="Honda", model=f"TestModel{uuid.uuid4().hex[:6]}", segment="sedan", list_price=22000.0
    )
    db_session.add_all([branch, model])
    db_session.flush()
    series_key = f"model:{model.id}::branch:{branch.id}"

    run = _new_run(db_session, finished_at=datetime.now(UTC))
    # Forecast for a week that is still in the future as of `as_of` -- never evaluable.
    future_week = date.today() + timedelta(weeks=2)
    db_session.add(
        Forecast(
            run_id=run.id,
            series_key=series_key,
            week_start=future_week,
            yhat=5.0,
            yhat_lo80=4.0,
            yhat_hi80=6.0,
            method="test",
        )
    )
    db_session.commit()

    result = compute_achieved_accuracy(db_session, series_key, as_of=datetime.now(UTC))
    assert result is None


def test_achieved_accuracy_returns_none_for_unknown_series(db_session: Session) -> None:
    result = compute_achieved_accuracy(
        db_session, f"model:{uuid.uuid4()}::branch:{uuid.uuid4()}", as_of=datetime.now(UTC)
    )
    assert result is None
