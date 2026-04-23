#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão avançada com AtenaCodex: autopilot de confiabilidade e plano de ação."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_codex import AtenaCodex


def main() -> int:
    codex = AtenaCodex(root_path=str(ROOT))
    result = codex.run_advanced_autopilot(
        objective="Executar diagnóstico estratégico e gerar plano avançado de estabilização",
        include_commands=True,
        timeout_seconds=120,
    )

    print("🧠 ATENA CODEX — Missão avançada concluída")
    print(f"Status: {result['status']}")
    print(f"Risk score: {result['risk_score']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Módulos essenciais faltantes: {len(result['missing_essential_modules'])}")
    print(f"Comandos com falha: {result['failing_commands_count']}")
    print("\nPlano de ação:")
    for step in result["action_plan"]:
        print(f"- [{step['priority']}] {step['title']}: {step['details']}")
    print(f"\nRelatório salvo em: {result['report_path']}")

    print("\nResumo JSON:")
    print(json.dumps({
        "status": result["status"],
        "risk_score": result["risk_score"],
        "confidence": result["confidence"],
        "report_path": result["report_path"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
