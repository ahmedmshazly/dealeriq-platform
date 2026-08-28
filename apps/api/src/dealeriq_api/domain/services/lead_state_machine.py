"""Lead status state machine (FR-031). A pure function, deliberately decoupled from the DB -
unit-tested against every legal and illegal transition pair before being wired into the route.

`lost` is reachable from any non-terminal state (real sales funnels abandon at any stage); `won`
and `lost` are terminal. Nothing skips forward past `negotiating` in one hop.
"""

from dealeriq_api.domain.models.lead import LeadStatus

ALLOWED_TRANSITIONS: dict[LeadStatus, frozenset[LeadStatus]] = {
    LeadStatus.NEW: frozenset({LeadStatus.CONTACTED, LeadStatus.LOST}),
    LeadStatus.CONTACTED: frozenset(
        {LeadStatus.TEST_DRIVE, LeadStatus.NEGOTIATING, LeadStatus.LOST}
    ),
    LeadStatus.TEST_DRIVE: frozenset({LeadStatus.NEGOTIATING, LeadStatus.LOST}),
    LeadStatus.NEGOTIATING: frozenset({LeadStatus.WON, LeadStatus.LOST}),
    LeadStatus.WON: frozenset(),
    LeadStatus.LOST: frozenset(),
}


def is_valid_transition(current: LeadStatus, target: LeadStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


class InvalidLeadTransition(Exception):
    def __init__(self, current: LeadStatus, target: LeadStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition a lead from '{current.value}' to '{target.value}'.")


def validate_transition(current: LeadStatus, target: LeadStatus) -> None:
    if not is_valid_transition(current, target):
        raise InvalidLeadTransition(current, target)
