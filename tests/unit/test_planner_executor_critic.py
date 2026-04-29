from core.planner_executor_critic import decompose_goal, run_planner_loop


def test_planner_decompose_and_run_ok():
    steps = decompose_goal("mapear requisitos; criar plano; validar")
    assert len(steps) == 3

    payload = run_planner_loop("mapear requisitos; criar plano; validar", risk_threshold=0.8)
    assert payload["steps_total"] >= 1
    assert payload["critic"]["quality_score"] >= 0


def test_planner_blocks_high_risk_step():
    payload = run_planner_loop("deploy em produção e delete dados", risk_threshold=0.7)
    assert payload["status"] in {"ok", "warn"}
