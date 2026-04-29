#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrap de dependências mínimas para execução da ATENA em modo guardian/production."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REQUIRED = [
    "requests",
    "astor",
    "numpy",
    "aiosqlite",
    "rich",
    "psutil",
    "transformers",
]


def is_installed(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is not None


def main() -> int:
    missing = [pkg for pkg in REQUIRED if not is_installed(pkg)]
    if not missing:
        print("✅ Bootstrap: todas as dependências mínimas já estão instaladas.")
        return 0

    print(f"🔧 Bootstrap: instalando dependências ausentes: {', '.join(missing)}")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        print("❌ Bootstrap: falha na instalação de dependências.")
        return proc.returncode

    remaining = [pkg for pkg in REQUIRED if not is_installed(pkg)]
    if remaining:
        print(f"❌ Bootstrap: dependências ainda ausentes: {', '.join(remaining)}")
        return 2

    print("✅ Bootstrap: ambiente mínimo ATENA pronto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
