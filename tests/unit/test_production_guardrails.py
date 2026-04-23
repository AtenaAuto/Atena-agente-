from pathlib import Path

from core.production_guardrails import Action, AuditLogger, PolicyEngine, Role


def test_viewer_only_read_status():
    engine = PolicyEngine()
    allowed = engine.decide(Role.VIEWER, Action.READ_STATUS)
    denied = engine.decide(Role.VIEWER, Action.RUN_DIAGNOSTIC)

    assert allowed.allowed is True
    assert allowed.requires_approval is False
    assert denied.allowed is False


def test_operator_open_url_requires_approval():
    engine = PolicyEngine()
    decision = engine.decide(Role.OPERATOR, Action.OPEN_URL)

    assert decision.allowed is True
    assert decision.requires_approval is True


def test_operator_high_risk_denied():
    engine = PolicyEngine()
    decision = engine.decide_with_context(role=Role.OPERATOR, action=Action.OPEN_URL, risk_level="high", hour_utc=14)
    assert decision.allowed is False


def test_audit_logger_writes_jsonl(tmp_path: Path):
    engine = PolicyEngine()
    logger = AuditLogger(tmp_path / "audit.jsonl")
    decision = engine.decide(Role.ADMIN, Action.RUN_MUTABLE_COMMAND)
    event = logger.append(
        actor="alice",
        role=Role.ADMIN,
        action=Action.RUN_MUTABLE_COMMAND,
        decision=decision,
        metadata={"ticket": "INC-42"},
    )

    assert event.actor == "alice"
    content = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    assert '"decision": "allowed"' in content[0]
