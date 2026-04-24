from __future__ import annotations

import json

from core import internet_challenge


def test_run_continuous_internet_evolution_builds_report(monkeypatch, tmp_path):
    monkeypatch.setattr(internet_challenge, "ROOT", tmp_path)

    confidences = iter([0.4, 0.55, 0.7])

    def _fake_run(topic: str):
        value = next(confidences)
        return {
            "status": "ok",
            "weighted_confidence": value,
            "difficulty_score": 1 - value,
            "synthesis": {
                "high_quality_sources": ["arxiv", "github"],
                "failed_sources": ["reddit"],
            },
            "best_api_sources": ["arxiv", "github"],
            "connectivity_summary": {"ok_ratio": 0.6},
            "evolution_signal": {"trend": "improving"},
        }

    monkeypatch.setattr(internet_challenge, "run_internet_challenge", _fake_run)

    report = internet_challenge.run_continuous_internet_evolution("ai agents", cycles=3)

    assert report["trend"] == "improving"
    assert report["best_weighted_confidence"] == 0.7
    assert report["delta_weighted_confidence"] == 0.3
    assert report["quality_gate"]["passed"] is True
    assert len(report["runs"]) == 3
    assert "query_variant_used" in report["runs"][0]
    assert report["report_path"] == "analysis_reports/ATENA_Continuous_Internet_Evolution.json"

    report_path = tmp_path / report["report_path"]
    assert report_path.exists()
    stored = json.loads(report_path.read_text(encoding="utf-8"))
    assert stored["trend"] == "improving"


def test_next_evolution_topic_includes_quality_and_failures():
    payload = {
        "synthesis": {
            "high_quality_sources": ["arxiv", "github"],
            "failed_sources": ["reddit", "duckduckgo"],
        }
    }

    topic = internet_challenge._next_evolution_topic("ai agents", payload, 2)

    assert "ai agents" in topic
    assert "arxiv" in topic
    assert "reddit" in topic


def test_run_continuous_internet_evolution_sets_quality_gate_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(internet_challenge, "ROOT", tmp_path)

    def _fake_run(topic: str):
        return {
            "status": "partial",
            "weighted_confidence": 0.1,
            "difficulty_score": 0.9,
            "synthesis": {"high_quality_sources": [], "failed_sources": ["wikipedia"]},
            "best_api_sources": [],
            "connectivity_summary": {"ok_ratio": 0.1},
            "evolution_signal": {"trend": "degrading"},
        }

    monkeypatch.setattr(internet_challenge, "run_internet_challenge", _fake_run)
    report = internet_challenge.run_continuous_internet_evolution("ai agents", cycles=2)
    assert report["quality_gate"]["passed"] is False
    assert "final_confidence_below_0_3" in report["quality_gate"]["reasons"]


def test_run_continuous_prefers_better_query_variant(monkeypatch, tmp_path):
    monkeypatch.setattr(internet_challenge, "ROOT", tmp_path)

    def _fake_run(topic: str):
        weighted = 0.1
        if "security" in topic.lower():
            weighted = 0.5
        return {
            "status": "ok" if weighted >= 0.5 else "partial",
            "weighted_confidence": weighted,
            "difficulty_score": 1 - weighted,
            "synthesis": {"high_quality_sources": [], "failed_sources": []},
            "best_api_sources": [],
            "connectivity_summary": {"ok_ratio": weighted},
            "evolution_signal": {"trend": "stable"},
        }

    monkeypatch.setattr(internet_challenge, "run_internet_challenge", _fake_run)
    report = internet_challenge.run_continuous_internet_evolution("segurança agentes", cycles=1)

    assert report["runs"][0]["query_variant_used"] == "security agents"
    assert report["final_weighted_confidence"] == 0.5
