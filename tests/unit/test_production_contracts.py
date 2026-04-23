from core.production_contracts import validate_contract


def test_validate_contract_success():
    payload = {
        "window_days": 7,
        "thresholds": {},
        "summary": {},
        "checks": {},
        "status": "ok",
    }
    assert validate_contract("slo-check", payload) == []


def test_validate_contract_missing_fields():
    errors = validate_contract("tenant-report", {"tenant_id": "t1"})
    assert errors
    assert any("missing field" in e for e in errors)


def test_validate_contract_production_ready():
    payload = {"status": "warn", "checks": [], "summary": {}}
    assert validate_contract("production-ready", payload) == []


def test_validate_contract_remediation_plan():
    payload = {"status": "warn", "actions": [], "total_actions": 0}
    assert validate_contract("remediation-plan", payload) == []


def test_validate_contract_perfection_plan():
    payload = {"generated_at": "2026-04-14T00:00:00+00:00", "status": "in-progress", "tracks": [], "success_criteria": {}}
    assert validate_contract("perfection-plan", payload) == []


def test_validate_contract_internet_challenge():
    payload = {"topic": "ai", "status": "ok", "confidence": 1.0, "sources": [], "recommendation": "x"}
    assert validate_contract("internet-challenge", payload) == []


def test_validate_contract_slo_alert():
    payload = {"status": "ok", "alert": {}, "sent": False, "delivery": {}}
    assert validate_contract("slo-alert", payload) == []


def test_validate_contract_go_live_gate():
    payload = {"decision": "GO", "blockers": [], "readiness_status": "pass", "slo_status": "ok", "pending_actions": 1}
    assert validate_contract("go-live-gate", payload) == []


def test_validate_contract_self_audit():
    payload = {"status": "ok", "score": 1.0, "passed": 1, "total": 1, "checks": [], "recommendations": []}
    assert validate_contract("self-audit", payload) == []
