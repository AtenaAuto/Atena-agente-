import json
from unittest.mock import patch

from core.internet_challenge import run_internet_challenge


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_urlopen(url: str, timeout: int = 15):
    if "wikipedia" in url:
        return _FakeResponse({"title": "AI", "extract": "Artificial intelligence summary"})
    if "github" in url:
        return _FakeResponse({"items": [{"full_name": "org/repo", "stargazers_count": 10}]})
    return _FakeResponse({"hits": [{"title": "HN story", "points": 42}]})


def test_run_internet_challenge_mocked():
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        payload = run_internet_challenge("artificial intelligence")
    assert payload["status"] == "ok"
    assert payload["confidence"] >= 0.8
    assert len(payload["sources"]) == 3
    assert payload["all_source_count"] >= 20
    assert "synthesis" in payload
    assert payload["synthesis"]["release_risk"] in {"low", "medium", "high"}
    assert 0.0 <= payload["difficulty_score"] <= 1.0
