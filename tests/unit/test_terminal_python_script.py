import json
import subprocess
import sys
from pathlib import Path

from core.atena_terminal_python_script import create_and_run_terminal_python_script


def test_create_and_run_terminal_python_script(tmp_path: Path) -> None:
    result = create_and_run_terminal_python_script(
        "mostrar mensagem Python no terminal",
        output_dir=tmp_path,
    )

    assert result.status == "ok"
    assert result.returncode == 0
    assert Path(result.script_path).exists()
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["goal"] == "mostrar mensagem Python no terminal"
    assert "script Python" in payload["message"]


def test_python_script_cli_no_run_creates_file(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.python_script",
            "criar automação simples",
            "--output-dir",
            str(tmp_path),
            "--no-run",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "created"
    assert Path(payload["script_path"]).exists()
    assert payload["returncode"] == 0
