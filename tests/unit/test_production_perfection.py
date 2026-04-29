from pathlib import Path

from core.production_observability import TelemetryStore
from core.production_perfection import build_perfection_plan
from core.skill_marketplace import SkillMarketplace, SkillRecord


def test_build_perfection_plan_shape(tmp_path: Path):
    payload = build_perfection_plan(tmp_path)
    assert payload["status"] == "in-progress"
    assert isinstance(payload["tracks"], list)
    assert payload["tracks"]


def test_build_perfection_plan_can_reach_complete(tmp_path: Path):
    telemetry = TelemetryStore(tmp_path / "telemetry.jsonl")
    telemetry.append("future-ai", "ok", 300, 10)
    telemetry.append("guardian", "ok", 350, 12)
    telemetry.append("production-ready", "ok", 320, 11)

    market = SkillMarketplace(tmp_path / "skills_catalog.json")
    market.register(
        SkillRecord(
            skill_id="core-skill",
            version="1.0.0",
            risk_level="low",
            cost_class="standard",
            compatible_with=">=3.2.0",
        )
    )
    assert market.approve("core-skill", "1.0.0") is True
    assert market.promote("core-skill", "1.0.0") is True

    (tmp_path / "policy_audit.jsonl").write_text('{"event":"ok"}\n', encoding="utf-8")

    payload = build_perfection_plan(tmp_path)
    assert payload["status"] == "complete"
    assert payload["progress_pct"] == 100.0
    assert all(track["completed"] for track in payload["tracks"])
