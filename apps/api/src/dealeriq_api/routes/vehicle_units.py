"""GET/POST /vehicle-units, POST /vehicle-units/{id}/adjust (FR-020..024, API-001)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.inventory_service import (
    adjust_unit,
    create_vehicle_unit,
    list_vehicle_units,
)
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import UnitStatus
from dealeriq_api.schemas.inventory import (
    VehicleUnitAdjustRequest,
    VehicleUnitCreateRequest,
    VehicleUnitResponse,
)

router = APIRouter(prefix="/api/v1/vehicle-units", tags=["vehicle-units"])


@router.get("", response_model=Page[VehicleUnitResponse])
def list_vehicle_units_route(
    branch_id: uuid.UUID | None = None,
    model_id: uuid.UUID | None = None,
    segment: str | None = None,
    status: UnitStatus | None = None,
    min_days_on_lot: int | None = None,
    max_days_on_lot: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(require_permission("inventory:view")),
    db: Session = Depends(get_db),
) -> Page[VehicleUnitResponse]:
    units, total = list_vehicle_units(
        db,
        branch_id=branch_id,
        model_id=model_id,
        segment=segment,
        status=status,
        min_days_on_lot=min_days_on_lot,
        max_days_on_lot=max_days_on_lot,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[VehicleUnitResponse.from_model(u) for u in units],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=VehicleUnitResponse, status_code=201)
def create_vehicle_unit_route(
    body: VehicleUnitCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
) -> VehicleUnitResponse:
    ip = request.client.host if request.client else None
    unit = create_vehicle_unit(
        db,
        actor_id=current_user.id,
        vin=body.vin,
        model_id=body.model_id,
        branch_id=body.branch_id,
        acquisition_date=body.acquisition_date,
        acquisition_cost=body.acquisition_cost,
        ip=ip,
    )
    return VehicleUnitResponse.from_model(unit)


@router.post("/{unit_id}/adjust", response_model=VehicleUnitResponse)
def adjust_vehicle_unit_route(
    unit_id: uuid.UUID,
    body: VehicleUnitAdjustRequest,
    request: Request,
    current_user: User = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
) -> VehicleUnitResponse:
    ip = request.client.host if request.client else None
    unit = adjust_unit(
        db,
        actor_id=current_user.id,
        unit_id=unit_id,
        new_status=body.new_status,
        reason=body.reason,
        ip=ip,
    )
    return VehicleUnitResponse.from_model(unit)
