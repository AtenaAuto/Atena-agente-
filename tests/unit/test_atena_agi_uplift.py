#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from core.atena_agi_uplift import (
    AGIMaturityAssessor,
    ContinuousEvaluator,
    GeneralizationRouter,
    LongTermMemoryEngine,
    MultiStepPlanner,
    SecurityAuditor,
    SelfCorrectionEngine,
)


def test_long_term_memory_semantic_recall(tmp_path: Path):
    mem = LongTermMemoryEngine(tmp_path)
    mem.remember_decision(
        objective="estabilidade deploy",
        decision="adotar benchmark diário",
        outcome="menos regressão",
        tags=["deploy", "benchmark"],
    )
    hits = mem.semantic_recall("benchmark deploy", top_k=2)
    assert hits
    assert hits[0]["semantic_score"] > 0
    history = mem.decision_history(limit=1)
    assert history[0]["decision_id"]
    assert mem.ensure_minimum_decisions(5) >= 5


def test_continuous_evaluator_regression_guard(tmp_path: Path):
    ev = ContinuousEvaluator(tmp_path)
    ev.record_score(0.9, "2026-04-13")
    ev.record_score(0.91, "2026-04-14")
    ev.record_score(0.89, "2026-04-15")
    ev.record_score(0.70, "2026-04-16")
    guard = ev.regression_guard(min_drop=0.08, window=3)
    assert guard["block_deploy"] is True
    gate = ev.enforce_deploy_gate(guard)
    assert gate["blocked"] is True
    assert ev.ensure_minimum_days(14) >= 14
    multi = ev.run_multidomain_benchmark({"dev": [["python", "-c", "print('ok')"]]}, cwd=tmp_path)
    assert multi["dev"]["score"] == 1.0


def test_multistep_planner_and_security_and_generalization(tmp_path: Path):
    planner = MultiStepPlanner()
    result = planner.execute(
        objective="melhorar qualidade",
        step_executor=lambda step: (True, step),
        rollback=lambda step: f"rb:{step}",
    )
    assert result["status"] == "ok"
    assert len(result["results"]) >= 4

    sec = SecurityAuditor(tmp_path)
    assert sec.can_execute("tier2", approved=False) is False
    audit = sec.audit("deploy-main", "tier2", approved=False, result="blocked")
    assert audit["result"] == "blocked"
    assert audit["hash"]
    assert sec.ensure_minimum_audits(5) >= 5

    router = GeneralizationRouter()
    routed = router.expand_plan("Criar roadmap e pricing para GTM")
    assert routed["domain"] == "estrategia"
    assert routed["playbook"]


def test_self_correction_iterative(tmp_path: Path):
    engine = SelfCorrectionEngine()
    result = engine.run_iterative(
        test_cmd=["python", "-c", "print('ok')"],
        patch_cmds=[["python", "-c", "print('patch')"]],
        rollback_cmd=["python", "-c", "print('rollback')"],
        cwd=tmp_path,
    )
    assert result["status"] == "ok"


def test_agi_maturity_assessor_returns_score_and_plan(tmp_path: Path):
    assessor = AGIMaturityAssessor(tmp_path)
    assessment = assessor.assess()
    assert 1.0 <= assessment["score_1_to_10"] <= 10.0
    plan = assessor.plan_to_ten(assessment)
    assert plan
