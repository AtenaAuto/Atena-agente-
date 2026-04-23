#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_terminal_assistant as ta


def test_prompt_label_has_professional_format():
    label = ta.prompt_label("local:sim")
    assert "ATENA ✦" in label
    assert "local:sim" in label
    assert ">" in label


def test_print_assistant_output_plain_mode(monkeypatch):
    monkeypatch.setattr(ta, "HAS_RICH", False)
    ta.print_assistant_output("Resposta simples")
