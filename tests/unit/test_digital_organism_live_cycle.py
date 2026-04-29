#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

from core.atena_digital_organism_live_cycle import (
    _pick_project_type,
    _safe_project_name,
    run_live_cycle,
    run_live_cycles,
    run_live_daemon,
)


def test_pick_project_type_prefers_api_when_sources_strong():
    payload = {
        "weighted_confidence": 0.81,
        "sources": [
            {"source": "github", "quality_score": 0.8},
            {"source": "npm", "quality_score": 0.71},
        ],
    }
    assert _pick_project_type(payload) == "api"


def test_safe_project_name_truncates_long_topics():
    topic = "x" * 300
    name = _safe_project_name(topic)
    assert len(name) <= 90
    assert name.count("-") >= 1


def test_run_live_cycle_creates_memory_and_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "core.atena_digital_organism_live_cycle.run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "confidence": 0.9,
            "weighted_confidence": 0.75,
            "source_count": 3,
            "recommendation": "triangulate",
            "sources": [{"source": "github", "quality_score": 0.8}],
        },
    )

    payload = run_live_cycle(tmp_path, "autonomous coding")

    assert payload["build"]["ok"] is True
    assert payload["execution"]["ok"] is True
    assert Path(payload["memory_path"]).exists()
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()

    memory_lines = Path(payload["memory_path"]).read_text(encoding="utf-8").strip().splitlines()
    assert memory_lines
    last = json.loads(memory_lines[-1])
    assert last["topic"] == "autonomous coding"


def test_run_live_cycle_recovery_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "core.atena_digital_organism_live_cycle.run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "confidence": 0.9,
            "weighted_confidence": 0.8,
            "source_count": 4,
            "recommendation": "triangulate",
            "sources": [{"source": "github", "quality_score": 0.9}],
        },
    )

    def fake_build_and_validate(root, topic, project_type, code_module):  # noqa: ANN001
        if project_type == "api":
            return (
                {
                    "ok": True,
                    "project_type": "api",
                    "project_name": "x",
                    "output_dir": str(tmp_path / "x"),
                    "message": "ok",
                },
                {"ok": False, "reason": "simulated fail"},
            )
        return (
            {
                "ok": True,
                "project_type": project_type,
                "project_name": "fallback",
                "output_dir": str(tmp_path / "fallback"),
                "message": "ok",
            },
            {"ok": True, "reason": "fallback success"},
        )

    monkeypatch.setattr("core.atena_digital_organism_live_cycle._build_and_validate", fake_build_and_validate)
    payload = run_live_cycle(tmp_path, "self-heal-cycle", max_recovery_attempts=2)
    assert payload["status"] == "ok"
    assert payload["recovery_used"] is True
    assert payload["build"]["project_type"] in {"cli", "site"}


def test_run_live_cycles_batch_summary(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "core.atena_digital_organism_live_cycle.run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "confidence": 0.9,
            "weighted_confidence": 0.8,
            "source_count": 4,
            "recommendation": "triangulate",
            "sources": [{"source": "github", "quality_score": 0.9}],
        },
    )

    payload = run_live_cycles(tmp_path, seed_topic="agentic coding", iterations=2, strict=True)
    summary = payload["summary"]
    assert summary["iterations"] == 2
    assert summary["status"] == "ok"
    assert summary["consistently_learning"] is True
    assert Path(summary["batch_json"]).exists()
    assert Path(summary["batch_markdown"]).exists()


def test_run_live_daemon_generates_global_summary(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "core.atena_digital_organism_live_cycle.run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "confidence": 0.92,
            "weighted_confidence": 0.82,
            "source_count": 5,
            "recommendation": "triangulate",
            "sources": [{"source": "github", "quality_score": 0.91}],
        },
    )

    payload = run_live_daemon(
        tmp_path,
        seed_topic="agentic systems",
        batches=2,
        iterations_per_batch=2,
        strict=True,
    )
    summary = payload["summary"]
    assert summary["status"] == "ok"
    assert summary["batches"] == 2
    assert summary["avg_success_rate"] >= 0.9
    assert Path(summary["daemon_json"]).exists()
    assert Path(summary["daemon_markdown"]).exists()
