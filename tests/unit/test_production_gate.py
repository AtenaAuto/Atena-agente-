from core.production_gate import evaluate_go_live


def test_evaluate_go_live_go():
    payload = evaluate_go_live(
        readiness={"status": "pass"},
        remediation={"total_actions": 1},
        slo_alert={"status": "ok"},
    )
    assert payload["decision"] == "GO"


def test_evaluate_go_live_no_go():
    payload = evaluate_go_live(
        readiness={"status": "fail"},
        remediation={"total_actions": 3},
        slo_alert={"status": "violated"},
    )
    assert payload["decision"] == "NO_GO"
    assert payload["blockers"]
