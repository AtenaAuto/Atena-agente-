#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plano objetivo para elevar ATENA ao nível enterprise."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.production_gate import evaluate_go_live
from core.production_observability import TelemetryStore
from core.production_readiness import build_remediation_plan, run_readiness
from core.skill_marketplace import SkillMarketplace


def build_perfection_plan(evolution_dir: Path | None = None) -> dict[str, object]:
    root = Path(__file__).resolve().parent.parent
    evo = evolution_dir or (root / "atena_evolution" / "production_center")
    evo.mkdir(parents=True, exist_ok=True)

    telemetry = TelemetryStore(evo / "telemetry.jsonl")
    market = SkillMarketplace(evo / "skills_catalog.json")
    readiness = run_readiness(telemetry=telemetry, market=market, evolution_dir=evo)
    remediation = build_remediation_plan(readiness)
    slo = telemetry.slo_check(
        min_success_rate=0.95,
        max_avg_latency_ms=1200,
        max_cost_units=500.0,
        window_days=30,
    )
    gate = evaluate_go_live(readiness=readiness, remediation=remediation, slo_alert=slo)

    telemetry_summary = telemetry.summarize()
    has_policy_audit = (evo / "policy_audit.jsonl").exists()
    has_active_approved = any(r.get("active") and r.get("approved") for r in market.list_records())

    tracks = [
        {
            "name": "observability-alerting",
            "priority": "p0",
            "completed": telemetry_summary["total"] > 0 and slo["status"] == "ok",
            "items": [
                "Integrar alertas ativos (webhook/pager) para violações de SLO.",
                "Criar dashboard com p95/p99, erro e custo por tenant.",
            ],
        },
        {
            "name": "security-governance",
            "priority": "p0",
            "completed": has_policy_audit and has_active_approved,
            "items": [
                "Adicionar ABAC por tenant/ambiente/risco.",
                "Habilitar assinatura e validação de integridade de skills.",
            ],
        },
        {
            "name": "release-excellence",
            "priority": "p1",
            "completed": readiness["status"] == "pass" and gate["decision"] == "GO",
            "items": [
                "Adicionar gate obrigatório production-ready + remediation-plan no CI.",
                "Criar rotina de drill mensal (incident-drill + runbook).",
            ],
        },
    ]

    completed = sum(1 for track in tracks if track["completed"])
    progress_pct = round((completed / max(1, len(tracks))) * 100, 1)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if completed == len(tracks) else "in-progress",
        "tracks": tracks,
        "progress_pct": progress_pct,
        "evidence": {
            "telemetry_total": telemetry_summary["total"],
            "slo_status": slo["status"],
            "readiness_status": readiness["status"],
            "go_live_decision": gate["decision"],
            "pending_actions": remediation["total_actions"],
            "policy_audit_present": has_policy_audit,
            "active_approved_skill": has_active_approved,
        },
        "success_criteria": {
            "slo_compliance": ">= 99%",
            "critical_incidents_month": 0,
            "go_live_gate": "all green",
        },
    }
