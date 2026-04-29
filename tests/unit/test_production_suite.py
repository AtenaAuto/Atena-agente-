from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.heavy_mode_selector import choose_mode
from core.production_access import AccessManager, AccessRole, QuotaManager, TenantQuota, UserIdentity, Workspace
from core.production_observability import TelemetryStore
from core.production_onboarding import run_onboarding
from core.production_quality_harness import score_profiles, score_profiles_with_baseline
from core.skill_marketplace import SkillMarketplace, SkillRecord


def test_access_manager_tenant_isolation():
    ws_a = Workspace(workspace_id="w1", tenant_id="t1", name="core")
    user_ok = UserIdentity(user_id="u1", tenant_id="t1", role=AccessRole.DEV, workspaces={"w1"})
    user_other_tenant = UserIdentity(user_id="u2", tenant_id="t2", role=AccessRole.ADMIN, workspaces=set())

    assert AccessManager.can_access_workspace(user_ok, ws_a) is True
    assert AccessManager.can_access_workspace(user_other_tenant, ws_a) is False


def test_telemetry_store_summary(tmp_path: Path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    store.append("doctor", "ok", 120, 0.5, tenant_id="t1")
    store.append("smoke", "failed", 250, 1.0, tenant_id="t2")
    summary = store.summarize()

    assert summary["total"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["cost_units"] == 1.5


def test_telemetry_slo_and_tenant_report(tmp_path: Path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    store.append("doctor", "ok", 100, 2.0, tenant_id="tenant-a")
    store.append("guardian", "ok", 150, 1.0, tenant_id="tenant-a")
    store.append("ops", "failed", 900, 10.0, tenant_id="tenant-b")

    tenant_a = store.summarize_by_tenant("tenant-a")
    assert tenant_a["total"] == 2
    assert tenant_a["success_rate"] == 1.0

    slo = store.slo_check(min_success_rate=0.5, max_avg_latency_ms=500, max_cost_units=20, window_days=30)
    assert slo["status"] == "ok"


def test_skill_marketplace_register_approve_promote_rollback(tmp_path: Path):
    market = SkillMarketplace(tmp_path / "skills.json")
    market.register(
        SkillRecord(
            skill_id="atena-orchestrator",
            version="1.0.0",
            risk_level="medium",
            cost_class="standard",
            compatible_with=">=3.2.0",
        )
    )
    market.register(
        SkillRecord(
            skill_id="atena-orchestrator",
            version="1.1.0",
            risk_level="medium",
            cost_class="standard",
            compatible_with=">=3.2.0",
        )
    )
    assert market.approve("atena-orchestrator", version="1.1.0") is True
    assert market.promote("atena-orchestrator", "1.1.0") is True
    assert market.active_version("atena-orchestrator") == "1.1.0"
    assert market.rollback("atena-orchestrator", "1.1.0") is True


def test_choose_mode_prefers_heavy_with_budget():
    decision = choose_mode(task_complexity=9, budget_units=5.0, latency_sensitive=False)
    assert decision.mode == "heavy"


def test_quality_harness_scoring_mocked(tmp_path: Path):
    with patch("core.production_quality_harness.subprocess.run", return_value=SimpleNamespace(returncode=0)):
        payload = score_profiles(["support", "dev"])
        baseline = score_profiles_with_baseline(["support", "dev"], tmp_path / "baseline.json")
    assert payload["score"] == 1.0
    assert payload["passed"] == 2
    assert baseline["baseline"]["history_points"] == 1


def test_onboarding_flow_mocked():
    with patch("core.production_onboarding.subprocess.run", return_value=SimpleNamespace(returncode=0)):
        payload = run_onboarding()
    assert payload["status"] == "ok"
    assert payload["completed_steps"] == payload["total_steps"]


def test_quota_manager_evaluate_usage():
    quota = TenantQuota(requests_per_minute=120, max_parallel_jobs=4, max_storage_mb=500)
    result = QuotaManager.evaluate_usage(quota, requests_per_minute=100, parallel_jobs=2, storage_mb=400)
    assert result["status"] == "ok"
