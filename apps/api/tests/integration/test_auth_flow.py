"""Integration tests against a real, ephemeral Postgres (testcontainers, ADR-013): login,
lockout, refresh rotation + reuse detection, logout, RBAC 403s, and audit rows.
"""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import (
    BOOTSTRAP_EMAIL,
    BOOTSTRAP_PASSWORD,
    admin_token,
    create_user,
    login,
    usable_token,
)


def test_me_returns_the_authenticated_users_own_profile(client: TestClient) -> None:
    token = admin_token(client)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == BOOTSTRAP_EMAIL
    assert body["role_key"] == "admin"


def test_login_happy_path_returns_access_token_and_refresh_cookie(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "analyst")
    resp = login(client, email, temp_password)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["must_change_password"] is True
    assert "dealeriq_refresh" in resp.cookies


def test_must_change_password_blocks_protected_routes_until_changed(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "sales")
    raw_login = login(client, email, temp_password)
    assert raw_login.status_code == 200
    assert raw_login.json()["must_change_password"] is True
    blocked_token = raw_login.json()["access_token"]

    blocked = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {blocked_token}"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {blocked_token}"})
    assert me.status_code == 200

    token = usable_token(client, email, temp_password)
    ok = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    resp = login(client, BOOTSTRAP_EMAIL, "definitely-wrong")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_unauthenticated_request_is_401(client: TestClient) -> None:
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_sales_role_gets_403_on_admin_only_route(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "sales")
    sales_token = usable_token(client, email, temp_password)

    resp = client.post(
        "/api/v1/users",
        json={"email": "nope@dealeriq.dev", "role_key": "sales"},
        headers={"Authorization": f"Bearer {sales_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_admin_succeeds_on_the_route_the_sales_user_was_forbidden_from(
    client: TestClient,
) -> None:
    token = admin_token(client)
    resp = client.post(
        "/api/v1/users",
        json={"email": f"ok-{uuid.uuid4().hex[:8]}@dealeriq.dev", "role_key": "sales"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


def test_manager_can_view_but_not_manage_users(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "manager")
    manager_token = usable_token(client, email, temp_password)

    view_resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {manager_token}"})
    assert view_resp.status_code == 200

    manage_resp = client.post(
        "/api/v1/users",
        json={"email": "nope2@dealeriq.dev", "role_key": "sales"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manage_resp.status_code == 403


def test_lockout_after_five_failed_attempts_then_admin_unlock(client: TestClient) -> None:
    admin = admin_token(client)
    user_id, email, temp_password = create_user(client, admin, "sales")

    for _ in range(5):
        resp = login(client, email, "wrong-password")
        assert resp.status_code == 401

    locked_resp = login(client, email, "wrong-password")
    assert locked_resp.status_code == 423
    assert locked_resp.json()["error"]["code"] == "account_locked"

    # Even the correct password is rejected while locked.
    still_locked = login(client, email, temp_password)
    assert still_locked.status_code == 423

    unlock_resp = client.patch(
        f"/api/v1/users/{user_id}",
        json={"unlock": True},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert unlock_resp.status_code == 200
    assert unlock_resp.json()["locked_until"] is None

    unlocked_login = login(client, email, temp_password)
    assert unlocked_login.status_code == 200


def test_refresh_rotates_the_token_and_reuse_revokes_the_whole_family(
    client: TestClient,
) -> None:
    login_resp = login(client, BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD)
    assert login_resp.status_code == 200
    original_cookie = login_resp.cookies.get("dealeriq_refresh")

    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200

    # Replay the ORIGINAL (now-superseded) cookie to simulate theft/reuse.
    reuse_resp = client.post("/api/v1/auth/refresh", cookies={"dealeriq_refresh": original_cookie})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "unauthorized"

    # The whole family — including the token just legitimately rotated to — is now revoked.
    second_refresh = client.post("/api/v1/auth/refresh")
    assert second_refresh.status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    login_resp = login(client, BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD)
    assert login_resp.status_code == 200
    cookie = login_resp.cookies.get("dealeriq_refresh")

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    refresh_resp = client.post("/api/v1/auth/refresh", cookies={"dealeriq_refresh": cookie})
    assert refresh_resp.status_code == 401


def test_user_creation_writes_an_audit_row(client: TestClient) -> None:
    admin = admin_token(client)
    user_id, email, _ = create_user(client, admin, "analyst")

    audit_resp = client.get(
        "/api/v1/audit-log",
        params={"entity_id": user_id},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert audit_resp.status_code == 200
    actions = {row["action"] for row in audit_resp.json()["items"]}
    assert "user.created" in actions
    created_row = next(row for row in audit_resp.json()["items"] if row["action"] == "user.created")
    assert created_row["after"]["email"] == email
    assert created_row["actor_email"] == BOOTSTRAP_EMAIL


def test_permission_matrix_reflects_seeded_grants(client: TestClient) -> None:
    # Checks the Phase 1 (auth/RBAC) permission set specifically, as a subset — later phases
    # (Phase 2's inventory/customers/leads/orders permissions, etc.) add more grants, and this
    # test shouldn't need updating every time a new permission ships. Phase-specific matrix
    # assertions live in that phase's own integration tests (e.g. test_inventory_flow.py).
    admin = admin_token(client)
    resp = client.get("/api/v1/permissions/matrix", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    matrix = {row["role_key"]: set(row["permissions"]) for row in resp.json()}
    assert {"users:view", "users:manage", "permissions:view", "audit_log:view"} <= matrix["admin"]
    assert {"users:view"} <= matrix["manager"]
    assert "users:manage" not in matrix["sales"]
    assert "users:manage" not in matrix["analyst"]


def test_change_password_requires_correct_current_password(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "analyst")
    # change-password is allowlisted while must_change_password is still true
    login_resp = login(client, email, temp_password)
    token = login_resp.json()["access_token"]
    refresh_cookie = login_resp.cookies.get("dealeriq_refresh")

    wrong_current = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-it", "new_password": "brand-new-pass-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wrong_current.status_code == 403

    correct = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temp_password, "new_password": "brand-new-pass-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert correct.status_code == 204

    # Refresh from the pre-change cookie must fail once sessions are revoked.
    refresh = client.post("/api/v1/auth/refresh", cookies={"dealeriq_refresh": refresh_cookie})
    assert refresh.status_code == 401

    relogin = login(client, email, "brand-new-pass-123")
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is False


def test_list_roles_returns_the_four_seeded_roles(client: TestClient) -> None:
    admin = admin_token(client)
    resp = client.get("/api/v1/roles", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    keys = {row["key"] for row in resp.json()}
    assert keys == {"admin", "manager", "sales", "analyst"}


def test_create_user_with_unknown_role_is_rejected(client: TestClient) -> None:
    admin = admin_token(client)
    resp = client.post(
        "/api/v1/users",
        json={"email": f"badrole-{uuid.uuid4().hex[:8]}@dealeriq.dev", "role_key": "nope"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


def test_create_user_with_duplicate_email_is_rejected(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, _ = create_user(client, admin, "analyst")
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "role_key": "analyst"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 400


def test_update_nonexistent_user_returns_404(client: TestClient) -> None:
    admin = admin_token(client)
    resp = client.patch(
        f"/api/v1/users/{uuid.uuid4()}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 404


def test_update_user_with_unknown_role_is_rejected(client: TestClient) -> None:
    admin = admin_token(client)
    user_id, _, _ = create_user(client, admin, "analyst")
    resp = client.patch(
        f"/api/v1/users/{user_id}",
        json={"role_key": "not-a-role"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert resp.status_code == 400


def test_logout_all_revokes_every_session_for_the_user(client: TestClient) -> None:
    admin = admin_token(client)
    _, email, temp_password = create_user(client, admin, "analyst")

    session_a = login(client, email, temp_password)
    cookie_a = session_a.cookies.get("dealeriq_refresh")
    token_a = session_a.json()["access_token"]

    session_b = client.post("/api/v1/auth/login", json={"email": email, "password": temp_password})
    cookie_b = session_b.cookies.get("dealeriq_refresh")

    logout_all_resp = client.post(
        "/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert logout_all_resp.status_code == 204

    refresh_a = client.post("/api/v1/auth/refresh", cookies={"dealeriq_refresh": cookie_a})
    assert refresh_a.status_code == 401
    refresh_b = client.post("/api/v1/auth/refresh", cookies={"dealeriq_refresh": cookie_b})
    assert refresh_b.status_code == 401


def test_deactivated_user_cannot_log_in(client: TestClient) -> None:
    admin = admin_token(client)
    user_id, email, temp_password = create_user(client, admin, "analyst")

    deactivate_resp = client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    login_resp = login(client, email, temp_password)
    assert login_resp.status_code == 401
