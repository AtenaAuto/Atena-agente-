#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modo Kyros da ATENA: foco em prontidão operacional e execução guiada."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired as exc:
        return 124, f"Timeout ao executar comando: {' '.join(cmd)} | limite={timeout}s | detalhe={exc}"
    except FileNotFoundError as exc:
        return 127, f"Comando não encontrado: {' '.join(cmd)} | detalhe={exc}"


def render_status() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("⏱️  ATENA Kyros Mode")
    print(f"Timestamp (UTC): {ts}")
    print("Objetivo: operar com foco em tempo, estabilidade e decisão de execução.")
    print("Perfis ativos: health-check, smoke-check, gate recommendation")
    return 0


def run_smoke(timeout: int = 120) -> int:
    checks = [
        ("doctor", ["./atena", "doctor"]),
        ("modules-smoke", ["./atena", "modules-smoke"]),
    ]
    ok = 0
    print("⏱️  KYROS Smoke Run")
    for name, cmd in checks:
        rc, out = run_cmd(cmd, timeout=timeout)
        status = "OK" if rc == 0 else "FAIL"
        print(f"- {name}: {status}")
        if rc != 0:
            print(out[:500])
        else:
            ok += 1

    print(f"Resultado Kyros: {ok}/{len(checks)} checks OK")
    return 0 if ok == len(checks) else 2


def render_capabilities() -> int:
    capabilities = [
        "Status operacional em tempo real (timestamp UTC + perfil ativo)",
        "Execução de smoke de prontidão (doctor + modules-smoke)",
        "Controle de timeout por comando com parâmetro --timeout",
        "Tratamento de timeout sem crash (retorno 124)",
        "Tratamento de comando ausente sem crash (retorno 127)",
        "Execução combinada (--status --smoke) em uma chamada",
        "Saída orientada a operação (OK/FAIL por check)",
        "Retorno de código processável por automações (0/2/124/127)",
    ]
    print("⏱️  Kyros Capabilities")
    for i, cap in enumerate(capabilities, start=1):
        print(f"{i}. {cap}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="ATENA Kyros Mode")
    parser.add_argument("--status", action="store_true", help="Mostra status do modo Kyros")
    parser.add_argument("--smoke", action="store_true", help="Executa smoke rápido (doctor + modules-smoke)")
    parser.add_argument("--capabilities", action="store_true", help="Lista o que o modo Kyros é capaz de fazer")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout por comando no smoke (segundos)")
    args = parser.parse_args(argv)

    if not args.status and not args.smoke and not args.capabilities:
        return render_status()

    if args.status:
        render_status()

    if args.capabilities:
        render_capabilities()

    if args.smoke:
        return run_smoke(timeout=max(1, args.timeout))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
