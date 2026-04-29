from __future__ import annotations

from protocols.atena_enterprise_advanced_mission import _sanitize_payload_for_persistence


def test_sanitize_payload_for_persistence_redacts_secret_and_marks_warn():
    payload = {"steps": ["usar token ghp_ABCDEF1234567890XYZ1234"]}

    safe_payload = _sanitize_payload_for_persistence(payload)

    assert safe_payload["security_redaction"]["status"] == "warn"
    assert safe_payload["security_redaction"]["redacted"] is True
    assert "[REDACTED_SECRET]" in safe_payload["steps"][0]


def test_sanitize_payload_for_persistence_marks_ok_without_secret():
    payload = {"steps": ["sem segredo aqui"]}

    safe_payload = _sanitize_payload_for_persistence(payload)

    assert safe_payload["security_redaction"]["status"] == "ok"
    assert safe_payload["security_redaction"]["redacted"] is False
