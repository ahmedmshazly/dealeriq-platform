"""Vehicle models/units, the append-only stock-movement ledger, and stock adjustments
(FR-020..024). Unit status is always changed alongside a ledger row in the same transaction —
there is no path that updates `vehicle_units.status` without a corresponding `stock_movements`
insert (DAT-003).
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.core.errors import bad_request, not_found
from dealeriq_api.domain.audit import write_audit_row
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.vehicle import (
    MovementType,
    StockMovement,
    UnitStatus,
    VehicleModel,
    VehicleUnit,
)


def create_branch(db: Session, *, name: str, city: str) -> Branch:
    branch = Branch(name=name, city=city)
    db.add(branch)
    db.commit()
    return branch


def list_branches(db: Session) -> list[Branch]:
    return list(db.execute(select(Branch).order_by(Branch.name)).scalars().all())


def create_vehicle_model(
    db: Session,
    *,
    actor_id: uuid.UUID,
    make: str,
    model: str,
    trim: str | None,
    segment: str,
    list_price: float,
    ip: str | None,
) -> VehicleModel:
    vehicle_model = VehicleModel(
        make=make, model=model, trim=trim, segment=segment, list_price=list_price
    )
    db.add(vehicle_model)
    db.flush()
    write_audit_row(
        db,
        actor_id=actor_id,
        action="vehicle_model.created",
        entity_type="vehicle_model",
        entity_id=str(vehicle_model.id),
        after={"make": make, "model": model, "segment": segment, "list_price": str(list_price)},
        ip=ip,
    )
    db.commit()
    return vehicle_model


def list_vehicle_models(db: Session) -> list[VehicleModel]:
    return list(db.execute(select(VehicleModel).order_by(VehicleModel.make)).scalars().all())


def create_vehicle_unit(
    db: Session,
    *,
    actor_id: uuid.UUID,
    vin: str,
    model_id: uuid.UUID,
    branch_id: uuid.UUID,
    acquisition_date: date,
    acquisition_cost: float,
    ip: str | None,
) -> VehicleUnit:
    if db.get(VehicleModel, model_id) is None:
        raise bad_request(f"Unknown vehicle model '{model_id}'.")
    if db.get(Branch, branch_id) is None:
        raise bad_request(f"Unknown branch '{branch_id}'.")

    unit = VehicleUnit(
        vin=vin,
        model_id=model_id,
        branch_id=branch_id,
        status=UnitStatus.IN_STOCK,
        acquisition_date=acquisition_date,
        acquisition_cost=acquisition_cost,
    )
    db.add(unit)
    db.flush()

    db.add(
        StockMovement(
            unit_id=unit.id,
            type=MovementType.RECEIPT,
            to_branch_id=branch_id,
            actor_id=actor_id,
            occurred_at=datetime.now(UTC),
        )
    )
    write_audit_row(
        db,
        actor_id=actor_id,
        action="vehicle_unit.received",
        entity_type="vehicle_unit",
        entity_id=str(unit.id),
        after={"vin": vin, "branch_id": str(branch_id)},
        ip=ip,
    )
    db.commit()
    return unit


def days_on_lot(unit: VehicleUnit) -> int:
    return (date.today() - unit.acquisition_date).days


def list_vehicle_units(
    db: Session,
    *,
    branch_id: uuid.UUID | None,
    model_id: uuid.UUID | None,
    segment: str | None,
    status: UnitStatus | None,
    min_days_on_lot: int | None,
    max_days_on_lot: int | None,
    limit: int,
    offset: int,
) -> tuple[list[VehicleUnit], int]:
    stmt = select(VehicleUnit).join(VehicleModel, VehicleUnit.model_id == VehicleModel.id)

    if branch_id is not None:
        stmt = stmt.where(VehicleUnit.branch_id == branch_id)
    if model_id is not None:
        stmt = stmt.where(VehicleUnit.model_id == model_id)
    if segment is not None:
        stmt = stmt.where(VehicleModel.segment == segment)
    if status is not None:
        stmt = stmt.where(VehicleUnit.status == status)

    all_rows = list(db.execute(stmt).scalars().unique().all())

    if min_days_on_lot is not None:
        all_rows = [u for u in all_rows if days_on_lot(u) >= min_days_on_lot]
    if max_days_on_lot is not None:
        all_rows = [u for u in all_rows if days_on_lot(u) <= max_days_on_lot]

    total = len(all_rows)
    all_rows.sort(key=lambda u: u.acquisition_date)
    page = all_rows[offset : offset + limit]
    return page, total


def adjust_unit(
    db: Session,
    *,
    actor_id: uuid.UUID,
    unit_id: uuid.UUID,
    new_status: UnitStatus,
    reason: str,
    ip: str | None,
) -> VehicleUnit:
    if not reason or not reason.strip():
        raise bad_request("A reason is required for stock adjustments (FR-024).")

    unit = db.get(VehicleUnit, unit_id)
    if unit is None:
        raise not_found("Vehicle unit not found.")

    before_status = unit.status
    unit.status = new_status
    db.add(
        StockMovement(
            unit_id=unit.id,
            type=MovementType.ADJUSTMENT,
            actor_id=actor_id,
            reason=reason,
            occurred_at=datetime.now(UTC),
        )
    )
    write_audit_row(
        db,
        actor_id=actor_id,
        action="vehicle_unit.adjusted",
        entity_type="vehicle_unit",
        entity_id=str(unit.id),
        before={"status": before_status.value},
        after={"status": new_status.value, "reason": reason},
        ip=ip,
    )
    db.commit()
    return unit
