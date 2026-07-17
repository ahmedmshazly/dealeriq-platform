"""APScheduler activation (ADR-004, DS-OPS-001): the first real cron registrations — Phase 4/5
each only registered a `job_name` for the on-demand HTTP trigger, deferring actual scheduling to
this phase.

Every scheduled job calls the *exact same function* `POST /jobs/{name}/run` already calls, each
opening its own DB session directly (no HTTP request context to inject one from) — so
DS-OPS-002's idempotency guarantee covers a cron firing and an on-demand HTTP trigger uniformly,
and the FR-072 concurrency guard (checked inside each job's own transaction) prevents a cron
firing from colliding with a manual trigger that's still running.

Only started when `settings.enable_scheduler=True` (see core/config.py's docstring on why this
defaults off) — `make dev` is the only caller that turns it on.
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session, sessionmaker

from dealeriq_api.core.db import engine
from dealeriq_api.domain.jobs.alert_job import run_alert_job
from dealeriq_api.domain.jobs.digest_job import run_digest_job
from dealeriq_api.domain.jobs.forecast_job import run_forecast_job
from dealeriq_api.domain.jobs.inventory_job import run_inventory_job
from dealeriq_api.domain.jobs.lead_scoring_job import run_lead_scoring_job

logger = logging.getLogger("dealeriq_api.scheduler")

_SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _run_with_own_session(job_fn: Callable[[Session], object], job_label: str) -> None:
    db = _SessionLocal()
    try:
        job_fn(db)
    except Exception:
        logger.exception("Scheduled job '%s' failed", job_label)
    finally:
        db.close()


def _run_forecast() -> None:
    _run_with_own_session(run_forecast_job, "forecast")


def _run_inventory() -> None:
    _run_with_own_session(run_inventory_job, "inventory")


def _run_alerts() -> None:
    _run_with_own_session(run_alert_job, "alerts")


def _run_digest() -> None:
    _run_with_own_session(run_digest_job, "digest")


def _run_lead_scoring() -> None:
    _run_with_own_session(run_lead_scoring_job, "lead_scoring")


def create_scheduler() -> BackgroundScheduler:
    """DS-OPS-001's default schedule, all five jobs now registered."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_forecast, trigger="cron", day_of_week="mon", hour=2, id="forecast")
    scheduler.add_job(_run_inventory, trigger="cron", hour=3, id="inventory")
    scheduler.add_job(_run_alerts, trigger="cron", hour=3, minute=30, id="alerts")
    scheduler.add_job(_run_lead_scoring, trigger="cron", hour=4, id="lead_scoring")
    scheduler.add_job(_run_digest, trigger="cron", hour=7, id="digest")
    return scheduler
