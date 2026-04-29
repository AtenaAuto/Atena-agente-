from __future__ import annotations

from types import SimpleNamespace

import core.atena_llm_router as llm_router
from core.atena_llm_router import AtenaLLMRouter


def test_auto_orchestrate_prefers_qwen_when_dashscope_key(monkeypatch):
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "0")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dummy")
    monkeypatch.setattr(llm_router, "OpenAI", lambda **kwargs: object())
    router = AtenaLLMRouter()

    monkeypatch.setattr(router, "set_backend", lambda spec: (True, f"set:{spec}"))

    ok, msg = router.auto_orchestrate_llm()

    assert ok is True
    assert "seleção automática" in msg
    assert "qwen:" in msg


def test_auto_orchestrate_falls_back_to_local_and_prepares(monkeypatch):
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "0")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    router = AtenaLLMRouter()

    monkeypatch.setattr(router, "set_backend", lambda spec: (True, "backend local ativado"))
    fake_brain = SimpleNamespace(
        cfg=SimpleNamespace(base_model_name=""),
        prepare_runtime_model=lambda: (True, "ok"),
    )
    monkeypatch.setattr(router, "_get_local_brain", lambda: fake_brain)

    ok, msg = router.auto_orchestrate_llm()

    assert ok is True
    assert "local-brain pronto" in msg
