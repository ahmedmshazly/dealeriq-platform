import uuid

from dealeriq_api.auth.ownership import can_view_owned_resource, may_act_on, resolve_owner_filter

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


def test_resolve_owner_filter_forces_self_for_manage_own() -> None:
    assert (
        resolve_owner_filter(
            granted={"leads:manage_own", "leads:view"},
            manage_any_key="leads:manage_any",
            manage_own_key="leads:manage_own",
            current_user_id=OWNER,
            requested_owner_id=OTHER,
        )
        == OWNER
    )


def test_resolve_owner_filter_honours_request_for_manage_any() -> None:
    assert (
        resolve_owner_filter(
            granted={"leads:manage_any", "leads:view"},
            manage_any_key="leads:manage_any",
            manage_own_key="leads:manage_own",
            current_user_id=OWNER,
            requested_owner_id=OTHER,
        )
        == OTHER
    )


def test_resolve_owner_filter_unscoped_for_view_only() -> None:
    assert (
        resolve_owner_filter(
            granted={"leads:view"},
            manage_any_key="leads:manage_any",
            manage_own_key="leads:manage_own",
            current_user_id=OWNER,
            requested_owner_id=None,
        )
        is None
    )


def test_can_view_owned_resource_sales_own_only() -> None:
    assert (
        can_view_owned_resource(
            granted={"orders:manage_own", "orders:view"},
            manage_any_key="orders:manage_any",
            manage_own_key="orders:manage_own",
            current_user_id=OWNER,
            owner_id=OWNER,
        )
        is True
    )
    assert (
        can_view_owned_resource(
            granted={"orders:manage_own", "orders:view"},
            manage_any_key="orders:manage_any",
            manage_own_key="orders:manage_own",
            current_user_id=OWNER,
            owner_id=OTHER,
        )
        is False
    )
