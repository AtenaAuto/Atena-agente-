from __future__ import annotations

from protocols import atena_enterprise_readiness_mission as mission


def test_merge_allowlists_keeps_defaults_and_user_patterns() -> None:
    merged = mission._merge_allowlists([r"^custom/file.py:10$", mission.DEFAULT_SECRET_ALLOWLIST[0]])
    assert mission.DEFAULT_SECRET_ALLOWLIST[0] in merged
    assert r"^custom/file.py:10$" in merged
    assert len(merged) == 2


def test_apply_allowlist_ignores_secret_scan_test_fixture_findings() -> None:
    raw = {
        "ok": False,
        "findings": [
            {"file": "tests/unit/test_atena_secret_scan.py", "line": 53, "pattern": "ghp_[A-Za-z0-9]{30,}"},
            {"file": "core/real_file.py", "line": 10, "pattern": "sk-[A-Za-z0-9]{20,}"},
        ],
        "scanned_files": 2,
    }

    filtered = mission._apply_allowlist(raw, mission._merge_allowlists([]))
    assert filtered["ok"] is False
    assert len(filtered["findings"]) == 1
    assert filtered["findings"][0]["file"] == "core/real_file.py"


def test_apply_allowlist_no_findings_after_filter_marks_ok() -> None:
    raw = {
        "ok": False,
        "findings": [
            {"file": "tests/unit/test_atena_secret_scan.py", "line": 99, "pattern": "ghp_[A-Za-z0-9]{30,}"}
        ],
        "scanned_files": 1,
    }

    filtered = mission._apply_allowlist(raw, mission._merge_allowlists([]))
    assert filtered["ok"] is True
    assert filtered["findings"] == []
