import pytest

from dealeriq_api.domain.lead_state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidLeadTransition,
    is_valid_transition,
    validate_transition,
)
from dealeriq_api.domain.models.lead import LeadStatus

ALL_STATUSES = list(LeadStatus)

LEGAL_PAIRS = [
    (current, target) for current, targets in ALLOWED_TRANSITIONS.items() for target in targets
]

ILLEGAL_PAIRS = [
    (current, target)
    for current in ALL_STATUSES
    for target in ALL_STATUSES
    if target not in ALLOWED_TRANSITIONS[current]
]


@pytest.mark.parametrize("current,target", LEGAL_PAIRS)
def test_every_legal_transition_is_accepted(current: LeadStatus, target: LeadStatus) -> None:
    assert is_valid_transition(current, target) is True
    validate_transition(current, target)  # must not raise


@pytest.mark.parametrize("current,target", ILLEGAL_PAIRS)
def test_every_illegal_transition_is_rejected(current: LeadStatus, target: LeadStatus) -> None:
    assert is_valid_transition(current, target) is False
    with pytest.raises(InvalidLeadTransition):
        validate_transition(current, target)


def test_won_and_lost_are_terminal() -> None:
    assert ALLOWED_TRANSITIONS[LeadStatus.WON] == frozenset()
    assert ALLOWED_TRANSITIONS[LeadStatus.LOST] == frozenset()


def test_lost_is_reachable_from_every_non_terminal_state() -> None:
    for status in (
        LeadStatus.NEW,
        LeadStatus.CONTACTED,
        LeadStatus.TEST_DRIVE,
        LeadStatus.NEGOTIATING,
    ):
        assert LeadStatus.LOST in ALLOWED_TRANSITIONS[status]


def test_new_cannot_jump_straight_to_won() -> None:
    assert is_valid_transition(LeadStatus.NEW, LeadStatus.WON) is False
