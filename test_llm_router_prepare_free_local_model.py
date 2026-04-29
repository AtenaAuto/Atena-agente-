#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_llm_router import AtenaLLMRouter


class _FakeBrain:
    def prepare_runtime_model(self):
        return True, "ok"


def test_prepare_free_local_model_uses_local_brain(monkeypatch):
    router = AtenaLLMRouter()
    monkeypatch.setattr(router, "_get_local_brain", lambda: _FakeBrain())
    ok, msg = router.prepare_free_local_model()
    assert ok is True
    assert msg == "ok"


def test_prepare_free_local_model_rejects_non_local_provider():
    router = AtenaLLMRouter()
    router.cfg.provider = "openai"
    ok, msg = router.prepare_free_local_model()
    assert ok is False
    assert "apenas para provider local" in msg
