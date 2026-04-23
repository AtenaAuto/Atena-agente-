#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace

from core.atena_agi_external_validation import run_external_validation, save_external_validation


def test_run_external_validation_scoring(monkeypatch, tmp_path: Path):
    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ANN001
        command = " ".join(cmd)
        if "go-no-go" in command:
            return SimpleNamespace(returncode=2, stdout="no-go", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("core.atena_agi_external_validation.subprocess.run", fake_run)
    payload = run_external_validation(tmp_path, timeout_seconds=2)
    assert payload["score_0_100"] < 100
    assert payload["score_1_10"] > 0
    assert len(payload["results"]) >= 5


def test_save_external_validation_writes_artifacts(tmp_path: Path):
    payload = {
        "score_0_100": 88.0,
        "score_1_10": 8.8,
        "maturity": "high",
        "results": [{"id": "x", "domain": "d", "weight": 1.0, "ok": True}],
    }
    js, md = save_external_validation(tmp_path, payload)
    assert js.exists()
    assert md.exists()
