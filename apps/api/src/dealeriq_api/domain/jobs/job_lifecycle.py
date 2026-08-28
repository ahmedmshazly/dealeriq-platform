"""Shared analytics-run lifecycle helpers (FR-070..072).

`begin_run` inserts and *commits* the RUNNING row before any heavy work so the partial unique
index on `(job_name) WHERE status = 'RUNNING'` is visible to other sessions - concurrent
triggers get 409 instead of serializing then double-executing.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dealeriq_api.core.errors import conflict
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus


def is_job_running(db: Session, job_name: str) -> bool:
    from sqlalchemy import select

    existing = db.execute(
        select(AnalyticsRun.id).where(
            AnalyticsRun.job_name == job_name, AnalyticsRun.status == RunStatus.RUNNING
        )
    ).first()
    return existing is not None


def begin_run(
    db: Session,
    *,
    job_name: str,
    code_version: str,
    params: dict[str, Any] | None = None,
    seed: int | None = None,
    data_from: date | None = None,
    data_to: date | None = None,
) -> AnalyticsRun:
    """Insert a RUNNING analytics_runs row and commit it; raise 409 if one is already running."""
    if is_job_running(db, job_name):
        raise conflict(f"A '{job_name}' run is already in progress.")

    today = datetime.now(UTC).date()
    run = AnalyticsRun(
        job_name=job_name,
        params=params or {},
        seed=seed,
        code_version=code_version,
        data_from=data_from or today,
        data_to=data_to or today,
        status=RunStatus.RUNNING,
        metrics={},
        started_at=datetime.now(UTC),
    )
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError as exc:
        raise conflict(f"A '{job_name}' run is already in progress.") from exc
    # Durable claim before heavy work so other sessions see RUNNING immediately.
    db.commit()
    db.refresh(run)
    return run
