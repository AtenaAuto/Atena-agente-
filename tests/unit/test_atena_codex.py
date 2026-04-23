from __future__ import annotations

from types import SimpleNamespace

from modules.atena_codex import AtenaCodex


def test_check_python_modules_exposes_advanced_group() -> None:
    codex = AtenaCodex()
    checks = codex.check_python_modules()

    assert "essential" in checks
    assert "advanced" in checks
    assert "optional" in checks


def test_run_full_diagnostic_treats_soft_fail_as_warning(monkeypatch) -> None:
    codex = AtenaCodex()

    monkeypatch.setattr(codex, "environment_snapshot", lambda: {"host": "test"})
    monkeypatch.setattr(
        codex,
        "check_python_modules",
        lambda: {
            "essential": [{"name": "requests", "ok": True, "details": "ok"}],
            "advanced": [],
            "optional": [],
        },
    )
    monkeypatch.setattr(
        codex,
        "run_local_commands",
        lambda timeout_seconds=120: [
            {
                "command": "python -c import atena_launcher",
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "soft_failed": False,
                "soft_reason": "",
            },
            {
                "command": "python -c import main",
                "returncode": 1,
                "stdout": "",
                "stderr": "No module named 'numpy'",
                "soft_failed": True,
                "soft_reason": "advanced missing",
            },
        ],
    )

    diagnostic = codex.run_full_diagnostic(include_commands=True)

    assert diagnostic["status"] == "ok"


def test_run_advanced_autopilot_reports_soft_warning_and_advanced_missing(monkeypatch, tmp_path) -> None:
    codex = AtenaCodex(root_path=str(tmp_path))

    monkeypatch.setattr(
        codex,
        "run_full_diagnostic",
        lambda include_commands=True, timeout_seconds=120: {
            "status": "ok",
            "modules": {
                "essential": [{"name": "requests", "ok": True, "details": "ok"}],
                "advanced": [{"name": "numpy", "ok": False, "details": "missing"}],
                "optional": [],
            },
            "commands": [
                {
                    "command": "python -c import main",
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "No module named 'numpy'",
                    "soft_failed": True,
                    "soft_reason": "advanced missing",
                }
            ],
        },
    )

    result = codex.run_advanced_autopilot(objective="test")

    assert result["status"] == "ok"
    assert result["missing_essential_modules"] == []
    assert result["missing_advanced_modules"] == ["numpy"]
    assert result["failing_commands_count"] == 0
    assert result["soft_warning_commands_count"] == 1
    assert any(item["title"] == "Eliminar soft-fails de import avançado" for item in result["action_plan"])


def test_extract_missing_import_from_stderr() -> None:
    stderr = "ModuleNotFoundError: No module named 'psutil'"
    assert AtenaCodex._extract_missing_import_from_stderr(stderr) == "psutil"
    assert AtenaCodex._extract_missing_import_from_stderr("random error") is None


def test_run_module_smoke_suite_retries_after_install(monkeypatch, tmp_path) -> None:
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    (modules_dir / "sample.py").write_text("x = 1\n", encoding="utf-8")

    codex = AtenaCodex(root_path=str(tmp_path))
    calls = {"run": 0}

    def fake_run(cmd, capture_output, text, timeout, check, cwd):  # noqa: ANN001
        calls["run"] += 1
        cmd_text = " ".join(cmd)
        if "pip install psutil" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if calls["run"] == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr="ModuleNotFoundError: No module named 'psutil'")
        return SimpleNamespace(returncode=0, stdout="OK:sample", stderr="")

    monkeypatch.setattr("modules.atena_codex.subprocess.run", fake_run)
    report = codex.run_module_smoke_suite(timeout_seconds=3)
    first_result = next(item for item in report["results"] if item["type"] == "module_import")
    assert first_result["ok"] is True
