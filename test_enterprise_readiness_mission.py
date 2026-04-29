#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from protocols import atena_enterprise_readiness_mission as mission


def test_evaluate_generated_api_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(mission, "ROOT", tmp_path)
    app_dir = tmp_path / "atena_evolution" / "generated_apps" / "api_ok"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "main.py").write_text("@app.get('/health')\n@app.get('/idea')\n", encoding="utf-8")

    result = mission._evaluate_generated_api("api_ok", ["/health", "/idea"])

    assert result["ok"] is True
    assert result["missing_endpoints"] == []


def test_evaluate_generated_api_missing_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(mission, "ROOT", tmp_path)
    app_dir = tmp_path / "atena_evolution" / "generated_apps" / "api_missing"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "main.py").write_text("@app.get('/health')\n", encoding="utf-8")

    result = mission._evaluate_generated_api("api_missing", ["/health", "/idea"])

    assert result["ok"] is False
    assert result["missing_endpoints"] == ["/idea"]


def test_compute_score_penalizes_structure_failure():
    steps = [
        mission.StepResult("Doctor", ["python", "doctor.py"], 0, 0.1, "", ""),
        mission.StepResult("Production Gate", ["python", "prod.py"], 0, 0.1, "", ""),
        mission.StepResult("Professional Launch", ["python", "launch.py"], 0, 0.1, "", ""),
        mission.StepResult("Code Build API", ["python", "build.py"], 0, 0.1, "", ""),
    ]

    score_ok, _ = mission._compute_score(steps, structure_check_ok=True)
    score_fail, _ = mission._compute_score(steps, structure_check_ok=False)

    assert score_ok == 100
    assert score_fail == 90


def test_scan_for_secrets_detects_github_token(tmp_path, monkeypatch):
    monkeypatch.setattr(mission, "ROOT", tmp_path)
    leaked = tmp_path / "docs" / "leak.md"
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("token=" + ("ghp_" + "A" * 32), encoding="utf-8")

    result = mission._scan_for_secrets(max_findings=5)

    assert result["ok"] is False
    assert len(result["findings"]) == 1
    assert result["findings"][0]["file"] == "docs/leak.md"


def test_check_repo_clean_handles_non_git_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(mission, "ROOT", tmp_path)

    result = mission._check_repo_clean()

    assert result["ok"] is False
    assert result["returncode"] != 0


def test_apply_allowlist_filters_findings():
    scan = {
        "ok": False,
        "findings": [
            {"file": "docs/a.md", "line": 10, "pattern": "ghp_"},
            {"file": "docs/b.md", "line": 12, "pattern": "ghp_"},
        ],
        "scanned_files": 2,
    }
    filtered = mission._apply_allowlist(scan, [r"docs/a\.md:10"])

    assert filtered["ok"] is False
    assert len(filtered["findings"]) == 1
    assert filtered["findings"][0]["file"] == "docs/b.md"


def test_classify_release_risk_levels():
    assert mission._classify_release_risk(100, 90, False, True, True, True) == "low"
    assert mission._classify_release_risk(100, 90, False, True, False, True) == "medium"
    assert mission._classify_release_risk(70, 90, False, False, True, True) == "high"
    assert mission._classify_release_risk(100, 90, True, True, True, True) == "critical"
