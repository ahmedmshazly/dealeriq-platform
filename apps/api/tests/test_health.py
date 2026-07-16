from fastapi.testclient import TestClient

from dealeriq_api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_response_carries_request_id_header() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers


def test_health_response_carries_security_headers() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src" in response.headers["Content-Security-Policy"]
