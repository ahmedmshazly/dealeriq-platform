"""InventoryIntel, UnitRisk, Anomaly - Phase 5's analytics tables (DS-INV-001..004,
DS-ANO-001..004). Schema per SRS §7's representative-resources list verbatim, all FK'd back to
Phase 4's `analytics_runs` (reused, not duplicated - FR-070 already covers "every analytics
execution," not just forecasting). DAT-003: analytics tables, never touched by transactional
code, never mutated in place once a run completes.

`InventoryIntel` is one row per (run, model, branch): ABC/XYZ is a model-level classification
(same value repeated across every branch row for that model, since revenue/demand-variability
ranking per the SRS's own DS-INV-001 wording is model-wide) denormalized alongside the
branch-specific reorder point, so a caller gets everything about one model at one branch from a
single row rather than a join.

`Anomaly.esd_confirmed` is an addition beyond SRS §7's abbreviated column list - DS-ANO-002
explicitly requires "both scores are stored," which needs a column to hold the ESD result
(nullable: `None` when the series had too little history for ESD to run at all, not merely
"not confirmed").
"""

import uuid
from datetime import date

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin

ANOMALY_STATUS_NEW = "new"


class InventoryIntel(IdMixin, Base):
    __tablename__ = "inventory_intel"
    __table_args__ = (
        Index("ix_inventory_intel_run_id_model_id_branch_id", "run_id", "model_id", "branch_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_models.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    abc: Mapped[str] = mapped_column(String(1))
    xyz: Mapped[str] = mapped_column(String(1))
    revenue_share: Mapped[float] = mapped_column(Float)
    demand_cv: Mapped[float] = mapped_column(Float)
    reorder_point: Mapped[float | None] = mapped_column(Float, default=None)
    safety_stock: Mapped[float | None] = mapped_column(Float, default=None)
    service_level: Mapped[float | None] = mapped_column(Float, default=None)
    skipped_reason: Mapped[str | None] = mapped_column(String(255), default=None)
    """Set (with reorder_point/safety_stock/service_level left null) when this (model, branch)
    has no succeeded Phase 4 forecast run yet - never fabricated (spec.md User Story 2)."""


class UnitRisk(IdMixin, Base):
    __tablename__ = "unit_risk"
    __table_args__ = (Index("ix_unit_risk_run_id_unit_id", "run_id", "unit_id"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_units.id"))
    days_on_lot: Mapped[int] = mapped_column(Integer)
    is_aging: Mapped[bool] = mapped_column(default=False)
    p_sale_30d: Mapped[float | None] = mapped_column(Float, default=None)
    risk_decile: Mapped[int | None] = mapped_column(Integer, default=None)
    """1 = worst decile (least likely to sell within 30 days, flagged for pricing review),
    10 = best. Null when the unit's segment doesn't have enough survival-curve history yet."""


class Anomaly(IdMixin, Base):
    __tablename__ = "anomalies"
    __table_args__ = (Index("ix_anomalies_run_id_scope", "run_id", "scope"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    scope: Mapped[str] = mapped_column(String(20))
    """"series" (DS-ANO-001/002) or "transaction" (DS-ANO-003)."""
    entity_key: Mapped[str] = mapped_column(String(255))
    """A series_key (Phase 4's convention, e.g. "model:<uuid>::branch:<uuid>") for scope=series,
    or an order id for scope=transaction."""
    week_start: Mapped[date | None] = mapped_column(default=None)
    observed: Mapped[float] = mapped_column(Float)
    expected: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40))
    severity: Mapped[float] = mapped_column(Float)
    esd_confirmed: Mapped[bool | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(20), default=ANOMALY_STATUS_NEW)
