"""_record_failed_login's window/threshold arithmetic, tested in isolation (no DB) against a
plain User instance - FR-005: lock after 5 consecutive failures *within 15 minutes*; a failure
outside the window restarts the count rather than accumulating forever.
"""

from datetime import UTC, datetime, timedelta

from dealeriq_api.auth.service import _record_failed_login
from dealeriq_api.domain.models.rbac import User

WINDOW = 15
MAX_ATTEMPTS = 5
DURATION = 15


def _fresh_user() -> User:
    return User(email="x@example.com", password_hash="irrelevant", role_id=None)


def test_first_failure_sets_count_to_one() -> None:
    user = _fresh_user()
    now = datetime.now(UTC)
    _record_failed_login(None, user, now, WINDOW, MAX_ATTEMPTS, DURATION)  # type: ignore[arg-type]
    assert user.failed_login_count == 1
    assert user.locked_until is None


def test_consecutive_failures_within_window_accumulate_and_lock_at_threshold() -> None:
    user = _fresh_user()
    now = datetime.now(UTC)
    for i in range(MAX_ATTEMPTS):
        _record_failed_login(None, user, now + timedelta(seconds=i), WINDOW, MAX_ATTEMPTS, DURATION)  # type: ignore[arg-type]
    assert user.failed_login_count == MAX_ATTEMPTS
    assert user.locked_until is not None
    assert user.locked_until > now


def test_failure_outside_the_window_resets_the_counter_instead_of_accumulating() -> None:
    user = _fresh_user()
    now = datetime.now(UTC)
    _record_failed_login(None, user, now, WINDOW, MAX_ATTEMPTS, DURATION)  # type: ignore[arg-type]
    assert user.failed_login_count == 1

    later = now + timedelta(minutes=WINDOW + 1)
    _record_failed_login(None, user, later, WINDOW, MAX_ATTEMPTS, DURATION)  # type: ignore[arg-type]
    assert user.failed_login_count == 1  # reset, not 2
