from __future__ import annotations

import json

from core import atena_dependency_installer as installer


def test_build_pip_command_includes_selected_requirement_files():
    commands = installer.build_pip_command(["core", "dev"], python_executable="pythonX")

    assert commands == [[
        "pythonX",
        "-m",
        "pip",
        "install",
        "-r",
        str(installer.SETUP_DIR / "requirements-pinned.txt"),
        "-r",
        str(installer.SETUP_DIR / "requirements-dev.txt"),
    ]]


def test_run_dependency_install_dry_run_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "REPORT_DIR", tmp_path)

    payload = installer.run_dependency_install(["core"], apply=False)

    assert payload["status"] == "planned"
    assert payload["applied"] is False
    assert payload["groups"] == ["core"]
    assert payload["results"] == []
    report_path = tmp_path / "latest_dependency_install.json"
    assert report_path.exists()
    latest = json.loads(report_path.read_text(encoding="utf-8"))
    assert latest["status"] == "planned"


def test_run_dependency_install_apply_uses_subprocess(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "REPORT_DIR", tmp_path)
    calls = []

    class Completed:
        returncode = 0
        stdout = "installed"
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    payload = installer.run_dependency_install(["core"], apply=True, timeout=7)

    assert payload["status"] == "ok"
    assert payload["returncode"] == 0
    assert len(calls) == 1
    assert calls[0][0][:4] == [installer.sys.executable, "-m", "pip", "install"]
    assert calls[0][1]["timeout"] == 7
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs


def test_install_atena_dependencies_returns_terminal_compatible_result(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "REPORT_DIR", tmp_path)

    result = installer.install_atena_dependencies(
        dry_run=True,
        include_ultimate=True,
        include_system=True,
    )
    payload = result.to_dict()

    assert payload["status"] == "planned"
    assert payload["report_path"]
    assert payload["payload"]["groups"] == ["core", "dev", "ultimate"]
    assert payload["steps"][0]["name"] == "pip install"
    assert payload["steps"][0]["status"] == "planned"
    assert payload["steps"][-1]["name"] == "system dependencies"
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
