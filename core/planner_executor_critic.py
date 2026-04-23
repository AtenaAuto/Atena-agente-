#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Planner → Executor → Critic em modo MVP corporativo."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StepResult:
    step: str
    status: str
    risk: float
    score: float


def decompose_goal(goal: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[.;\n]", goal) if p.strip()]
    if len(parts) <= 1 and " e " in goal:
        parts = [p.strip() for p in goal.split(" e ") if p.strip()]
    return parts or [goal.strip()]


def _estimate_risk(step: str) -> float:
    step_l = step.lower()
    risk = 0.2
    if any(k in step_l for k in ["delete", "drop", "produção", "prod"]):
        risk += 0.5
    if any(k in step_l for k in ["migr", "deploy", "rollback"]):
        risk += 0.2
    return min(1.0, risk)


def _execute_step(step: str) -> StepResult:
    risk = _estimate_risk(step)
    blocked = risk >= 0.8
    status = "blocked" if blocked else "ok"
    score = max(0.0, 1.0 - risk)
    return StepResult(step=step, status=status, risk=round(risk, 2), score=round(score, 2))


def run_planner_loop(goal: str, risk_threshold: float = 0.75) -> dict[str, object]:
    steps = decompose_goal(goal)
    executed = []
    blocked_indexes = []

    for idx, step in enumerate(steps):
        result = _execute_step(step)
        checkpoint = {
            "index": idx,
            "step": result.step,
            "status": result.status,
            "risk": result.risk,
            "score": result.score,
            "go_no_go": "go" if result.risk < risk_threshold and result.status == "ok" else "no_go",
        }
        executed.append(checkpoint)
        if checkpoint["go_no_go"] == "no_go":
            blocked_indexes.append(idx)
            break

    avg_score = round(sum(item["score"] for item in executed) / max(1, len(executed)), 2)
    avg_risk = round(sum(item["risk"] for item in executed) / max(1, len(executed)), 2)

    return {
        "status": "ok" if not blocked_indexes else "warn",
        "goal": goal,
        "steps_total": len(steps),
        "steps_executed": len(executed),
        "checkpoints": executed,
        "critic": {
            "quality_score": avg_score,
            "risk_score": avg_risk,
            "blocked_indexes": blocked_indexes,
            "auto_rollback_suggested": len(blocked_indexes) > 0,
        },
    }
