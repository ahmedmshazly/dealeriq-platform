"""FR-004 / FR-072: concurrent RUNNING rows for the same job_name are rejected."""

import pytest
from sqlalchemy.orm import Session

from dealeriq_api.core.errors import ApiError
from dealeriq_api.domain.jobs.job_lifecycle import begin_run
from dealeriq_api.domain.models.analytics import RunStatus


def test_begin_run_rejects_second_running_row_for_same_job(db_session: Session) -> None:
    first = begin_run(db_session, job_name="forecast", code_version="test")
    assert first.status == RunStatus.RUNNING
    db_session.commit()

    with pytest.raises(ApiError) as exc_info:
        begin_run(db_session, job_name="forecast", code_version="test")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "conflict"

    # A different job may still start.
    other = begin_run(db_session, job_name="inventory", code_version="test")
    assert other.status == RunStatus.RUNNING
    db_session.rollback()
