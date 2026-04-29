#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autoanálise operacional para elevar ATENA continuamente."""

from __future__ import annotations

from pathlib import Path


CORE_FILES = [
    "core/atena_production_center.py",
    "core/atena_production_api.py",
    "core/production_observability.py",
    "core/production_guardrails.py",
    "core/production_gate.py",
    "core/production_readiness.py",
    "core/skill_marketplace.py",
    "render.yaml",
]


def run_self_audit(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    for rel in CORE_FILES:
        path = root / rel
        checks.append({"name": rel, "ok": path.exists(), "type": "required_file"})

    total = len(checks)
    passed = sum(1 for c in checks if c["ok"])
    score = round((passed / total) if total else 0.0, 4)

    recommendations: list[str] = []
    if score < 1.0:
        recommendations.append("Completar arquivos obrigatórios de produção ausentes.")
    recommendations.append("Rodar go-live-gate antes de cada deploy.")
    recommendations.append("Configurar webhook real no slo-alert para incidentes críticos.")
    recommendations.append("Agendar execução diária do self-audit no CI.")

    return {
        "status": "ok" if score >= 0.9 else "needs-work",
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "recommendations": recommendations,
    }
