"""Job registry entry for the alert-evaluation job (ADR-004). Mirrors `jobs/forecast.py` and
`jobs/inventory.py` exactly."""

from dealeriq_api.domain.alert_job import JOB_NAME, run_alert_job

__all__ = ["JOB_NAME", "run_alert_job"]
