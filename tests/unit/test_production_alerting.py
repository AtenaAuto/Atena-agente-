from pathlib import Path
from unittest.mock import patch

from core.production_observability import dispatch_alert


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_dispatch_alert_success_mocked():
    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        payload = dispatch_alert("https://example.com/webhook", {"a": 1})
    assert payload["sent"] is True
    assert payload["http_status"] == 200


def test_dispatch_alert_deduped(tmp_path: Path):
    state = tmp_path / "alerts.json"
    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        first = dispatch_alert("https://example.com/webhook", {"a": 1}, state_path=state, dedupe_window_sec=999)
        second = dispatch_alert("https://example.com/webhook", {"a": 1}, state_path=state, dedupe_window_sec=999)
    assert first["sent"] is True
    assert second["sent"] is False
    assert second.get("deduped") is True


def test_dispatch_alert_retries_then_success(tmp_path: Path):
    calls = {"n": 0}

    def _urlopen(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("temporary")
        return _FakeResponse()

    with patch("urllib.request.urlopen", side_effect=_urlopen), patch("time.sleep", return_value=None):
        payload = dispatch_alert(
            "https://example.com/webhook",
            {"b": 2},
            retries=2,
            backoff_sec=0,
            state_path=tmp_path / "alerts.json",
        )

    assert payload["sent"] is True
    assert payload["attempt"] == 2
