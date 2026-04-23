#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI de integração dos módulos de produção da ATENA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.heavy_mode_selector import choose_mode
from core.internet_challenge import run_internet_challenge
from core.production_access import QuotaManager, TenantQuota
from core.production_advanced_suite import (
    build_issue_to_pr_plan,
    run_eval_suite,
    run_finops_route,
    run_incident_commander,
    run_rag_governance_check,
    run_security_check,
)
from core.atena_subagent_solver import solve_with_subagent
from core.production_gate import evaluate_go_live
from core.production_contracts import validate_contract
from core.production_guardrails import Action, AuditLogger, PolicyEngine, Role
from core.production_observability import TelemetryStore, dispatch_alert
from core.production_onboarding import run_onboarding
from core.production_quality_harness import score_profiles_with_baseline
from core.production_perfection import build_perfection_plan
from core.production_programming_probe import run_programming_probe
from core.production_readiness import build_remediation_plan, run_readiness
from core.production_resilience import run_incident_drill
from core.production_self_audit import run_self_audit
from core.skill_marketplace import SkillMarketplace, SkillRecord

EVOLUTION = ROOT / "atena_evolution" / "production_center"
EVOLUTION.mkdir(parents=True, exist_ok=True)


def _emit(command: str, payload: dict | list) -> None:
    errors = validate_contract(command, payload)
    if isinstance(payload, dict):
        payload["contract_valid"] = len(errors) == 0
        if errors:
            payload["contract_errors"] = errors
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATENA Production Center")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_policy = sub.add_parser("policy-check", help="Valida role/action")
    p_policy.add_argument("--role", required=True, choices=[r.value for r in Role])
    p_policy.add_argument("--action", required=True, choices=[a.value for a in Action])
    p_policy.add_argument("--risk", default="medium")
    p_policy.add_argument("--hour-utc", type=int, default=12)
    p_policy.add_argument("--actor", default="cli-user")

    p_tlog = sub.add_parser("telemetry-log", help="Registra evento de telemetria")
    p_tlog.add_argument("--mission", required=True)
    p_tlog.add_argument("--status", required=True)
    p_tlog.add_argument("--latency-ms", required=True, type=int)
    p_tlog.add_argument("--cost", required=True, type=float)
    p_tlog.add_argument("--tenant", default="default")

    sub.add_parser("telemetry-summary", help="Resumo de telemetria")

    p_tenant = sub.add_parser("tenant-report", help="Resumo de telemetria por tenant")
    p_tenant.add_argument("--tenant", required=True)
    p_tenant.add_argument("--month", required=True, help="Formato YYYY-MM (informativo)")

    p_slo = sub.add_parser("slo-check", help="Validação de SLO no período")
    p_slo.add_argument("--window-days", type=int, default=7)
    p_slo.add_argument("--min-success-rate", type=float, default=0.95)
    p_slo.add_argument("--max-avg-latency-ms", type=int, default=500)
    p_slo.add_argument("--max-cost-units", type=float, default=100.0)

    p_alert = sub.add_parser("slo-alert", help="Valida SLO e opcionalmente dispara webhook")
    p_alert.add_argument("--window-days", type=int, default=7)
    p_alert.add_argument("--min-success-rate", type=float, default=0.95)
    p_alert.add_argument("--max-avg-latency-ms", type=int, default=500)
    p_alert.add_argument("--max-cost-units", type=float, default=100.0)
    p_alert.add_argument("--webhook-url")
    p_alert.add_argument("--retries", type=int, default=2)
    p_alert.add_argument("--backoff-sec", type=float, default=1.0)
    p_alert.add_argument("--dedupe-window-sec", type=int, default=300)

    p_quality = sub.add_parser("quality-score", help="Scoring por perfis")
    p_quality.add_argument("--profiles", default="support,dev,ops,security")

    sub.add_parser("onboarding-run", help="Executa onboarding profissional")

    p_sreg = sub.add_parser("skill-register", help="Registra skill")
    p_sreg.add_argument("--id", required=True)
    p_sreg.add_argument("--version", default="1.0.0")
    p_sreg.add_argument("--risk", default="medium")
    p_sreg.add_argument("--cost-class", default="standard")
    p_sreg.add_argument("--compat", default=">=3.2.0")

    p_sap = sub.add_parser("skill-approve", help="Aprova skill")
    p_sap.add_argument("--id", required=True)
    p_sap.add_argument("--version")

    p_prom = sub.add_parser("skill-promote", help="Promove versão aprovada para ativa")
    p_prom.add_argument("--id", required=True)
    p_prom.add_argument("--version", required=True)

    p_roll = sub.add_parser("skill-rollback", help="Rollback para versão anterior")
    p_roll.add_argument("--id", required=True)
    p_roll.add_argument("--to-version", required=True)

    sub.add_parser("skill-list", help="Lista skills")
    p_sval = sub.add_parser("skill-validate", help="Validação formal para ativação de skill")
    p_sval.add_argument("--id", required=True)
    p_sval.add_argument("--version", required=True)
    p_sval.add_argument("--sandbox-pass", action="store_true")
    p_sval.add_argument("--contract-pass", action="store_true")
    p_sval.add_argument("--security-pass", action="store_true")

    p_mode = sub.add_parser("mode-select", help="Seleciona modo leve/pesado")
    p_mode.add_argument("--complexity", type=int, required=True)
    p_mode.add_argument("--budget", type=float, required=True)
    p_mode.add_argument("--latency-sensitive", action="store_true")

    p_drill = sub.add_parser("incident-drill", help="Executa simulação de incidente")
    p_drill.add_argument("--scenario", default="provider-outage")
    p_drill.add_argument("--primary", default="provider-a")
    p_drill.add_argument("--fallback", default="provider-b")

    p_net = sub.add_parser("internet-challenge", help="Executa desafio de pesquisa complexa multi-fonte")
    p_net.add_argument("--topic", required=True)

    sub.add_parser("production-ready", help="Executa checklist de prontidão para produção")
    sub.add_parser("remediation-plan", help="Gera plano de ação a partir da prontidão")
    sub.add_parser("perfection-plan", help="Mostra trilha para nível enterprise")
    p_gate = sub.add_parser("go-live-gate", help="Decisão formal GO/NO_GO para produção")
    p_gate.add_argument("--window-days", type=int, default=30)
    p_gate.add_argument("--min-success-rate", type=float, default=0.95)
    p_gate.add_argument("--max-avg-latency-ms", type=int, default=500)
    p_gate.add_argument("--max-cost-units", type=float, default=100.0)

    sub.add_parser("self-audit", help="Autoanálise completa de prontidão da ATENA")
    p_prog = sub.add_parser("programming-probe", help="Testa se a ATENA consegue programar (site/api/cli)")
    p_prog.add_argument("--prefix", default="probe")
    p_prog.add_argument(
        "--site-template",
        choices=["basic", "landing-page", "portfolio", "dashboard", "blog"],
        default="dashboard",
    )

    p_quota = sub.add_parser("quota-check", help="Valida uso atual contra quota")
    p_quota.add_argument("--rpm", type=int, required=True)
    p_quota.add_argument("--parallel-jobs", type=int, required=True)
    p_quota.add_argument("--storage-mb", type=int, required=True)
    p_quota.add_argument("--limit-rpm", type=int, default=120)
    p_quota.add_argument("--limit-jobs", type=int, default=4)
    p_quota.add_argument("--limit-storage-mb", type=int, default=500)

    sub.add_parser("eval-run", help="Executa avaliação contínua (evals-as-code MVP)")

    p_i2p = sub.add_parser("issue-to-pr-plan", help="Gera plano de execução issue -> PR")
    p_i2p.add_argument("--issue", required=True)
    p_i2p.add_argument("--repository", default="ATENA-")

    p_rag = sub.add_parser("rag-governance-check", help="Valida RBAC + citações para consulta RAG")
    p_rag.add_argument("--role", required=True, choices=["viewer", "operator", "admin"])
    p_rag.add_argument("--data-classification", required=True, choices=["public", "internal", "confidential"])
    p_rag.add_argument("--has-citations", action="store_true")

    p_sec = sub.add_parser("security-check", help="Scanner simples de risco (prompt/action)")
    p_sec.add_argument("--prompt", required=True)
    p_sec.add_argument("--action", default="open_url")

    p_fin = sub.add_parser("finops-route", help="Roteia modo por custo x qualidade")
    p_fin.add_argument("--complexity", type=int, required=True)
    p_fin.add_argument("--budget", type=float, required=True)
    p_fin.add_argument("--latency-sensitive", action="store_true")

    p_ic = sub.add_parser("incident-commander", help="Gera plano de resposta a incidente (MVP)")
    p_ic.add_argument("--scenario", default="latency-spike")

    p_sub = sub.add_parser("subagent-solve", help="Cria subagente para um problema e integra ao fluxo principal")
    p_sub.add_argument("--problem", required=True)
    p_sub.add_argument("--code-only", action="store_true", help="Retorna apenas o código gerado quando disponível")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    policy = PolicyEngine()
    audit = AuditLogger(EVOLUTION / "policy_audit.jsonl")

    if args.cmd == "policy-check":
        decision = policy.decide_with_context(role=Role(args.role), action=Action(args.action), risk_level=args.risk, hour_utc=args.hour_utc)
        audit.append(
            actor=args.actor,
            role=Role(args.role),
            action=Action(args.action),
            decision=decision,
            metadata={"risk": args.risk, "hour_utc": str(args.hour_utc)},
        )
        _emit("policy-check", decision.__dict__)
        return 0 if decision.allowed else 2

    if args.cmd == "telemetry-log":
        event = telemetry.append(args.mission, args.status, args.latency_ms, args.cost, tenant_id=args.tenant)
        _emit("telemetry-log", event.__dict__)
        return 0

    if args.cmd == "telemetry-summary":
        _emit("telemetry-summary", telemetry.summarize())
        return 0

    if args.cmd == "tenant-report":
        report = telemetry.summarize_by_tenant(args.tenant)
        report["month"] = args.month
        _emit("tenant-report", report)
        return 0

    if args.cmd == "slo-check":
        payload = telemetry.slo_check(
            min_success_rate=args.min_success_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
            max_cost_units=args.max_cost_units,
            window_days=args.window_days,
        )
        _emit("slo-check", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "slo-alert":
        payload = telemetry.slo_check(
            min_success_rate=args.min_success_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
            max_cost_units=args.max_cost_units,
            window_days=args.window_days,
        )
        delivery = {"sent": False, "reason": "webhook not provided"}
        if args.webhook_url:
            delivery = dispatch_alert(
                args.webhook_url,
                payload,
                retries=args.retries,
                backoff_sec=args.backoff_sec,
                dedupe_window_sec=args.dedupe_window_sec,
                state_path=EVOLUTION / "alerts_dedupe.json",
            )
        alert_payload = {
            "status": payload["status"],
            "alert": payload["alert"],
            "sent": bool(delivery.get("sent", False)),
            "delivery": delivery,
        }
        _emit("slo-alert", alert_payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "quality-score":
        profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
        payload = score_profiles_with_baseline(profiles, EVOLUTION / "quality_baseline.json")
        _emit("quality-score", payload)
        return 0 if float(payload.get("score", 0.0)) >= 0.5 else 2

    if args.cmd == "onboarding-run":
        payload = run_onboarding()
        _emit("onboarding-run", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "skill-register":
        market.register(
            SkillRecord(
                skill_id=args.id,
                version=args.version,
                risk_level=args.risk,
                cost_class=args.cost_class,
                compatible_with=args.compat,
            )
        )
        _emit("skill-register", {"status": "registered", "id": args.id, "version": args.version})
        return 0

    if args.cmd == "skill-approve":
        ok = market.approve(args.id, version=args.version)
        _emit("skill-approve", {"status": "approved" if ok else "not-found", "id": args.id, "version": args.version})
        return 0 if ok else 2

    if args.cmd == "skill-promote":
        ok = market.promote(args.id, args.version)
        _emit("skill-promote", {"status": "promoted" if ok else "not-eligible", "id": args.id, "version": args.version})
        return 0 if ok else 2

    if args.cmd == "skill-rollback":
        ok = market.rollback(args.id, args.to_version)
        _emit("skill-rollback", {"status": "rolled-back" if ok else "not-eligible", "id": args.id, "to_version": args.to_version})
        return 0 if ok else 2

    if args.cmd == "skill-list":
        _emit("skill-list", market.list_records())
        return 0

    if args.cmd == "skill-validate":
        ok = market.validate(
            args.id,
            args.version,
            sandbox_passed=args.sandbox_pass,
            contract_passed=args.contract_pass,
            security_passed=args.security_pass,
        )
        _emit(
            "skill-validate",
            {
                "status": "validated" if ok else "not-found",
                "id": args.id,
                "version": args.version,
                "sandbox_passed": bool(args.sandbox_pass),
                "contract_passed": bool(args.contract_pass),
                "security_passed": bool(args.security_pass),
            },
        )
        return 0 if ok else 2

    if args.cmd == "mode-select":
        decision = choose_mode(args.complexity, args.budget, args.latency_sensitive)
        _emit("mode-select", decision.__dict__)
        return 0

    if args.cmd == "incident-drill":
        result = run_incident_drill(args.scenario, primary_provider=args.primary, fallback_provider=args.fallback)
        _emit("incident-drill", result.__dict__)
        return 0 if result.recovered else 2

    if args.cmd == "internet-challenge":
        payload = run_internet_challenge(args.topic)
        _emit("internet-challenge", payload)
        return 0 if payload["status"] in {"ok", "partial"} else 2

    if args.cmd == "quota-check":
        quota = TenantQuota(
            requests_per_minute=args.limit_rpm,
            max_parallel_jobs=args.limit_jobs,
            max_storage_mb=args.limit_storage_mb,
        )
        payload = QuotaManager.evaluate_usage(
            quota,
            requests_per_minute=args.rpm,
            parallel_jobs=args.parallel_jobs,
            storage_mb=args.storage_mb,
        )
        _emit("quota-check", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "production-ready":
        payload = run_readiness(
            telemetry=telemetry,
            market=market,
            evolution_dir=EVOLUTION,
        )
        _emit("production-ready", payload)
        return 0 if payload["status"] in {"pass", "warn"} else 2

    if args.cmd == "remediation-plan":
        readiness = run_readiness(
            telemetry=telemetry,
            market=market,
            evolution_dir=EVOLUTION,
        )
        payload = build_remediation_plan(readiness)
        _emit("remediation-plan", payload)
        return 0

    if args.cmd == "perfection-plan":
        payload = build_perfection_plan()
        _emit("perfection-plan", payload)
        return 0

    if args.cmd == "go-live-gate":
        readiness = run_readiness(
            telemetry=telemetry,
            market=market,
            evolution_dir=EVOLUTION,
        )
        remediation = build_remediation_plan(readiness)
        slo_payload = telemetry.slo_check(
            min_success_rate=args.min_success_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
            max_cost_units=args.max_cost_units,
            window_days=args.window_days,
        )
        decision = evaluate_go_live(readiness=readiness, remediation=remediation, slo_alert=slo_payload)
        _emit("go-live-gate", decision)
        return 0 if decision["decision"] == "GO" else 2

    if args.cmd == "self-audit":
        payload = run_self_audit(ROOT)
        _emit("self-audit", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "programming-probe":
        payload = run_programming_probe(ROOT, prefix=args.prefix, site_template=args.site_template)
        _emit("programming-probe", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "eval-run":
        payload = run_eval_suite(telemetry)
        _emit("eval-run", payload)
        return 0 if payload["status"] == "pass" else 2

    if args.cmd == "issue-to-pr-plan":
        payload = build_issue_to_pr_plan(args.issue, args.repository)
        _emit("issue-to-pr-plan", payload)
        return 0

    if args.cmd == "rag-governance-check":
        payload = run_rag_governance_check(args.role, args.data_classification, args.has_citations)
        _emit("rag-governance-check", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "security-check":
        payload = run_security_check(args.prompt, args.action)
        _emit("security-check", payload)
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "finops-route":
        payload = run_finops_route(args.complexity, args.budget, args.latency_sensitive)
        _emit("finops-route", payload)
        return 0 if payload["budget_ok"] else 2

    if args.cmd == "incident-commander":
        payload = run_incident_commander(args.scenario, EVOLUTION / "telemetry.jsonl")
        _emit("incident-commander", payload)
        return 0

    if args.cmd == "subagent-solve":
        payload = solve_with_subagent(args.problem, history_path=EVOLUTION / "telemetry.jsonl")
        if getattr(args, "code_only", False):
            code_solution = payload.get("code_solution")
            if isinstance(code_solution, str) and code_solution.strip():
                print(code_solution.rstrip())
                return 0
        _emit("subagent-solve", payload)
        return 0 if payload.get("status") == "ok" else 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
