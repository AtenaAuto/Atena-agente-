#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from types import SimpleNamespace

from core import atena_hacker_recon


def test_hacker_recon_builds_main_command_and_json(monkeypatch, capsys, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "text": text, "capture_output": capture_output})
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(
        [
            "--topic",
            "agentes ai",
            "--auto",
            "--cycles",
            "2",
            "--json",
            "--output-json",
            "analysis_reports/recon.json",
            "--history-json",
            "history.json",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][2:] == ["--recon", "agentes ai", "--auto", "--cycles", "2"]
    assert '"ok": true' in captured.out
    assert '"recon_score":' in captured.out
    assert "Relatório salvo em:" in captured.out
    assert (tmp_path / "analysis_reports" / "recon.json").exists()


def test_hacker_recon_no_report(monkeypatch, tmp_path):
    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(["--topic", "x", "--no-report", "--history-json", "history.json"])

    assert rc == 0
    assert not (tmp_path / "analysis_reports").exists()
    assert (tmp_path / "history.json").exists()


def test_hacker_recon_timeout_returns_124(monkeypatch, tmp_path):
    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        raise atena_hacker_recon.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output="partial", stderr="slow")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(["--topic", "x", "--timeout", "1", "--no-report", "--history-json", "history.json"])

    assert rc == 1


def test_hacker_recon_requires_topic_or_batch(monkeypatch):
    rc = atena_hacker_recon.run([])
    assert rc == 2


def test_hacker_recon_batch_mode_aggregates(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=f"Recon: {cmd[-1]}\n", stderr="")

    batch_file = tmp_path / "topics.txt"
    batch_file.write_text("topic A\ntopic B\n", encoding="utf-8")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(["--batch-file", str(batch_file), "--json", "--no-report", "--history-json", "history.json"])

    assert rc == 0
    assert len(calls) == 2


def test_hacker_recon_prioritize_history_reorders_topics(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    batch_file = tmp_path / "topics.txt"
    batch_file.write_text("topic low\ntopic high\n", encoding="utf-8")
    history_file = tmp_path / "history.json"
    history_file.write_text(
        '{"entries":[{"topic":"topic high","recon_score":95},{"topic":"topic low","recon_score":10}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(
        [
            "--batch-file",
            str(batch_file),
            "--no-report",
            "--prioritize-history",
            "--history-json",
            str(history_file),
        ]
    )

    assert rc == 0
    assert calls[0][-1] == "topic high"


def test_hacker_recon_retries_failed_topic(monkeypatch, tmp_path):
    calls = {"n": 0}

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr="fail")
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    out_json = tmp_path / "summary.json"
    rc = atena_hacker_recon.run(
        ["--topic", "retry topic", "--retries", "1", "--no-report", "--history-json", "history.json", "--output-json", str(out_json)]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert rc == 0
    assert calls["n"] == 2
    assert payload["results"][0]["attempts"] == 2


def test_hacker_recon_parallel_batch(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls.append(cmd[-1])
        time.sleep(0.01)
        return SimpleNamespace(returncode=0, stdout=f"Recon: {cmd[-1]}\n", stderr="")

    batch_file = tmp_path / "topics_parallel.txt"
    batch_file.write_text("topic 1\ntopic 2\ntopic 3\n", encoding="utf-8")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(
        ["--batch-file", str(batch_file), "--parallel", "3", "--no-report", "--history-json", "history.json"]
    )

    assert rc == 0
    assert sorted(calls) == ["topic 1", "topic 2", "topic 3"]
