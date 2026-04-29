#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Fix: auto-correções básicas de ambiente/projeto."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class FixStep:
    name: str
    command: list[str] | None = None
    mkdir: Path | None = None
    chmod: Path | None = None


STEPS = [
    FixStep(name="Garantir pasta de estado", mkdir=ROOT / "atena_evolution" / "states"),
    FixStep(name="Garantir launcher executável", chmod=ROOT / "atena"),
    FixStep(
        name="Compilar módulos críticos",
        command=[sys.executable, "-m", "py_compile", "core/atena_launcher.py", "core/atena_terminal_assistant.py", "protocols/atena_invoke.py"],
    ),
    FixStep(
        name="Lint skill shell",
        command=["bash", "-n", "skills/atena-orchestrator/scripts/run_atena.sh"],
    ),
    FixStep(
        name="Lint skill python",
        command=[sys.executable, "-m", "py_compile", "skills/neural-reality-sync/scripts/sync_engine.py"],
    ),
]


def run_step(step: FixStep) -> bool:
    try:
        if step.mkdir is not None:
            step.mkdir.mkdir(parents=True, exist_ok=True)
            return True
        if step.chmod is not None:
            mode = step.chmod.stat().st_mode
            step.chmod.chmod(mode | 0o111)
            return True
        if step.command is not None:
            proc = subprocess.run(step.command, cwd=str(ROOT), capture_output=True, text=True, timeout=45)
            if proc.returncode != 0:
                print(f"   stderr: {proc.stderr[:300].strip()}")
            return proc.returncode == 0
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"   erro: {exc}")
        return False


def main() -> int:
    print("🛠️  ATENA Fix iniciando...")
    ok = 0
    for step in STEPS:
        result = run_step(step)
        print(f"{'✅' if result else '❌'} {step.name}")
        if result:
            ok += 1
    print(f"\nResultado: {ok}/{len(STEPS)} correções/checks concluídos.")
    return 0 if ok == len(STEPS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
