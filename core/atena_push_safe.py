#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Push seguro da ATENA: só envia se `doctor --full` aprovar."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GENERATED_FILES = [
    ROOT / "atena_evolution" / "doctor_report.json",
    ROOT / "atena_evolution" / "atena_state.json",
    ROOT / "atena_evolution" / "mission_advanced_script_report.json",
    ROOT / "atena_evolution" / "portfolio_optimization_results.json",
    ROOT / "modules" / "atena_advanced_portfolio_optimizer.py",
]
GENERATED_DIRS = [
    ROOT / "core" / "__pycache__",
    ROOT / "skills" / "neural-reality-sync" / "scripts" / "__pycache__",
]
GENERATED_EXTRA_FILES = [
    ROOT / "protocols" / "__pycache__" / "atena_invoke.cpython-310.pyc",
]


def run(cmd: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, check=False)

def cleanup_generated_artifacts():
    # restaura arquivo tracked alterado pelo invoke
    run(["git", "checkout", "--", "modules/atena_advanced_portfolio_optimizer.py"])
    for path in GENERATED_FILES:
        if path.exists() and not path.name == "atena_advanced_portfolio_optimizer.py":
            try:
                path.unlink()
            except Exception:
                pass
    for directory in GENERATED_DIRS:
        if directory.exists():
            try:
                import shutil

                shutil.rmtree(directory)
            except Exception:
                pass
    for path in GENERATED_EXTRA_FILES:
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Push Safe")
    parser.add_argument("--branch", default="work", help="branch local para push")
    parser.add_argument("--remote", default="origin", help="remote git")
    parser.add_argument("--execute", action="store_true", help="executa push real (sem essa flag é dry-run)")
    args = parser.parse_args()

    print("🔒 Validando qualidade antes do push...")
    doctor = run(["./atena", "doctor", "--full"], timeout=600)
    print(doctor.stdout[:1200])
    if doctor.returncode != 0:
        print("❌ Doctor não aprovou. Push bloqueado.")
        return 1

    cleanup_generated_artifacts()

    status = run(["git", "status", "--porcelain"])
    dirty = bool(status.stdout.strip())
    if dirty:
        print("❌ Repositório com mudanças não commitadas. Push bloqueado.")
        return 1

    push_cmd = ["git", "push", args.remote, args.branch]
    push_main_cmd = ["git", "push", args.remote, f"{args.branch}:main"]
    print("✅ Aprovação concluída. Comandos prontos:")
    print("   " + " ".join(push_cmd))
    print("   " + " ".join(push_main_cmd))

    if not args.execute:
        print("ℹ️ Dry-run: use --execute para enviar de fato.")
        return 0

    r1 = run(push_cmd)
    print(r1.stdout[:500] + r1.stderr[:500])
    if r1.returncode != 0:
        return r1.returncode
    r2 = run(push_main_cmd)
    print(r2.stdout[:500] + r2.stderr[:500])
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
