"""POST /jobs/{job_name}/run, GET /jobs/{job_name}/runs (FR-070..072, C-03).

`job_name` is a path segment (not yet an enum) since later phases register more jobs (alerts,
...) against the same two endpoints — Phase 4 added "forecast", Phase 5 adds "inventory".
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import bad_request, conflict
from dealeriq_api.domain.forecast_job import is_job_running
from dealeriq_api.domain.models.analytics import AnalyticsRun
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.jobs.forecast import JOB_NAME as FORECAST_JOB_NAME
from dealeriq_api.jobs.forecast import run_forecast_job
from dealeriq_api.jobs.inventory import JOB_NAME as INVENTORY_JOB_NAME
from dealeriq_api.jobs.inventory import run_inventory_job
from dealeriq_api.schemas.forecasts import AnalyticsRunResponse

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

KNOWN_JOBS: dict[str, Callable[[Session], AnalyticsRun]] = {
    FORECAST_JOB_NAME: run_forecast_job,
    INVENTORY_JOB_NAME: run_inventory_job,
}


@router.post("/{job_name}/run", response_model=AnalyticsRunResponse, status_code=201)
def trigger_job_route(
    job_name: str,
    _current_user: User = Depends(require_permission("jobs:trigger")),
    db: Session = Depends(get_db),
) -> AnalyticsRunResponse:
    if job_name not in KNOWN_JOBS:
        raise bad_request(f"Unknown job '{job_name}'.")
    if is_job_running(db, job_name):
        raise conflict(f"A '{job_name}' run is already in progress.")

    run_fn = KNOWN_JOBS[job_name]
    run = run_fn(db)
    return AnalyticsRunResponse.from_model(run)


@router.get("/{job_name}/runs", response_model=list[AnalyticsRunResponse])
def list_job_runs_route(
    job_name: str,
    _current_user: User = Depends(require_permission("jobs:view")),
    db: Session = Depends(get_db),
) -> list[AnalyticsRunResponse]:
    if job_name not in KNOWN_JOBS:
        raise bad_request(f"Unknown job '{job_name}'.")
    runs = (
        db.execute(
            select(AnalyticsRun)
            .where(AnalyticsRun.job_name == job_name)
            .order_by(AnalyticsRun.started_at.desc())
        )
        .scalars()
        .all()
    )
    return [AnalyticsRunResponse.from_model(r) for r in runs]
