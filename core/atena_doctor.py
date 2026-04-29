#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Doctor: healthcheck rápido do ambiente e comandos principais."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Check:
    name: str
    command: List[str]
    timeout: int = 20


BASE_CHECKS = [
    Check("Launcher help", ["./atena", "help"], timeout=15),
    Check("Compile core launcher", [sys.executable, "-m", "py_compile", "core/atena_launcher.py"], timeout=20),
    Check("Compile assistant", [sys.executable, "-m", "py_compile", "core/atena_terminal_assistant.py"], timeout=20),
    Check("Compile invoke", [sys.executable, "-m", "py_compile", "protocols/atena_invoke.py"], timeout=20),
    Check("Skill shell lint", ["bash", "-n", "skills/atena-orchestrator/scripts/run_atena.sh"], timeout=10),
    Check("Skill python lint", [sys.executable, "-m", "py_compile", "skills/neural-reality-sync/scripts/sync_engine.py"], timeout=10),
]

FULL_EXTRA_CHECKS = [
    Check("Core help", [sys.executable, "core/main.py", "--help"], timeout=25),
    Check("Invoke fallback smoke", ["./atena", "invoke"], timeout=35),
]


def run_check(check: Check) -> dict:
    try:
        proc = subprocess.run(
            check.command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=check.timeout,
            check=False,
        )
        return {
            "name": check.name,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[:300],
            "stderr": proc.stderr[:300],
            "command": " ".join(check.command),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": check.name,
            "ok": False,
            "returncode": "timeout",
            "stdout": (exc.stdout or "")[:300],
            "stderr": (exc.stderr or "")[:300],
            "command": " ".join(check.command),
        }


def print_report(results: list[dict]) -> None:
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    fail = total - ok
    print("🔎 ATENA Doctor Report")
    print(f"Host: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Checks: {ok}/{total} ok | {fail} falhas\n")
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        print(f"{icon} {r['name']} :: {r['command']}")
        if not r["ok"]:
            if r["stderr"]:
                print(f"   stderr: {r['stderr'].strip()}")
            elif r["stdout"]:
                print(f"   stdout: {r['stdout'].strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Doctor")
    parser.add_argument("--full", action="store_true", help="Inclui checks mais pesados de runtime")
    args = parser.parse_args()

    checks = list(BASE_CHECKS)
    if args.full:
        checks.extend(FULL_EXTRA_CHECKS)

    results = [run_check(c) for c in checks]
    print_report(results)
    out = ROOT / "atena_evolution" / "doctor_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
