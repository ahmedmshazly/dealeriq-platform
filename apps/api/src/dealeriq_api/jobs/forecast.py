"""Job registry entry for the forecast job (ADR-004, FR-072).

This phase only needs the job addressable by name for the on-demand HTTP trigger
(`POST /jobs/forecast/run`, wired directly to `run_forecast_job` in `routes/jobs.py` — no
background scheduler is instantiated yet, since nothing needs one until Phase 6 adds cron
triggers). `JOB_NAME` here is the single source of truth `routes/jobs.py`'s job registry and
`domain/forecast_job.py`'s `AnalyticsRun.job_name` both key off of, so the two can't drift apart.
"""

from dealeriq_api.domain.jobs.forecast_job import JOB_NAME, run_forecast_job

__all__ = ["JOB_NAME", "run_forecast_job"]
