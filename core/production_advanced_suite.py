#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capacidades avançadas (MVP) para evolução operacional da ATENA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.heavy_mode_selector import choose_mode
from core.production_guardrails import Action, PolicyEngine, Role
from core.production_observability import TelemetryStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_eval_suite(telemetry: TelemetryStore) -> dict[str, object]:
    summary = telemetry.summarize()
    checks = [
        {"name": "min_events", "ok": summary["total"] >= 1, "threshold": 1, "value": summary["total"]},
        {"name": "success_rate", "ok": summary["success_rate"] >= 0.8, "threshold": 0.8, "value": summary["success_rate"]},
        {"name": "avg_latency_ms", "ok": summary["avg_latency_ms"] <= 1200, "threshold": 1200, "value": summary["avg_latency_ms"]},
    ]
    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    status = "pass" if passed == total else "warn"
    return {
        "status": status,
        "passed": passed,
        "total": total,
        "checks": checks,
        "generated_at": _utc_now(),
        "summary": summary,
    }


def build_issue_to_pr_plan(issue: str, repository: str) -> dict[str, object]:
    steps = [
        "Analisar contexto da issue e critérios de aceite.",
        "Gerar plano técnico e arquitetura mínima.",
        "Implementar em branch dedicada com commits pequenos.",
        "Adicionar/ajustar testes automatizados.",
        "Executar checks de qualidade e segurança.",
        "Abrir PR com riscos, rollback e plano de validação.",
    ]
    return {
        "status": "ok",
        "issue": issue,
        "repository": repository,
        "steps": steps,
        "next_action": "Executar etapa 1 e criar branch feature/*",
    }


def run_rag_governance_check(role: str, data_classification: str, has_citations: bool) -> dict[str, object]:
    allowed_classifications = {
        "viewer": {"public"},
        "operator": {"public", "internal"},
        "admin": {"public", "internal", "confidential"},
    }
    role_key = role.lower()
    allowed = data_classification in allowed_classifications.get(role_key, set())
    checks = [
        {"name": "rbac_access", "ok": allowed},
        {"name": "citations_required", "ok": bool(has_citations)},
    ]
    passed = sum(1 for c in checks if c["ok"])
    status = "ok" if passed == len(checks) else "blocked"
    return {
        "status": status,
        "role": role_key,
        "data_classification": data_classification,
        "checks": checks,
        "recommendation": "Liberar consulta RAG." if status == "ok" else "Bloquear e solicitar role/citações válidas.",
    }


@dataclass
class SecurityCheckResult:
    status: str
    risk_score: int
    blocked: bool
    reasons: list[str]
    recommended_action: str


def run_security_check(prompt: str, action: str) -> dict[str, object]:
    lowered = prompt.lower()
    reasons: list[str] = []
    risk = 0

    if any(token in lowered for token in ("ignore previous", "system prompt", "jailbreak")):
        reasons.append("possible_prompt_injection")
        risk += 45
    if any(token in lowered for token in ("api_key", "secret", "token", "password")):
        reasons.append("possible_secret_exfiltration")
        risk += 40
    if action in {"execute_shell", "delete_data", "deploy_prod"}:
        reasons.append("high_impact_action")
        risk += 25

    blocked = risk >= 60
    result = SecurityCheckResult(
        status="blocked" if blocked else "ok",
        risk_score=min(risk, 100),
        blocked=blocked,
        reasons=reasons or ["no_high_risk_signal"],
        recommended_action="Exigir aprovação humana + sandbox restrito." if blocked else "Executar com auditoria.",
    )
    return asdict(result)


def run_finops_route(complexity: int, budget: float, latency_sensitive: bool) -> dict[str, object]:
    decision = choose_mode(task_complexity=complexity, budget_units=budget, latency_sensitive=latency_sensitive)
    estimated_cost = float(decision.estimated_cost)
    return {
        "status": "ok",
        "mode": decision.mode,
        "reason": decision.reason,
        "estimated_cost_units": estimated_cost,
        "budget_ok": estimated_cost <= budget if budget > 0 else False,
    }


def run_incident_commander(scenario: str, telemetry_path: Path) -> dict[str, object]:
    telemetry = TelemetryStore(telemetry_path)
    summary = telemetry.summarize()
    severity = "high" if summary["success_rate"] < 0.8 else "medium"
    actions = [
        "Declarar incidente e abrir canal de comunicação.",
        "Aplicar mitigação inicial (fallback/rate limit).",
        "Executar validação de saúde pós-mitigação.",
        "Publicar postmortem preliminar em até 30 minutos.",
    ]
    return {
        "status": "ok",
        "scenario": scenario,
        "severity": severity,
        "actions": actions,
        "summary": summary,
    }
