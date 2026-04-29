from pathlib import Path

from core.production_observability import TelemetryStore
from core.production_readiness import build_remediation_plan, run_readiness
from core.skill_marketplace import SkillMarketplace, SkillRecord


def test_run_readiness_warn_without_required_baseline(tmp_path: Path):
    telemetry = TelemetryStore(tmp_path / "telemetry.jsonl")
    market = SkillMarketplace(tmp_path / "skills.json")

    market.register(
        SkillRecord(
            skill_id="prod-skill",
            version="1.0.0",
            risk_level="medium",
            cost_class="standard",
            compatible_with=">=3.2.0",
            approved=True,
            active=True,
        )
    )
    telemetry.append("doctor", "ok", 100, 1.0)

    payload = run_readiness(telemetry=telemetry, market=market, evolution_dir=tmp_path)
    assert payload["status"] in {"pass", "warn"}
    assert payload["summary"]["total_checks"] >= 4


def test_build_remediation_plan():
    payload = {
        "status": "fail",
        "checks": [
            {"name": "slo_baseline", "ok": False},
            {"name": "approved_active_skill", "ok": False},
        ],
    }
    plan = build_remediation_plan(payload)
    assert plan["total_actions"] >= 2
