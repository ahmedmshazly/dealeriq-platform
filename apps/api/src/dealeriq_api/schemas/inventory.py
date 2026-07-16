"""Request/response models for branches, vehicle models, and vehicle units (FR-020..024)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from dealeriq_api.domain.inventory_service import days_on_lot
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleUnit


class BranchCreateRequest(BaseModel):
    name: str
    city: str


class BranchResponse(BaseModel):
    id: uuid.UUID
    name: str
    city: str


class VehicleModelCreateRequest(BaseModel):
    make: str
    model: str
    trim: str | None = None
    segment: str
    list_price: float = Field(gt=0)


class VehicleModelResponse(BaseModel):
    id: uuid.UUID
    make: str
    model: str
    trim: str | None
    segment: str
    list_price: float


class VehicleUnitCreateRequest(BaseModel):
    vin: str = Field(min_length=11, max_length=17)
    model_id: uuid.UUID
    branch_id: uuid.UUID
    acquisition_date: date
    acquisition_cost: float = Field(gt=0)


class VehicleUnitAdjustRequest(BaseModel):
    new_status: UnitStatus
    reason: str = Field(min_length=1)


class VehicleUnitResponse(BaseModel):
    id: uuid.UUID
    vin: str
    model_id: uuid.UUID
    branch_id: uuid.UUID
    status: UnitStatus
    acquisition_date: date
    # FR-043: cost/margin is Manager+ only — null for callers without orders:view_margin.
    acquisition_cost: float | None
    days_on_lot: int
    # Analytics outputs (DS-INV, Phase 5) — not populated until that phase's job has run.
    abc_class: str | None = None
    xyz_class: str | None = None
    aging_risk_score: float | None = None

    @classmethod
    def from_model(cls, unit: VehicleUnit, *, include_cost: bool = False) -> "VehicleUnitResponse":
        return cls(
            id=unit.id,
            vin=unit.vin,
            model_id=unit.model_id,
            branch_id=unit.branch_id,
            status=unit.status,
            acquisition_date=unit.acquisition_date,
            acquisition_cost=float(unit.acquisition_cost) if include_cost else None,
            days_on_lot=days_on_lot(unit),
        )
