from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "atena-firezone-backend"


def test_matchmaking_ticket_roundtrip() -> None:
    client = TestClient(app)
    join = client.post("/matchmaking/join", json={"player_id": "player123", "mode": "br"})
    assert join.status_code == 200
    ticket = join.json()
    assert ticket["status"] == "queued"

    check = client.get(f"/matchmaking/ticket/{ticket['ticket_id']}")
    assert check.status_code == 200
    assert check.json()["player_id"] == "player123"


def test_matchmaking_rejects_invalid_mode() -> None:
    client = TestClient(app)
    join = client.post("/matchmaking/join", json={"player_id": "player123", "mode": "invalid"})
    assert join.status_code == 422
