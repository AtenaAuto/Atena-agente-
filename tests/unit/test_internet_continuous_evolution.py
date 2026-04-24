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
            "evolution_signal": {"trend": "improving"},
        }

    monkeypatch.setattr(internet_challenge, "run_internet_challenge", _fake_run)

    report = internet_challenge.run_continuous_internet_evolution("ai agents", cycles=3)

    assert report["trend"] == "improving"
    assert report["best_weighted_confidence"] == 0.7
    assert report["delta_weighted_confidence"] == 0.3
    assert len(report["runs"]) == 3
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
