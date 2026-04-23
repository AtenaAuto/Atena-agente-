#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-hardening SRE mode para ATENA (detecção de regressão + rollback + post-mortem)."""

from __future__ import annotations


def evaluate_regression(
    success_rate: float,
    latency_ms: float,
    cost_units: float,
    baseline_success: float,
    baseline_latency_ms: float,
    baseline_cost_units: float,
) -> dict[str, object]:
    regressions = []
    if success_rate < baseline_success:
        regressions.append("success_rate_drop")
    if latency_ms > baseline_latency_ms * 1.2:
        regressions.append("latency_spike")
    if cost_units > baseline_cost_units * 1.3:
        regressions.append("cost_spike")

    risk = "low"
    if len(regressions) >= 2:
        risk = "high"
    elif len(regressions) == 1:
        risk = "medium"

    rollback = risk == "high"
    return {
        "status": "ok" if not regressions else "warn",
        "regressions": regressions,
        "risk": risk,
        "rollback_suggested": rollback,
        "actions": [
            "Abrir incidente automaticamente",
            "Congelar deploys",
            "Executar rollback" if rollback else "Aumentar observabilidade e validar hipótese",
        ],
    }


def generate_postmortem(incident_title: str, regressions: list[str], rollback_executed: bool) -> dict[str, object]:
    return {
        "incident": incident_title,
        "impact_summary": f"Regressões detectadas: {', '.join(regressions) if regressions else 'nenhuma'}",
        "root_cause_hypothesis": "Mudança recente aumentou risco operacional além do baseline.",
        "rollback_executed": rollback_executed,
        "next_steps": [
            "Adicionar teste de regressão para o cenário",
            "Ajustar SLO/SLA thresholds",
            "Publicar lições aprendidas no runbook",
        ],
    }
