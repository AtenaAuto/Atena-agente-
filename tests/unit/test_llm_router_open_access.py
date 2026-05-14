from __future__ import annotations

from types import SimpleNamespace

from core.atena_llm_router import AtenaLLMRouter, RouterConfig


def test_open_access_mode_prefers_local_brain_over_paid_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("ATENA_OPEN_ACCESS_MODE", "1")
    router = AtenaLLMRouter(config=RouterConfig(open_access_mode=True, allow_paid_providers=True))
    fake_brain = SimpleNamespace(prepare_runtime_model=lambda: (True, "ok"))
    monkeypatch.setattr(router, "_get_local_brain", lambda: fake_brain)
    monkeypatch.setattr(router, "set_backend", lambda spec: (True, f"set:{spec}"))

    ok, msg = router.auto_orchestrate_llm()

    assert ok is True
    assert router.current() == "local:brain"
    assert "open-access" in msg
    assert "sem API paga" in msg


def test_open_access_plan_declares_no_paid_provider_required(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    router = AtenaLLMRouter(config=RouterConfig(open_access_mode=True, allow_paid_providers=False))

    plan = router.open_access_plan()

    assert plan["paid_provider_required"] is False
    assert plan["fallback_order"] == ["local:brain", "public-api:auto", "local:stub"]
    assert plan["paid_providers_enabled"] is False


def test_generate_uses_open_access_message_without_private_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    router = AtenaLLMRouter(config=RouterConfig(open_access_mode=True, allow_paid_providers=False))
    monkeypatch.setattr(router, "_has_internet", lambda: False)
    router._providers.clear()
    router._backend = "local:stub"

    response = router.generate("explique acesso aberto")

    assert "open-access" in response
    assert "nenhum provedor pago é necessário" in response
    assert "ATENA_OPEN_ACCESS_MODE=1" in response
