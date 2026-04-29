"""Testa RLHF corrigido — verifica que SQL bug foi eliminado."""
import os, tempfile, pytest
os.environ.setdefault("ATENA_TEST_MODE", "1")

def _engine():
    from modules.rlhf_engine import RLHFEngine
    tmp = tempfile.mktemp(suffix=".db")
    return RLHFEngine(db_path=tmp)

def test_initial_multiplier_is_one():
    e = _engine()
    assert e.get_reward_multiplier("add_logging") == 1.0

def test_success_increases_score():
    e = _engine()
    s1 = e.record_feedback("add_logging", success=True)
    assert s1 > 1.0, f"esperava >1.0, obteve {s1}"

def test_failure_decreases_score():
    e = _engine()
    s1 = e.record_feedback("rename_var", success=False)
    assert s1 < 1.0, f"esperava <1.0, obteve {s1}"

def test_score_clamps_between_min_max():
    e = _engine()
    for _ in range(50):
        e.record_feedback("add_type_hints", success=False)
    s = e.get_reward_multiplier("add_type_hints")
    assert s >= 0.10, f"clamp min falhou: {s}"
    for _ in range(100):
        e.record_feedback("add_type_hints", success=True)
    s = e.get_reward_multiplier("add_type_hints")
    assert s <= 2.00, f"clamp max falhou: {s}"

def test_sql_bug_fixed_delta_not_absolute():
    """Bug original: EXCLUDED.reward_score = 1.0+delta em vez de reward_score+delta."""
    e = _engine()
    # 5 sucessos → score deve ser ~1.5 (1.0 + 5*0.10)
    for _ in range(5):
        e.record_feedback("extract_helper", success=True)
    score = e.get_reward_multiplier("extract_helper")
    # Bug antigo daria ~1.1 (reset a cada update)
    assert score >= 1.4, f"bug SQL não corrigido — score={score}"

def test_top_and_worst_mutations():
    e = _engine()
    e.record_feedback("A", success=True)
    e.record_feedback("A", success=True)
    e.record_feedback("B", success=False)
    top = e.top_mutations(1)
    assert top[0]["type"] == "A"
    worst = e.worst_mutations(1)
    assert worst[0]["type"] == "B"
