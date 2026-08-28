"""Generic owner-or-permission check (FR-012): Sales users may only edit resources they own;
Managers and Admins may edit any. A route requires `<resource>:manage_own` OR
`<resource>:manage_any` to be callable at all (require_permission_any); this function then
decides, once the specific resource is loaded, whether *this* caller may act on *this* row.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import get_current_user, get_user_permissions
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import forbidden
from dealeriq_api.domain.models.rbac import User


def require_any_permission(*permission_keys: str) -> Callable[..., User]:
    """At least one of the given permissions must be granted - used for routes where the finer
    own-vs-any distinction is resolved later by `assert_owner_or_permission`."""

    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        granted = get_user_permissions(db, current_user.role_id)
        if not (set(permission_keys) & granted):
            raise forbidden(
                f"Requires one of {sorted(permission_keys)}, which your role does not grant."
            )
        return current_user

    return dependency


def may_act_on(
    *, granted: set[str], any_permission_key: str, user_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """Pure decision (no DB) - unit-tested directly against every combination of granted
    permissions and owner/non-owner callers."""
    return any_permission_key in granted or user_id == owner_id


def assert_owner_or_permission(
    *,
    db: Session,
    current_user: User,
    any_permission_key: str,
    owner_id: uuid.UUID,
) -> None:
    granted = get_user_permissions(db, current_user.role_id)
    if not may_act_on(
        granted=granted,
        any_permission_key=any_permission_key,
        user_id=current_user.id,
        owner_id=owner_id,
    ):
        raise forbidden("You may only act on resources you own.")


def resolve_owner_filter(
    *,
    granted: set[str],
    manage_any_key: str,
    manage_own_key: str,
    current_user_id: uuid.UUID,
    requested_owner_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Resolve list/get owner scoping for reads.

    - manage_any → honour optional client filter (unscoped if None).
    - manage_own without manage_any → force current user (Sales).
    - view-only (e.g. Analyst) → unscoped (optional client filter still applies).
    """
    if manage_any_key in granted:
        return requested_owner_id
    if manage_own_key in granted:
        return current_user_id
    return requested_owner_id


def can_view_owned_resource(
    *,
    granted: set[str],
    manage_any_key: str,
    manage_own_key: str,
    current_user_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> bool:
    """True if the caller may read a single owned resource (get-by-id / timeline)."""
    if manage_any_key in granted:
        return True
    if manage_own_key in granted:
        return current_user_id == owner_id
    # view-only roles (Analyst): dealership-wide read
    return True
