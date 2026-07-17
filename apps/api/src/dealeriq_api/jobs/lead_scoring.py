"""Job registry entry for the customer-analytics job (ADR-004). Mirrors `jobs/forecast.py`,
`jobs/inventory.py`, and `jobs/alerts.py` exactly."""

from dealeriq_api.domain.jobs.lead_scoring_job import JOB_NAME, run_lead_scoring_job

__all__ = ["JOB_NAME", "run_lead_scoring_job"]
