#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_terminal_assistant import build_claude_mode_prompt


def test_build_claude_mode_prompt_contains_required_sections():
    prompt = build_claude_mode_prompt("Implementar CLI de auditoria")
    assert "Objetivo" in prompt
    assert "Plano técnico" in prompt
    assert "Comandos exatos" in prompt
    assert "Validação" in prompt
    assert "Riscos e rollback" in prompt
