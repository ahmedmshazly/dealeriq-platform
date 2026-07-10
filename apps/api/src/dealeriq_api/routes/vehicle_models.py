"""GET/POST /vehicle-models (FR-020)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.inventory_service import create_vehicle_model, list_vehicle_models
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import VehicleModel
from dealeriq_api.schemas.inventory import VehicleModelCreateRequest, VehicleModelResponse

router = APIRouter(prefix="/api/v1/vehicle-models", tags=["vehicle-models"])


def _to_response(m: VehicleModel) -> VehicleModelResponse:
    return VehicleModelResponse(
        id=m.id,
        make=m.make,
        model=m.model,
        trim=m.trim,
        segment=m.segment,
        list_price=float(m.list_price),
    )


@router.get("", response_model=list[VehicleModelResponse])
def list_vehicle_models_route(
    _current_user: User = Depends(require_permission("inventory:view")),
    db: Session = Depends(get_db),
) -> list[VehicleModelResponse]:
    return [_to_response(m) for m in list_vehicle_models(db)]


@router.post("", response_model=VehicleModelResponse, status_code=201)
def create_vehicle_model_route(
    body: VehicleModelCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
) -> VehicleModelResponse:
    ip = request.client.host if request.client else None
    vehicle_model = create_vehicle_model(
        db,
        actor_id=current_user.id,
        make=body.make,
        model=body.model,
        trim=body.trim,
        segment=body.segment,
        list_price=body.list_price,
        ip=ip,
    )
    return _to_response(vehicle_model)
