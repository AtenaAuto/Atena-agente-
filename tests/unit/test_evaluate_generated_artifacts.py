from __future__ import annotations

import json

from scripts.evaluate_generated_artifacts import evaluate_artifact


def test_evaluate_markdown_artifact_scores_plan_keywords(tmp_path):
    md = tmp_path / "plan.md"
    md.write_text(
        "# Plano\nArquitetura multiagente\nMVP\nMétricas\nrollback\n",
        encoding="utf-8",
    )
    score = evaluate_artifact(md)
    assert score.overall >= 3.0
    assert score.actionability >= 4


def test_evaluate_json_artifact_scores_enterprise_fields(tmp_path):
    payload = {
        "internet_research_engine": {"weighted_confidence": 0.86},
        "sre_auto_hardening": {"regression": {"risk": "high"}},
        "security_redaction": {"status": "ok"},
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    score = evaluate_artifact(report)
    assert score.evidence >= 3
    assert score.risk >= 4
