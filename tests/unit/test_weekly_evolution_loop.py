from __future__ import annotations

from types import SimpleNamespace

import core.atena_weekly_evolution_loop as loop


def test_run_loop_collects_step_results(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, capture_output=False, text=False):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(loop.subprocess, "run", _fake_run)

    payload = loop.run_loop(tmp_path)

    assert payload["status"] == "ok"
    assert payload["steps_ok"] == payload["steps_total"]
    assert len(calls) == payload["steps_total"]
