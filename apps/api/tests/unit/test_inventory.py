from datetime import date, timedelta

from dealeriq_api.domain.inventory_service import days_on_lot
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleUnit


def _unit(acquisition_date: date) -> VehicleUnit:
    return VehicleUnit(
        vin="1FT7X2B69KEA12345",
        model_id=None,  # type: ignore[arg-type]
        branch_id=None,  # type: ignore[arg-type]
        status=UnitStatus.IN_STOCK,
        acquisition_date=acquisition_date,
        acquisition_cost=10000,
    )


def test_days_on_lot_for_a_unit_acquired_today_is_zero() -> None:
    assert days_on_lot(_unit(date.today())) == 0


def test_days_on_lot_counts_whole_days_since_acquisition() -> None:
    assert days_on_lot(_unit(date.today() - timedelta(days=45))) == 45
