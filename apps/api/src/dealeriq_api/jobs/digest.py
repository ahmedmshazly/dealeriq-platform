"""Job registry entry for the daily digest job (ADR-004). Mirrors `jobs/forecast.py` and
`jobs/inventory.py` exactly."""

from dealeriq_api.domain.digest_job import JOB_NAME, run_digest_job

__all__ = ["JOB_NAME", "run_digest_job"]
