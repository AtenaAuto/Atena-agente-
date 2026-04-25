import json
from unittest.mock import patch

from core.internet_challenge import _fetch_raw, _normalize_api_entries, run_internet_challenge


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
    assert isinstance(payload["best_api_sources"], list)
    assert "connectivity_summary" in payload
    assert 0.0 <= payload["connectivity_summary"]["ok_ratio"] <= 1.0
    assert "synthesis" in payload
    assert payload["synthesis"]["release_risk"] in {"low", "medium", "high"}
    assert 0.0 <= payload["difficulty_score"] <= 1.0
    assert "evolution_signal" in payload
    assert payload["evolution_signal"]["trend"] in {"improving", "stable", "degrading"}


def test_fetch_raw_blocks_non_top_domain_when_policy_enabled(monkeypatch):
    monkeypatch.setenv("ATENA_ENFORCE_TOP_API_DOMAINS", "1")
    with patch("urllib.request.urlopen") as mocked:
        try:
            _fetch_raw("https://example.com/search")
            assert False, "era esperado bloqueio de domínio fora da allowlist"
        except RuntimeError as exc:
            assert "domínio bloqueado por política top-api" in str(exc)
        mocked.assert_not_called()


def test_fetch_raw_allows_top_domain_when_policy_enabled(monkeypatch):
    monkeypatch.setenv("ATENA_ENFORCE_TOP_API_DOMAINS", "1")
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        payload = _fetch_raw("https://api.github.com/search/repositories?q=atena")
    assert "org/repo" in payload


def test_normalize_api_entries_filters_insecure_endpoints_by_default():
    rows = [
        {"name": "Secure", "endpoint": "https://secure.example/api", "category": "testing"},
        {"name": "Insecure", "endpoint": "http://insecure.example/api", "category": "testing"},
    ]
    normalized = _normalize_api_entries(rows)
    endpoints = [item["endpoint"] for item in normalized]
    assert "https://secure.example/api" in endpoints
    assert "http://insecure.example/api" not in endpoints


def test_fetch_raw_blocks_insecure_http_by_default():
    try:
        _fetch_raw("http://example.com/api")
        assert False, "era esperado bloqueio de HTTP inseguro"
    except RuntimeError as exc:
        assert "requisição insegura bloqueada" in str(exc)


def test_fetch_raw_blocks_invalid_scheme():
    try:
        _fetch_raw("file:///tmp/data.json")
        assert False, "era esperado bloqueio de esquema inválido"
    except RuntimeError as exc:
        assert "esquema de URL inválido" in str(exc)
