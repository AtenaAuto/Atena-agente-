#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from core.atena_local_lm import AtenaUltraBrain, AtenaCognitiveConfig


def test_simbrain_generates_advanced_cli_for_todo_fixme_prompt(tmp_path: Path):
    cfg = AtenaCognitiveConfig(
        base_dir=tmp_path / "brain",
        model_dir=tmp_path / "brain" / "models",
        memory_dir=tmp_path / "brain" / "memory",
    )
    brain = AtenaUltraBrain(cfg)

    prompt = (
        "Crie uma ferramenta Python avançada estilo Claude Code: "
        "um CLI que varre um repositório, detecta TODO/FIXME, "
        "gera relatório markdown e JSON."
    )
    answer = brain.think(prompt)

    assert "argparse" in answer
    assert "TODO" in answer
    assert "FIXME" in answer
    assert "write_markdown" in answer
    assert "write_json" in answer


def test_simbrain_generates_claude_structured_output(tmp_path: Path):
    cfg = AtenaCognitiveConfig(
        base_dir=tmp_path / "brain2",
        model_dir=tmp_path / "brain2" / "models",
        memory_dir=tmp_path / "brain2" / "memory",
    )
    brain = AtenaUltraBrain(cfg)
    prompt = (
        "Responda no estilo Claude Code. Formato obrigatório com objetivo, plano, comandos, código, validação e riscos."
    )
    answer = brain.think(prompt)
    assert "## 1) Objetivo" in answer
    assert "## 2) Plano técnico" in answer
    assert "## 3) Comandos exatos para executar" in answer
    assert "## 4) Código" in answer
    assert "## 5) Validação" in answer
    assert "## 6) Riscos e rollback" in answer
