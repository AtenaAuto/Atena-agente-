from pathlib import Path

from core.atena_capability_challenge import run_capability_challenge


ROOT = Path(__file__).resolve().parents[2]


def test_capability_challenge_scores_core_tasks():
    payload = run_capability_challenge("criar um produto SaaS auditável")

    assert payload["status"] == "pass"
    assert payload["score"] == 1.0
    assert payload["passed"] == payload["total"] == 5
    assert payload["claim"].startswith("ATENA deve provar capacidades")
    assert {task["name"] for task in payload["tasks"]} == {
        "objective_decomposition",
        "safety_boundary",
        "implementation_strategy",
        "verification_plan",
        "delivery_protocol",
    }


def test_capability_challenge_with_codegen_evidence():
    payload = run_capability_challenge(
        "provar que consegue programar uma entrega completa",
        include_codegen=True,
        root=ROOT,
    )

    assert payload["status"] == "pass"
    assert payload["score"] == 1.0
    assert payload["codegen_evidence"]["status"] == "ok"
    assert payload["codegen_evidence"]["generated_project_types"] == [
        "api",
        "cli",
        "library",
        "microservice",
        "site",
    ]


def test_capability_challenge_universal_suite_maps_domains():
    payload = run_capability_challenge("ela faz tudo com segurança", suite="universal")

    assert payload["status"] == "pass"
    assert payload["suite"] == "universal"
    assert payload["passed"] == payload["total"]
    assert payload["total"] == 12
    assert {item["name"] for item in payload["domain_results"]} == {
        "code_generation",
        "research_synthesis",
        "workflow_automation",
        "production_operations",
        "product_strategy",
        "data_analysis",
        "safety_governance",
    }
    high_risk = [item for item in payload["domain_results"] if item["risk_level"] == "high"]
    assert high_risk
    assert all("exigir revisão humana antes de impacto real" in item["guardrails"] for item in high_risk)


def test_capability_challenge_rejects_unknown_suite():
    try:
        run_capability_challenge("teste", suite="infinita")
    except ValueError as exc:
        assert "suite must" in str(exc)
    else:
        raise AssertionError("invalid suite should fail")


def test_capability_challenge_extreme_suite_runs_stress_probes():
    payload = run_capability_challenge("teste extremo de tudo com segurança", suite="extreme")

    assert payload["status"] == "pass"
    assert payload["suite"] == "extreme"
    assert payload["passed"] == payload["total"]
    assert payload["total"] == 17
    assert {item["name"] for item in payload["extreme_results"]} == {
        "ambiguous_goal_resolution",
        "adversarial_safety_boundary",
        "long_horizon_delivery",
        "resource_constraint",
        "reproducibility_audit",
    }
    assert payload["risk_report"] == {
        "high_risk_domains": ["production_operations", "safety_governance"],
        "requires_human_review": True,
        "destructive_actions_allowed": False,
    }
    assert all(item["ok"] for item in payload["extreme_results"])
