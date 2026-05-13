#!/usr/bin/env python3
"""CLI de auto-validação da ATENA.

Este módulo existe para o launcher ``./atena self-test`` e para o entry point
``atena-self-test``. Ele executa pytest em presets determinísticos e salva um
relatório JSON consumível por automações.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "atena_evolution" / "self_tests"

PRESETS: dict[str, list[str]] = {
    "quick": [
        "tests/unit/test_atena_launcher.py",
        "tests/unit/test_env_bootstrap.py",
        "tests/unit/test_rate_limiter.py",
        "tests/unit/test_atena_response_cache.py",
    ],
    "security": [
        "tests/unit/test_security_validator.py",
        "tests/unit/test_atena_secret_scan.py",
        "tests/unit/test_production_guardrails.py",
    ],
    "perf": [
        "tests/unit/test_atena_module_preloader.py",
        "tests/unit/test_event_bus.py",
        "tests/unit/test_memory_maintenance.py",
    ],
    "full": ["tests/unit"],
}


def _build_pytest_command(mode: str, extra_pytest_args: Sequence[str]) -> list[str]:
    targets = PRESETS.get(mode, PRESETS["full"])
    return [sys.executable, "-m", "pytest", *targets, *extra_pytest_args]


def run_self_test(mode: str, extra_pytest_args: Sequence[str] = ()) -> dict[str, object]:
    """Executa um preset de teste e retorna o payload do relatório."""
    started_at = datetime.now(timezone.utc)
    command = _build_pytest_command(mode, extra_pytest_args)
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    finished_at = datetime.now(timezone.utc)
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "mode": mode,
        "command": command,
        "returncode": proc.returncode,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "stdout_tail": (proc.stdout or "")[-12000:],
        "stderr_tail": (proc.stderr or "")[-6000:],
    }


def write_report(payload: dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    mode = str(payload.get("mode", "unknown"))
    path = REPORT_DIR / f"self_test_{mode}_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa auto-validações da ATENA")
    parser.add_argument(
        "mode",
        nargs="?",
        default="full",
        choices=sorted(PRESETS),
        help="Preset de validação a executar",
    )
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Argumentos extras para pytest")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório completo em JSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    extra = list(args.pytest_args)
    if extra and extra[0] == "--":
        extra = extra[1:]
    payload = run_self_test(args.mode, extra)
    report_path = write_report(payload)
    payload["report_path"] = str(report_path)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ATENA self-test mode={args.mode} status={payload['status']}")
        print(f"Report: {report_path}")
        print(str(payload.get("stdout_tail", ""))[-4000:])
        stderr_tail = str(payload.get("stderr_tail", ""))
        if stderr_tail.strip():
            print(stderr_tail[-2000:], file=sys.stderr)
    return int(payload["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
