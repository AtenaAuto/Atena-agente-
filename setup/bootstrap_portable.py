#!/usr/bin/env python3
"""Bootstrap portátil da ATENA para Linux/macOS/Windows/Colab."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], dry_run: bool = False) -> None:
    print("$", " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def ensure_launcher_permissions(dry_run: bool) -> None:
    launcher = ROOT / "atena"
    if launcher.exists():
        run(["chmod", "+x", str(launcher)], dry_run)


def install_python_deps(with_dev: bool, dry_run: bool) -> None:
    py = sys.executable
    run([py, "-m", "pip", "install", "--upgrade", "pip"], dry_run)
    run([py, "-m", "pip", "install", "-r", str(ROOT / "setup/requirements-pinned.txt")], dry_run)
    if with_dev:
        run([py, "-m", "pip", "install", "-r", str(ROOT / "setup/requirements-dev.txt")], dry_run)


def install_system_deps(dry_run: bool) -> None:
    system = platform.system().lower()
    if "linux" in system and shutil.which("apt-get"):
        run(["apt-get", "update", "-y"], dry_run)
        run(["apt-get", "install", "-y", "tesseract-ocr"], dry_run)
    elif "darwin" in system:
        print("[INFO] macOS detectado. Instale tesseract via: brew install tesseract")
    elif "windows" in system:
        print("[INFO] Windows detectado. Instale Tesseract manualmente se OCR for necessário.")
    else:
        print("[INFO] Gerenciador de pacotes não suportado automaticamente.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap portátil da ATENA")
    parser.add_argument("--with-dev", action="store_true", help="Instala requirements-dev também")
    parser.add_argument("--with-playwright", action="store_true", help="Instala Chromium do Playwright")
    parser.add_argument("--doctor", action="store_true", help="Executa diagnóstico final")
    parser.add_argument("--skip-system", action="store_true", help="Não instala dependências do sistema")
    parser.add_argument("--full-auto", action="store_true", help="Ativa with-dev, with-playwright e doctor")
    parser.add_argument("--dry-run", action="store_true", help="Somente imprime comandos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.full_auto:
        args.with_dev = True
        args.with_playwright = True
        args.doctor = True

    ensure_launcher_permissions(args.dry_run)
    install_python_deps(with_dev=args.with_dev, dry_run=args.dry_run)

    if not args.skip_system:
        install_system_deps(dry_run=args.dry_run)

    if args.with_playwright:
        run([sys.executable, "-m", "playwright", "install", "chromium"], args.dry_run)

    if args.doctor:
        run(["bash", str(ROOT / "atena"), "doctor"], args.dry_run)

    print("✅ Bootstrap portátil concluído")


if __name__ == "__main__":
    main()
