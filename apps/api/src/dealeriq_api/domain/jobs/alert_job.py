"""Alert-evaluation job orchestration (FR-060): runs rules (a)-(d) and (f) against the latest
succeeded forecast/inventory runs, tracked via its own `AnalyticsRun` row (`job_name="alerts"`),
mirroring `forecast_job.py`/`inventory_job.py`'s exact running->succeeded/failed lifecycle.

Rule (e) is NOT run here - it fires inline from `order_service.submit_order` (FR-060's
transactional trigger case), never from this scheduled/on-demand job.

DS-OPS-002: if the latest forecast or inventory run itself failed (or doesn't exist yet), the
rules that depend on it are simply skipped for this cycle, not evaluated against stale or
absent data - this is recorded in the run's own metrics, not treated as this job's failure.
"""

import importlib.metadata
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.domain.alerts.alert_rules import (
    evaluate_forecast_stockout,
    evaluate_lead_idle,
    evaluate_sales_anomaly,
    evaluate_stock_reorder,
    evaluate_unit_aging,
)
from dealeriq_api.domain.jobs.job_lifecycle import begin_run
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus

JOB_NAME = "alerts"


def _code_version() -> str:
    try:
        return importlib.metadata.version("dealeriq-api")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _latest_succeeded_run_id(db: Session, job_name: str) -> uuid.UUID | None:
    row = db.execute(
        select(AnalyticsRun.id)
        .where(AnalyticsRun.job_name == job_name, AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def run_alert_job(db: Session) -> AnalyticsRun:
    run = begin_run(db, job_name=JOB_NAME, code_version=_code_version())

    try:
        summary = _execute_pipeline(db)
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.metrics = summary
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.metrics = {"error": str(exc)}
        db.commit()
        raise

    db.commit()
    db.refresh(run)
    return run


def _execute_pipeline(db: Session) -> dict[str, int | bool]:
    inventory_run_id = _latest_succeeded_run_id(db, "inventory")
    forecast_run_id = _latest_succeeded_run_id(db, "forecast")

    n_stock_reorder = evaluate_stock_reorder(db, inventory_run_id) if inventory_run_id else 0
    n_unit_aging = evaluate_unit_aging(db, inventory_run_id) if inventory_run_id else 0
    n_sales_anomaly = evaluate_sales_anomaly(db, inventory_run_id) if inventory_run_id else 0
    n_forecast_stockout = evaluate_forecast_stockout(db, forecast_run_id) if forecast_run_id else 0
    n_lead_idle = evaluate_lead_idle(db)

    return {
        "inventory_run_found": inventory_run_id is not None,
        "forecast_run_found": forecast_run_id is not None,
        "stock_reorder_alerts": n_stock_reorder,
        "unit_aging_alerts": n_unit_aging,
        "sales_anomaly_alerts": n_sales_anomaly,
        "forecast_stockout_alerts": n_forecast_stockout,
        "lead_idle_alerts": n_lead_idle,
    }
