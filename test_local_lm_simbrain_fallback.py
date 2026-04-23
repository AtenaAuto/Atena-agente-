#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_local_lm import AtenaUltraBrain


def test_heuristic_greeting_returns_human_text():
    brain = AtenaUltraBrain()
    answer = brain._simulate_thinking("Oi Atena, tudo bem?")
    assert "heurístico" in answer
    assert "pronta para ajudar" in answer
    assert "Processando tarefa" not in answer


def test_heuristic_generic_fallback_mentions_prompt():
    brain = AtenaUltraBrain()
    answer = brain._simulate_thinking("Me ajude a organizar tarefas da sprint")
    assert "Entendi sua solicitação" in answer
    assert "Me ajude a organizar tarefas da sprint" in answer


def test_prepare_runtime_model_retries_after_auto_install(monkeypatch):
    brain = AtenaUltraBrain()
    brain.has_transformers = False
    calls = {"init": 0}

    def fake_init():
        calls["init"] += 1
        brain.has_transformers = calls["init"] >= 2

    monkeypatch.setattr(brain, "_init_model", fake_init)
    monkeypatch.setattr(brain, "_install_transformers_stack", lambda: (True, "ok"))

    ok, msg = brain.prepare_runtime_model()
    assert ok is True
    assert "Modelo local carregado" in msg
    assert calls["init"] == 2
