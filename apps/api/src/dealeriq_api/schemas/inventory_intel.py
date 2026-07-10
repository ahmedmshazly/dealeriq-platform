"""Request/response models for inventory intelligence & anomalies (DS-INV-001..004,
DS-ANO-001..004)."""

import uuid
from datetime import date

from pydantic import BaseModel


class HeatmapCellEntry(BaseModel):
    model_id: uuid.UUID
    model_name: str
    revenue_share: float
    demand_cv: float


class HeatmapCell(BaseModel):
    abc: str
    xyz: str
    models: list[HeatmapCellEntry]


class HeatmapResponse(BaseModel):
    run_id: uuid.UUID
    cells: list[HeatmapCell]


class ReorderPointEntry(BaseModel):
    branch_id: uuid.UUID
    branch_name: str
    reorder_point: float | None
    safety_stock: float | None
    service_level: float | None
    skipped_reason: str | None


class UnitRiskResponse(BaseModel):
    unit_id: uuid.UUID
    vin: str
    model_id: uuid.UUID
    model_name: str
    branch_id: uuid.UUID
    branch_name: str
    days_on_lot: int
    is_aging: bool
    p_sale_30d: float | None
    risk_decile: int | None


class ModelDetailResponse(BaseModel):
    run_id: uuid.UUID
    model_id: uuid.UUID
    model_name: str
    abc: str
    xyz: str
    reorder_points: list[ReorderPointEntry]
    at_risk_units: list[UnitRiskResponse]


class UnitRiskListResponse(BaseModel):
    run_id: uuid.UUID
    units: list[UnitRiskResponse]


class AnomalyResponse(BaseModel):
    id: uuid.UUID
    scope: str
    entity_key: str
    display_name: str
    week_start: date | None
    observed: float
    expected: float
    score: float
    method: str
    severity: float
    esd_confirmed: bool | None
    status: str


class AnomalyListResponse(BaseModel):
    run_id: uuid.UUID
    anomalies: list[AnomalyResponse]
