#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_llm_router
from core.atena_llm_router import AtenaLLMRouter


class _FakeOpenAI:
    def __init__(self, api_key, base_url=None):
        self.api_key = api_key
        self.base_url = base_url


def test_set_backend_custom_with_inline_base_url(monkeypatch):
    monkeypatch.setattr(atena_llm_router, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("ATENA_CUSTOM_API_KEY", "test-key")

    router = AtenaLLMRouter()
    ok, msg = router.set_backend("custom:gpt-4o-mini@https://example.com/v1")

    assert ok is True
    assert "backend custom ativado" in msg
    assert router.cfg.provider == "custom"
    assert router.cfg.model == "gpt-4o-mini"
    assert router.cfg.base_url == "https://example.com/v1"


def test_set_backend_compat_requires_base_url(monkeypatch):
    monkeypatch.setattr(atena_llm_router, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("ATENA_OPENAI_BASE_URL", raising=False)

    router = AtenaLLMRouter()
    ok, msg = router.set_backend("compat:gpt-4.1-mini")

    assert ok is False
    assert "ATENA_OPENAI_BASE_URL" in msg


def test_auto_prepare_local_model_runs_by_default(monkeypatch):
    monkeypatch.setattr(atena_llm_router, "OpenAI", _FakeOpenAI)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1")

    called = {"value": False}

    def _fake_prepare(self):
        called["value"] = True
        return True, "prepared"

    monkeypatch.setattr(AtenaLLMRouter, "prepare_free_local_model", _fake_prepare)

    router = AtenaLLMRouter()
    assert called["value"] is True
    assert router.auto_prepare_result == (True, "prepared")


def test_auto_prepare_local_model_can_be_disabled(monkeypatch):
    monkeypatch.setattr(atena_llm_router, "OpenAI", _FakeOpenAI)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "0")

    called = {"value": False}

    def _fake_prepare(self):
        called["value"] = True
        return True, "prepared"

    monkeypatch.setattr(AtenaLLMRouter, "prepare_free_local_model", _fake_prepare)

    router = AtenaLLMRouter()
    assert called["value"] is False
    assert router.auto_prepare_result is None
