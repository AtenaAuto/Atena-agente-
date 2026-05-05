from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_root_dashboard() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ATENA Dashboard" in resp.text


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_status_payload() -> None:
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "atena"
    assert data["status"] == "ok"
    assert "release" in data
    assert "environment" in data
    assert "started_at" in data


def test_request_id_header() -> None:
    resp = client.get("/healthz", headers={"x-request-id": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"
