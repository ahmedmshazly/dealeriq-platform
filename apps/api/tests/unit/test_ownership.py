import uuid

from dealeriq_api.auth.ownership import may_act_on

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


def test_owner_may_act_without_any_permission() -> None:
    assert (
        may_act_on(
            granted=set(), any_permission_key="leads:manage_any", user_id=OWNER, owner_id=OWNER
        )
        is True
    )


def test_non_owner_without_any_permission_is_denied() -> None:
    assert (
        may_act_on(
            granted=set(), any_permission_key="leads:manage_any", user_id=OTHER, owner_id=OWNER
        )
        is False
    )


def test_non_owner_with_manage_any_permission_is_allowed() -> None:
    assert (
        may_act_on(
            granted={"leads:manage_any"},
            any_permission_key="leads:manage_any",
            user_id=OTHER,
            owner_id=OWNER,
        )
        is True
    )


def test_unrelated_permission_does_not_grant_access() -> None:
    assert (
        may_act_on(
            granted={"orders:manage_any"},
            any_permission_key="leads:manage_any",
            user_id=OTHER,
            owner_id=OWNER,
        )
        is False
    )
