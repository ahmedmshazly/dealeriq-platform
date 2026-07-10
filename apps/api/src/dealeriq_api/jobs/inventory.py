"""Job registry entry for the inventory intelligence & anomaly-detection job (ADR-004).

Mirrors `jobs/forecast.py` exactly: `JOB_NAME` here is the single source of truth
`routes/jobs.py`'s job registry and `domain/inventory_job.py`'s `AnalyticsRun.job_name` both key
off of, so the two can't drift apart. No background scheduler instantiated yet (Phase 6's
concern), same as forecast.
"""

from dealeriq_api.domain.inventory_job import JOB_NAME, run_inventory_job

__all__ = ["JOB_NAME", "run_inventory_job"]
