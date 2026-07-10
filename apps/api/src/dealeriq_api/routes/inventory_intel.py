"""GET /inventory/abc-xyz (heatmap), GET /inventory/models/{model_id} (drill-down),
GET /inventory/units (aging/risk list), GET /anomalies (list) — DS-INV-001..004, DS-ANO-001..004.

All default to the latest `succeeded` "inventory" run; pass `?run_id=` for a historical one —
same convention Phase 4's forecasts routes established.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import not_found
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.branch import Branch
from dealeriq_api.domain.models.inventory_intel import Anomaly, InventoryIntel, UnitRisk
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import VehicleModel, VehicleUnit
from dealeriq_api.jobs.inventory import JOB_NAME
from dealeriq_api.schemas.inventory_intel import (
    AnomalyListResponse,
    AnomalyResponse,
    HeatmapCell,
    HeatmapCellEntry,
    HeatmapResponse,
    ModelDetailResponse,
    ReorderPointEntry,
    UnitRiskListResponse,
    UnitRiskResponse,
)

router = APIRouter(prefix="/api/v1", tags=["inventory-intel"])


def _resolve_run(db: Session, run_id: uuid.UUID | None) -> AnalyticsRun:
    if run_id is not None:
        run = db.get(AnalyticsRun, run_id)
        if run is None:
            raise not_found("Run not found.")
        return run
    run = (
        db.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == JOB_NAME, AnalyticsRun.status == RunStatus.SUCCEEDED)
            .order_by(AnalyticsRun.finished_at.desc())
        )
        .scalars()
        .first()
    )
    if run is None:
        raise not_found("No successful inventory run exists yet.")
    return run


def _model_names(db: Session, model_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not model_ids:
        return {}
    rows = db.execute(select(VehicleModel).where(VehicleModel.id.in_(model_ids))).scalars().all()
    return {m.id: f"{m.make} {m.model}" for m in rows}


def _branch_names(db: Session, branch_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not branch_ids:
        return {}
    rows = db.execute(select(Branch).where(Branch.id.in_(branch_ids))).scalars().all()
    return {b.id: b.name for b in rows}


@router.get("/inventory/abc-xyz", response_model=HeatmapResponse)
def heatmap_route(
    run_id: uuid.UUID | None = Query(default=None),
    _current_user: User = Depends(require_permission("inventory-intel:view")),
    db: Session = Depends(get_db),
) -> HeatmapResponse:
    run = _resolve_run(db, run_id)
    rows = db.execute(select(InventoryIntel).where(InventoryIntel.run_id == run.id)).scalars().all()

    seen_models: set[uuid.UUID] = set()
    by_cell: dict[tuple[str, str], list[InventoryIntel]] = {}
    for row in rows:
        if row.model_id in seen_models:
            continue
        seen_models.add(row.model_id)
        by_cell.setdefault((row.abc, row.xyz), []).append(row)

    model_names = _model_names(db, seen_models)
    cells = []
    for abc in ("A", "B", "C"):
        for xyz in ("X", "Y", "Z"):
            entries = by_cell.get((abc, xyz), [])
            cells.append(
                HeatmapCell(
                    abc=abc,
                    xyz=xyz,
                    models=[
                        HeatmapCellEntry(
                            model_id=e.model_id,
                            model_name=model_names.get(e.model_id, str(e.model_id)),
                            revenue_share=e.revenue_share,
                            demand_cv=e.demand_cv,
                        )
                        for e in entries
                    ],
                )
            )
    return HeatmapResponse(run_id=run.id, cells=cells)


@router.get("/inventory/models/{model_id}", response_model=ModelDetailResponse)
def model_detail_route(
    model_id: uuid.UUID,
    run_id: uuid.UUID | None = Query(default=None),
    _current_user: User = Depends(require_permission("inventory-intel:view")),
    db: Session = Depends(get_db),
) -> ModelDetailResponse:
    run = _resolve_run(db, run_id)
    model = db.get(VehicleModel, model_id)
    if model is None:
        raise not_found("Model not found.")

    intel_rows = (
        db.execute(
            select(InventoryIntel).where(
                InventoryIntel.run_id == run.id, InventoryIntel.model_id == model_id
            )
        )
        .scalars()
        .all()
    )
    if not intel_rows:
        raise not_found("Model has no inventory intelligence in this run.")

    branch_names = _branch_names(db, {r.branch_id for r in intel_rows})
    reorder_points = [
        ReorderPointEntry(
            branch_id=r.branch_id,
            branch_name=branch_names.get(r.branch_id, str(r.branch_id)),
            reorder_point=r.reorder_point,
            safety_stock=r.safety_stock,
            service_level=r.service_level,
            skipped_reason=r.skipped_reason,
        )
        for r in intel_rows
    ]

    unit_rows = db.execute(
        select(UnitRisk, VehicleUnit)
        .join(VehicleUnit, VehicleUnit.id == UnitRisk.unit_id)
        .where(UnitRisk.run_id == run.id, VehicleUnit.model_id == model_id)
    ).all()
    at_risk_units = [
        UnitRiskResponse(
            unit_id=unit_risk.unit_id,
            vin=unit.vin,
            model_id=model_id,
            model_name=f"{model.make} {model.model}",
            branch_id=unit.branch_id,
            branch_name=branch_names.get(unit.branch_id, str(unit.branch_id)),
            days_on_lot=unit_risk.days_on_lot,
            is_aging=unit_risk.is_aging,
            p_sale_30d=unit_risk.p_sale_30d,
            risk_decile=unit_risk.risk_decile,
        )
        for unit_risk, unit in unit_rows
    ]

    return ModelDetailResponse(
        run_id=run.id,
        model_id=model_id,
        model_name=f"{model.make} {model.model}",
        abc=intel_rows[0].abc,
        xyz=intel_rows[0].xyz,
        reorder_points=reorder_points,
        at_risk_units=at_risk_units,
    )


@router.get("/inventory/units", response_model=UnitRiskListResponse)
def unit_risk_list_route(
    run_id: uuid.UUID | None = Query(default=None),
    aging_only: bool = Query(default=False),
    worst_decile_only: bool = Query(default=False),
    _current_user: User = Depends(require_permission("inventory-intel:view")),
    db: Session = Depends(get_db),
) -> UnitRiskListResponse:
    run = _resolve_run(db, run_id)
    query = (
        select(UnitRisk, VehicleUnit, VehicleModel)
        .join(VehicleUnit, VehicleUnit.id == UnitRisk.unit_id)
        .join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
        .where(UnitRisk.run_id == run.id)
    )
    if aging_only:
        query = query.where(UnitRisk.is_aging.is_(True))
    if worst_decile_only:
        query = query.where(UnitRisk.risk_decile == 1)
    rows = db.execute(query).all()

    branch_names = _branch_names(db, {unit.branch_id for _, unit, _ in rows})
    units = [
        UnitRiskResponse(
            unit_id=unit_risk.unit_id,
            vin=unit.vin,
            model_id=model.id,
            model_name=f"{model.make} {model.model}",
            branch_id=unit.branch_id,
            branch_name=branch_names.get(unit.branch_id, str(unit.branch_id)),
            days_on_lot=unit_risk.days_on_lot,
            is_aging=unit_risk.is_aging,
            p_sale_30d=unit_risk.p_sale_30d,
            risk_decile=unit_risk.risk_decile,
        )
        for unit_risk, unit, model in rows
    ]
    return UnitRiskListResponse(run_id=run.id, units=units)


def _anomaly_display_name(db: Session, anomaly: Anomaly) -> str:
    if anomaly.scope != "series":
        return anomaly.entity_key
    parts = anomaly.entity_key.split("::")
    if len(parts) != 3 or not parts[2].startswith("branch:"):
        return anomaly.entity_key
    series_type, first_part, branch_part = parts
    branch_id = branch_part.removeprefix("branch:")
    branch = db.get(Branch, uuid.UUID(branch_id))
    branch_name = branch.name if branch is not None else branch_id
    label = series_type.replace("_", " ").title()

    if first_part.startswith("model:"):
        model = db.get(VehicleModel, uuid.UUID(first_part.removeprefix("model:")))
        model_name = f"{model.make} {model.model}" if model is not None else first_part
        return f"{label}: {model_name} @ {branch_name}"
    if first_part.startswith("segment:"):
        segment = first_part.removeprefix("segment:")
        return f"{label}: {segment.title()} @ {branch_name}"
    return anomaly.entity_key


@router.get("/anomalies", response_model=AnomalyListResponse)
def anomaly_list_route(
    run_id: uuid.UUID | None = Query(default=None),
    scope: str | None = Query(default=None),
    min_severity: float | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _current_user: User = Depends(require_permission("inventory-intel:view")),
    db: Session = Depends(get_db),
) -> AnomalyListResponse:
    run = _resolve_run(db, run_id)
    query = select(Anomaly).where(Anomaly.run_id == run.id)
    if scope is not None:
        query = query.where(Anomaly.scope == scope)
    if min_severity is not None:
        query = query.where(Anomaly.severity >= min_severity)
    if status_filter is not None:
        query = query.where(Anomaly.status == status_filter)
    query = query.order_by(Anomaly.severity.desc())
    rows = db.execute(query).scalars().all()

    anomalies = [
        AnomalyResponse(
            id=a.id,
            scope=a.scope,
            entity_key=a.entity_key,
            display_name=_anomaly_display_name(db, a),
            week_start=a.week_start,
            observed=a.observed,
            expected=a.expected,
            score=a.score,
            method=a.method,
            severity=a.severity,
            esd_confirmed=a.esd_confirmed,
            status=a.status,
        )
        for a in rows
    ]
    return AnomalyListResponse(run_id=run.id, anomalies=anomalies)
