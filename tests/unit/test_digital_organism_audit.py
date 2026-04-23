#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace

from core.atena_digital_organism_audit import (
    classify_stage,
    run_digital_organism_audit,
    save_digital_organism_audit,
)


def test_classify_stage_thresholds():
    assert classify_stage(95.0) == "organismo_digital_v1_operacional"
    assert classify_stage(85.0) == "organismo_digital_emergente"
    assert classify_stage(70.0) == "agente_autonomo_em_transicao"
    assert classify_stage(20.0) == "sistema_automatizado_nao_organico"


def test_run_digital_organism_audit_partial_score(monkeypatch, tmp_path: Path):
    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ANN001
        command = " ".join(cmd)
        if "agi-external-validation" in command:
            return SimpleNamespace(returncode=0, stdout="score_0_100=40.0", stderr="")
        if "guardian" in command:
            return SimpleNamespace(returncode=2, stdout="guardian failed", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("core.atena_digital_organism_audit.subprocess.run", fake_run)
    payload = run_digital_organism_audit(tmp_path, timeout_seconds=2)

    assert payload["score_0_100"] < 90.0
    assert payload["score_1_10"] > 0
    assert 0.0 <= payload["confidence_0_1"] <= 1.0
    assert payload["stage"] in {
        "organismo_digital_emergente",
        "agente_autonomo_em_transicao",
    }
    assert len(payload["checks"]) == 5
    assert "trend" in payload
    assert "recommendations" in payload


def test_save_digital_organism_audit_writes_artifacts(tmp_path: Path):
    payload = {
        "score_0_100": 91.5,
        "score_1_10": 9.15,
        "stage": "organismo_digital_v1_operacional",
        "verdict": "ATENA atende critérios de organismo digital operacional (v1).",
        "confidence_0_1": 0.9,
        "trend": {"samples": 1, "mean_score_0_100": 90.0, "delta_vs_mean": 1.5, "direction": "up"},
        "checks": [
            {
                "id": "doctor",
                "pillar": "safety-runtime",
                "command": ["./atena", "doctor"],
                "weight": 1.0,
                "score_factor": 1.0,
                "ok": True,
                "evidence": {"external_score_0_100": None, "parsed_json_path": None, "parsed_markdown_path": None},
            }
        ],
        "recommendations": ["r1"],
        "missing_capabilities": ["x"],
    }
    json_path, md_path = save_digital_organism_audit(tmp_path, payload)
    assert json_path.exists()
    assert md_path.exists()
