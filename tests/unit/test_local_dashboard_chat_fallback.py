from __future__ import annotations

from core.atena_local_dashboard import Handler


class _ExternalOn:
    enabled = True

    def ask(self, prompt: str) -> str:
        return f"external:{prompt}"


class _ExternalFail:
    enabled = True

    def ask(self, prompt: str) -> str:
        raise RuntimeError("down")


class _ExternalOff:
    enabled = False

    def ask(self, prompt: str) -> str:
        raise AssertionError("must not be called")


class _Router:
    def generate(self, prompt: str, context: str) -> str:
        return f"local:{prompt}:{context}"


def test_resolve_chat_answer_prefers_external(monkeypatch):
    monkeypatch.setattr(Handler, "external_client", _ExternalOn())
    monkeypatch.setattr(Handler, "router", _Router())

    answer, source = Handler.resolve_chat_answer("oi")

    assert answer == "external:oi"
    assert source == "external"


def test_resolve_chat_answer_uses_local_fallback(monkeypatch):
    monkeypatch.setattr(Handler, "external_client", _ExternalFail())
    monkeypatch.setattr(Handler, "router", _Router())

    answer, source = Handler.resolve_chat_answer("oi")

    assert answer.startswith("local:oi:")
    assert source == "local-fallback"


def test_resolve_chat_answer_local_only(monkeypatch):
    monkeypatch.setattr(Handler, "external_client", _ExternalOff())
    monkeypatch.setattr(Handler, "router", _Router())

    answer, source = Handler.resolve_chat_answer("oi")

    assert answer.startswith("local:oi:")
    assert source == "local"
