#!/usr/bin/env python3
"""Gera e executa um script Python simples no terminal da ATENA.

Este módulo existe para o operador poder pedir explicitamente:
"ATENA, faça um script Python no terminal" sem depender de LLM ou de
execução arbitrária de código recebido do usuário.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "atena_evolution" / "terminal_scripts"


@dataclass(frozen=True)
class TerminalPythonScriptResult:
    """Resultado da criação e execução de um script Python local."""

    status: str
    script_path: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "script_path": self.script_path,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _slugify(text: str, fallback: str = "atena_terminal_script") -> str:
    """Cria um nome de arquivo portátil e previsível para o objetivo."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip().lower()).strip("_")
    return (slug or fallback)[:60]


def build_python_script_source(goal: str) -> str:
    """Retorna código Python seguro e determinístico para o script solicitado."""
    clean_goal = (goal or "criar script Python no terminal").strip()
    generated_at = datetime.now(timezone.utc).isoformat()
    return f'''#!/usr/bin/env python3
"""Script Python gerado pela ATENA para execução no terminal."""

from __future__ import annotations

import json
from datetime import datetime, timezone


GOAL = {clean_goal!r}
GENERATED_AT_UTC = {generated_at!r}


def main() -> int:
    payload = {{
        "status": "ok",
        "message": "ATENA executou um script Python no terminal com sucesso.",
        "goal": GOAL,
        "generated_at_utc": GENERATED_AT_UTC,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "next_step": "Edite este arquivo para transformar o exemplo em automação real.",
    }}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def create_and_run_terminal_python_script(
    goal: str = "criar script Python no terminal",
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    run: bool = True,
) -> TerminalPythonScriptResult:
    """Cria um script Python em disco e, por padrão, executa no terminal."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / f"{_slugify(goal)}.py"
    script_path.write_text(build_python_script_source(goal), encoding="utf-8")
    script_path.chmod(0o755)

    command = [sys.executable, str(script_path)]
    if not run:
        return TerminalPythonScriptResult(
            status="created",
            script_path=str(script_path),
            command=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return TerminalPythonScriptResult(
        status="ok" if completed.returncode == 0 else "error",
        script_path=str(script_path),
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria e executa um script Python simples da ATENA")
    parser.add_argument("goal", nargs="*", help="Objetivo do script Python a ser criado")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretório onde o script será salvo")
    parser.add_argument("--no-run", action="store_true", help="Apenas cria o arquivo, sem executar")
    args = parser.parse_args(argv)

    goal = " ".join(args.goal).strip() or "criar script Python no terminal"
    result = create_and_run_terminal_python_script(goal, args.output_dir, run=not args.no_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.returncode == 0 else result.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
