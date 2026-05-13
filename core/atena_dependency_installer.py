#!/usr/bin/env python3
"""Instalador auditável de dependências da ATENA.

O launcher ``./atena install-deps`` chama este módulo. Por padrão ele apenas
planeja a instalação para evitar mudanças implícitas no ambiente; com
``--apply`` executa ``pip install`` nos grupos selecionados e salva um relatório
JSON em ``atena_evolution/dependency_installs``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SETUP_DIR = ROOT / "setup"
REPORT_DIR = ROOT / "atena_evolution" / "dependency_installs"

REQUIREMENT_GROUPS: dict[str, list[Path]] = {
    "core": [SETUP_DIR / "requirements-pinned.txt"],
    "dev": [SETUP_DIR / "requirements-dev.txt"],
    "ultimate": [SETUP_DIR / "requirements-ultimate.txt"],
}
DEFAULT_GROUPS = ("core", "dev")


def _existing_requirement_files(groups: Sequence[str]) -> list[Path]:
    """Retorna arquivos de requirements existentes para os grupos pedidos."""
    files: list[Path] = []
    for group in groups:
        for path in REQUIREMENT_GROUPS[group]:
            if path.exists():
                files.append(path)
    return files


def build_pip_command(
    groups: Sequence[str],
    *,
    python_executable: str = sys.executable,
    upgrade_pip: bool = False,
    extra_pip_args: Sequence[str] = (),
) -> list[list[str]]:
    """Monta comandos pip determinísticos para instalar grupos da ATENA."""
    commands: list[list[str]] = []
    if upgrade_pip:
        commands.append([python_executable, "-m", "pip", "install", "--upgrade", "pip"])

    requirement_files = _existing_requirement_files(groups)
    install_command = [python_executable, "-m", "pip", "install"]
    for requirement_file in requirement_files:
        install_command.extend(["-r", str(requirement_file)])
    install_command.extend(extra_pip_args)
    commands.append(install_command)
    return commands


def _tail_output(value: str | bytes | None, limit: int = 12000) -> str:
    """Normaliza trechos finais de stdout/stderr para relatórios JSON."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value[-limit:].decode("utf-8", errors="replace")
    return value[-limit:]


def _write_report(payload: dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"dependency_install_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_path = REPORT_DIR / "latest_dependency_install.json"
    latest_path.write_text(
        json.dumps(payload | {"report_path": str(path)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def run_dependency_install(
    groups: Sequence[str],
    *,
    apply: bool = False,
    upgrade_pip: bool = False,
    extra_pip_args: Sequence[str] = (),
    timeout: int | None = None,
) -> dict[str, object]:
    """Planeja ou executa instalação de dependências e devolve relatório."""
    normalized_groups = list(dict.fromkeys(groups))
    commands = build_pip_command(
        normalized_groups,
        upgrade_pip=upgrade_pip,
        extra_pip_args=extra_pip_args,
    )
    payload: dict[str, object] = {
        "status": "planned",
        "applied": apply,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "groups": normalized_groups,
        "requirement_files": [str(path) for path in _existing_requirement_files(normalized_groups)],
        "commands": commands,
        "results": [],
        "python": sys.executable,
        "cwd": str(ROOT),
    }

    if not apply:
        payload["note"] = "Dry-run: use --apply para instalar as dependências."
        report_path = _write_report(payload)
        payload["report_path"] = str(report_path)
        return payload

    env = os.environ.copy()
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    results: list[dict[str, object]] = []
    overall_returncode = 0
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            results.append({
                "command": command,
                "returncode": 124,
                "stdout_tail": _tail_output(exc.stdout),
                "stderr_tail": _tail_output(exc.stderr),
                "error": f"timeout after {exc.timeout} seconds",
            })
            overall_returncode = 124
            break
        results.append({
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-12000:],
            "stderr_tail": (completed.stderr or "")[-12000:],
        })
        if completed.returncode != 0:
            overall_returncode = completed.returncode
            break

    payload["results"] = results
    payload["returncode"] = overall_returncode
    payload["status"] = "ok" if overall_returncode == 0 else "failed"
    report_path = _write_report(payload)
    payload["report_path"] = str(report_path)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Planeja/instala dependências da ATENA")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Executa pip install; sem esta flag apenas planeja e grava relatório.",
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=sorted(REQUIREMENT_GROUPS),
        default=list(DEFAULT_GROUPS),
        help="Grupos a instalar. Padrão: core dev.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Instala core, dev e ultimate (ML/LLM pesado).",
    )
    parser.add_argument(
        "--upgrade-pip", action="store_true", help="Atualiza pip antes de instalar."
    )
    parser.add_argument(
        "--timeout", type=int, default=None, help="Timeout por comando pip, em segundos."
    )
    parser.add_argument("--json", action="store_true", help="Imprime o relatório completo em JSON.")
    parser.add_argument(
        "pip_args",
        nargs=argparse.REMAINDER,
        help="Argumentos extras para pip após --, por exemplo: -- --no-cache-dir",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    groups = sorted(REQUIREMENT_GROUPS) if args.all else args.groups
    extra_pip_args = list(args.pip_args)
    if extra_pip_args and extra_pip_args[0] == "--":
        extra_pip_args = extra_pip_args[1:]

    payload = run_dependency_install(
        groups,
        apply=args.apply,
        upgrade_pip=args.upgrade_pip,
        extra_pip_args=extra_pip_args,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ATENA dependency install status={payload['status']} applied={payload['applied']}")
        print(f"Groups: {', '.join(payload['groups'])}")
        print(f"Report: {payload['report_path']}")
        for command in payload["commands"]:
            print("$ " + " ".join(command))
        for result in payload.get("results", []):
            if isinstance(result, dict):
                print(
                    f"returncode={result.get('returncode')} command={' '.join(result.get('command', []))}"
                )
                stderr_tail = str(result.get("stderr_tail", "")).strip()
                if stderr_tail:
                    print(stderr_tail[-2000:], file=sys.stderr)
    return int(payload.get("returncode", 0))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
