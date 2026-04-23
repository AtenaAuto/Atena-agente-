from pathlib import Path

from core.production_self_audit import run_self_audit


def test_run_self_audit_shape():
    payload = run_self_audit(Path.cwd())
    assert payload["status"] in {"ok", "needs-work"}
    assert payload["total"] >= payload["passed"]
    assert isinstance(payload["checks"], list)
