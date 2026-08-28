"""Shared integration-test helpers - login/user-creation boilerplate used across every
resource's integration test module."""

import uuid

from fastapi.testclient import TestClient

BOOTSTRAP_EMAIL = "admin@dealeriq.dev"
BOOTSTRAP_PASSWORD = "ChangeMe123!"


def login(client: TestClient, email: str, password: str):  # noqa: ANN201
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def clear_must_change_password(client: TestClient, token: str, current_password: str) -> None:
    """FR-006 gate: clear must_change_password so subsequent API calls are not blocked."""
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": current_password, "new_password": current_password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text


def usable_token(client: TestClient, email: str, password: str) -> str:
    """Login and clear must_change_password if set; return a fully usable access token."""
    resp = login(client, email, password)
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    if resp.json().get("must_change_password"):
        clear_must_change_password(client, token, password)
    return token


def admin_token(client: TestClient) -> str:
    return usable_token(client, BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD)


def create_user(client: TestClient, token: str, role_key: str) -> tuple[str, str, str]:
    """Returns (user_id, email, temporary_password)."""
    email = f"{role_key}-{uuid.uuid4().hex[:8]}@dealeriq.dev"
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "role_key": role_key},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], email, body["temporary_password"]


def user_token(client: TestClient, token: str, role_key: str) -> str:
    """Creates a fresh user of the given role and returns their usable access token."""
    _, email, temp_password = create_user(client, token, role_key)
    return usable_token(client, email, temp_password)
