"""Testa planner com modelo de risco calibrado."""
from core.planner_executor_critic import _estimate_risk, decompose_goal, run_planner_loop

def test_delete_high_risk():
    assert _estimate_risk("delete all users from database") >= 0.55

def test_test_env_reduces_risk():
    r_prod = _estimate_risk("deploy to production")
    r_test = _estimate_risk("deploy to staging sandbox")
    assert r_test < r_prod

def test_backup_reduces_risk():
    r1 = _estimate_risk("drop table users")
    r2 = _estimate_risk("drop table users after backup and snapshot")
    assert r2 < r1

def test_safe_step_low_risk():
    assert _estimate_risk("create new module for logging") < 0.30

def test_decompose_semicolon():
    steps = decompose_goal("step one; step two; step three")
    assert len(steps) == 3

def test_planner_blocks_high_risk():
    result = run_planner_loop("delete all production data", risk_threshold=0.75)
    assert result["critic"]["blocked_indexes"]

def test_planner_allows_safe():
    result = run_planner_loop("create unit tests for the new feature")
    assert result["status"] == "ok"
    assert not result["critic"]["blocked_indexes"]

def test_planner_has_risk_signals():
    result = run_planner_loop("drop table users in production database")
    chk = result["checkpoints"][0]
    assert len(chk.get("risk_signals", [])) > 0
