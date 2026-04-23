from __future__ import annotations

from pathlib import Path

from core import atena_launcher


class _DummyCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_with_auto_dep_repair_interactive_disables_capture(monkeypatch):
    calls: list[dict] = []

    def _fake_run(*args, **kwargs):
        calls.append(kwargs)
        return _DummyCompleted(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)

    code = atena_launcher._run_with_auto_dep_repair(
        script=Path("dummy.py"),
        script_args=[],
        env={},
        interactive=True,
    )

    assert code == 0
    assert len(calls) == 1
    assert "capture_output" not in calls[0]
    assert "text" not in calls[0]


def test_run_with_auto_dep_repair_non_interactive_uses_capture(monkeypatch):
    calls: list[dict] = []

    def _fake_run(*args, **kwargs):
        calls.append(kwargs)
        return _DummyCompleted(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)

    code = atena_launcher._run_with_auto_dep_repair(
        script=Path("dummy.py"),
        script_args=[],
        env={},
        interactive=False,
    )

    assert code == 0
    assert len(calls) == 1
    assert calls[0]["capture_output"] is True
    assert calls[0]["text"] is True
