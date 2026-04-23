#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Ω — Missão genial: síntese estratégica autônoma multiobjetivo."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
EVOLUTION_DIR = ROOT / "atena_evolution"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_codex import AtenaCodex


def _build_experiments(risk_score: float, confidence: float) -> list[dict]:
    """Gera um portfólio de experimentos com score multiobjetivo."""
    base = [
        {"id": "E1", "name": "Hardening de Browser Agent", "impact": 0.86, "cost": 0.32, "risk": 0.22},
        {"id": "E2", "name": "Auto-rollback para mutações", "impact": 0.91, "cost": 0.44, "risk": 0.18},
        {"id": "E3", "name": "Validador de alinhamento contínuo", "impact": 0.89, "cost": 0.41, "risk": 0.26},
        {"id": "E4", "name": "Planejador contrafactual por hipótese", "impact": 0.93, "cost": 0.51, "risk": 0.29},
        {"id": "E5", "name": "Benchmark automático de regressão", "impact": 0.84, "cost": 0.28, "risk": 0.15},
        {"id": "E6", "name": "Swarm de revisão de código", "impact": 0.9, "cost": 0.48, "risk": 0.31},
    ]

    stability_bonus = max(0.0, min(0.15, confidence * 0.15))
    risk_penalty = max(0.0, min(0.15, risk_score * 0.15))

    for exp in base:
        exp["priority_score"] = round((0.65 * exp["impact"] - 0.2 * exp["cost"] - 0.15 * exp["risk"]) + stability_bonus - risk_penalty, 4)

    return sorted(base, key=lambda x: x["priority_score"], reverse=True)


def main() -> int:
    codex = AtenaCodex(root_path=str(ROOT))
    autopilot = codex.run_advanced_autopilot(
        objective="Criar plano genial de evolução com segurança operacional",
        include_commands=False,
        timeout_seconds=60,
    )

    experiments = _build_experiments(
        risk_score=float(autopilot.get("risk_score", 0.0)),
        confidence=float(autopilot.get("confidence", 0.0)),
    )
    top3 = experiments[:3]

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)

    md_path = DOCS_DIR / f"MISSAO_GENIAL_ATENA_{stamp}.md"
    json_path = EVOLUTION_DIR / f"genius_mission_{now.strftime('%Y%m%d_%H%M%S')}.json"

    md_lines = [
        f"# Missão Genial da ATENA Ω ({stamp})",
        "",
        "## Objetivo",
        "Executar síntese estratégica autônoma multiobjetivo com base no diagnóstico atual da ATENA.",
        "",
        "## Estado atual",
        f"- Status do autopilot: **{autopilot.get('status')}**",
        f"- Risk score: **{autopilot.get('risk_score')}**",
        f"- Confidence: **{autopilot.get('confidence')}**",
        "",
        "## Top 3 experimentos prioritários",
    ]
    for item in top3:
        md_lines.append(
            f"- **{item['id']} — {item['name']}** | score={item['priority_score']} | impact={item['impact']} | cost={item['cost']} | risk={item['risk']}"
        )

    md_lines.extend([
        "",
        "## Execução recomendada (72h)",
        "1. Implantar E4 e E2 em branch protegido com gate de rollback.",
        "2. Rodar benchmark automático de regressão (E5) por 3 ciclos.",
        "3. Liberar para produção apenas se confiança >= 0.85 e risco <= 0.20.",
    ])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    payload = {
        "generated_at": now.isoformat(),
        "autopilot": {
            "status": autopilot.get("status"),
            "risk_score": autopilot.get("risk_score"),
            "confidence": autopilot.get("confidence"),
            "action_plan": autopilot.get("action_plan", []),
        },
        "experiments": experiments,
        "top3": top3,
        "markdown_report": str(md_path.relative_to(ROOT)),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🧠✨ Missão genial concluída.")
    print(f"Status autopilot: {autopilot.get('status')}")
    print(f"Top experimento: {top3[0]['id']} - {top3[0]['name']} (score={top3[0]['priority_score']})")
    print(f"Relatório estratégico: {md_path.relative_to(ROOT)}")
    print(f"Artefato técnico: {json_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
