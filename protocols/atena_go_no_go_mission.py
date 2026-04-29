#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de validação Go/No-Go com 5 testes essenciais da ATENA."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EVOLUTION = ROOT / "atena_evolution"


@dataclass
class CheckResult:
    name: str
    command: str
    ok: bool
    details: str


def run_cmd(cmd: list[str], timeout: int = 120, extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return proc.returncode, out.strip()


def now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main() -> int:
    checks: list[CheckResult] = []

    # 1) Doctor
    rc, out = run_cmd(["./atena", "doctor"])
    checks.append(CheckResult("doctor", "./atena doctor", rc == 0, out))

    # 2) Module smoke
    rc, out = run_cmd(["./atena", "modules-smoke"])
    checks.append(CheckResult("modules-smoke", "./atena modules-smoke", rc == 0, out))

    # 3) Production gate
    rc, out = run_cmd(["./atena", "production-ready"], timeout=180)
    checks.append(CheckResult("production-ready", "./atena production-ready", rc == 0, out))

    # 4) Programação no assistant deve devolver código Python
    prompt = "/task Gere um script Python mínimo que imprima 'ok'\\n:q\\n"
    rc, out = run_cmd(
        ["bash", "-lc", f"printf \"{prompt}\" | ./atena assistant"],
        timeout=120,
        extra_env={
            "ATENA_AUTO_BOOTSTRAP": "0",
            "ATENA_AUTO_PREPARE_LOCAL_MODEL": "0",
        },
    )
    has_python_code = "```python" in out or "def main():" in out or "print(\"ok\")" in out
    checks.append(
        CheckResult(
            "assistant-programming",
            "printf '/task ...' | ./atena assistant",
            rc == 0 and has_python_code,
            out,
        )
    )

    # 5) Compile de demos/testes de topo
    rc, out = run_cmd(
        [
            sys.executable,
            "-m",
            "py_compile",
            "demo_orchestrator.py",
            "demo_price_extraction.py",
            "demo_web_extraction.py",
            "test_browser_integration.py",
            "test_control_system.py",
        ]
    )
    checks.append(
        CheckResult(
            "root-demos-pycompile",
            "python -m py_compile demo_*.py test_*.py",
            rc == 0,
            out or "ok",
        )
    )

    ok_count = sum(1 for c in checks if c.ok)
    status = "GO" if ok_count == len(checks) else "NO-GO"

    DOCS.mkdir(parents=True, exist_ok=True)
    EVOLUTION.mkdir(parents=True, exist_ok=True)
    d = now_date()
    ts = now_ts()
    md = DOCS / f"GO_NO_GO_REPORT_{d}.md"
    js = EVOLUTION / f"go_no_go_report_{ts}.json"

    lines = [f"# ATENA Go/No-Go Report ({d})", "", f"Status final: **{status}**", ""]
    for c in checks:
        icon = "✅" if c.ok else "❌"
        lines.append(f"## {icon} {c.name}")
        lines.append(f"- Comando: `{c.command}`")
        lines.append(f"- Resultado: {'OK' if c.ok else 'FALHA'}")
        lines.append("")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "status": status,
        "timestamp": ts,
        "ok_count": ok_count,
        "total": len(checks),
        "checks": [
            {
                "name": c.name,
                "command": c.command,
                "ok": c.ok,
            }
            for c in checks
        ],
        "report_md": str(md),
    }
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🧪 ATENA Go/No-Go Mission")
    print(f"Status: {status}")
    print(f"Checks: {ok_count}/{len(checks)}")
    print(f"Relatório: {md}")
    print(f"Artefato: {js}")
    return 0 if status == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
