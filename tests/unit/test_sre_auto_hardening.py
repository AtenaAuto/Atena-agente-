from core.sre_auto_hardening import evaluate_regression, generate_postmortem


def test_regression_detection_and_postmortem():
    reg = evaluate_regression(
        success_rate=0.85,
        latency_ms=900,
        cost_units=200,
        baseline_success=0.95,
        baseline_latency_ms=500,
        baseline_cost_units=100,
    )
    assert reg["status"] == "warn"
    assert reg["rollback_suggested"] is True

    pm = generate_postmortem("incident", reg["regressions"], reg["rollback_suggested"])
    assert pm["incident"] == "incident"
    assert isinstance(pm["next_steps"], list)
