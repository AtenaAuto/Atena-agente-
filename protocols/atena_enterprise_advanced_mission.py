#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão avançada enterprise: memória RAG, planner loop, SRE hardening e skill validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.enterprise_memory_rag import TenantMemoryRAG, build_reasoning_trace, redact_secrets
from core.internet_challenge import run_internet_challenge
from core.planner_executor_critic import run_planner_loop
from core.sre_auto_hardening import evaluate_regression, generate_postmortem
from core.skill_marketplace import SkillMarketplace, SkillRecord

EVOLUTION = ROOT / "atena_evolution" / "enterprise_advanced"
EVOLUTION.mkdir(parents=True, exist_ok=True)


def _memory_demo(tenant: str) -> dict[str, object]:
    store = TenantMemoryRAG(EVOLUTION / "memory.db")
    store.upsert(
        tenant_id=tenant,
        content="Implementar cache distribuído com invalidação por evento e monitorar p95 de latência.",
        citation="runbook://cache-strategy-v2",
        classification="internal",
        tags=["cache", "sre", "latency"],
    )
    result = store.query(tenant_id=tenant, question="Como reduzir p95 de latência no cache?", top_k=3)
    trace = build_reasoning_trace(
        steps=[
            "Consultar runbook interno",
            "Aplicar política de invalidação",
            "Registrar token ghp_ABCDEF1234567890XYZ para auditoria",  # será redacted
        ],
        citations=["runbook://cache-strategy-v2", "design://event-invalidation", "audit://security-guideline"],
    )
    retention = store.purge_expired({"public": 30, "internal": 90, "confidential": 365, "default": 90})
    return {"query": result, "trace": trace, "retention": retention}


def _planner_demo(goal: str) -> dict[str, object]:
    return run_planner_loop(goal, risk_threshold=0.75)


def _sre_demo() -> dict[str, object]:
    regression = evaluate_regression(
        success_rate=0.89,
        latency_ms=820.0,
        cost_units=170.0,
        baseline_success=0.95,
        baseline_latency_ms=500.0,
        baseline_cost_units=100.0,
    )
    postmortem = generate_postmortem(
        "latency-and-cost-regression",
        regression.get("regressions", []),
        bool(regression.get("rollback_suggested")),
    )
    return {"regression": regression, "postmortem": postmortem}


def _research_demo(topic: str) -> dict[str, object]:
    return run_internet_challenge(topic)


def _skill_demo() -> dict[str, object]:
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    record = SkillRecord(
        skill_id="enterprise-optimizer",
        version="1.0.0",
        risk_level="medium",
        cost_class="standard",
        compatible_with=">=3.2.0",
    )
    market.register(record)
    market.approve("enterprise-optimizer", version="1.0.0")
    market.validate("enterprise-optimizer", "1.0.0", sandbox_passed=True, contract_passed=True, security_passed=True)
    promoted = market.promote("enterprise-optimizer", "1.0.0")
    return {
        "promoted": promoted,
        "active_version": market.active_version("enterprise-optimizer"),
        "records": market.list_records(),
    }


def _sanitize_payload_for_persistence(payload: dict[str, object]) -> dict[str, object]:
    raw = json.dumps(payload, ensure_ascii=False)
    redacted = redact_secrets(raw)
    changed = raw != redacted
    safe_payload = json.loads(redacted)
    safe_payload["security_redaction"] = {
        "status": "warn" if changed else "ok",
        "redacted": changed,
    }
    return safe_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Enterprise Advanced Mission")
    parser.add_argument("--tenant", default="enterprise-default")
    parser.add_argument("--goal", default="Quebrar projeto grande em etapas; validar risco; executar com checkpoints")
    parser.add_argument("--topic", default="multi-agent ai governance conflict synthesis 2026")
    args = parser.parse_args()

    payload = {
        "status": "ok",
        "tenant": args.tenant,
        "memory_rag": _memory_demo(args.tenant),
        "planner_executor_critic": _planner_demo(args.goal),
        "sre_auto_hardening": _sre_demo(),
        "internet_research_engine": _research_demo(args.topic),
        "skill_marketplace": _skill_demo(),
    }

    safe_payload = _sanitize_payload_for_persistence(payload)
    out = EVOLUTION / "enterprise_advanced_report.json"
    out.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🏢⚙️ ATENA Enterprise Advanced Mission")
    print("Status: ok")
    print(f"Report: {out}")
    print(f"Tenant: {args.tenant}")
    print(f"Planner status: {payload['planner_executor_critic']['status']}")
    print(f"SRE risk: {payload['sre_auto_hardening']['regression']['risk']}")
    print(f"Research weighted_confidence: {payload['internet_research_engine'].get('weighted_confidence')}")
    print(f"Skill promoted: {payload['skill_marketplace']['promoted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
