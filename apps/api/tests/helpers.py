"""Shared integration-test helpers — login/user-creation boilerplate used across every
resource's integration test module."""

import uuid

from fastapi.testclient import TestClient

BOOTSTRAP_EMAIL = "admin@dealeriq.dev"
BOOTSTRAP_PASSWORD = "ChangeMe123!"


def login(client: TestClient, email: str, password: str):  # noqa: ANN201
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def admin_token(client: TestClient) -> str:
    resp = login(client, BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD)
    assert resp.status_code == 200
    return resp.json()["access_token"]


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
    """Creates a fresh user of the given role and returns their access token."""
    _, email, temp_password = create_user(client, token, role_key)
    resp = login(client, email, temp_password)
    assert resp.status_code == 200
    return resp.json()["access_token"]
