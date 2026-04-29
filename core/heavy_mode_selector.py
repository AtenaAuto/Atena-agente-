#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seletor leve/pesado para ATENA com orçamento simples de compute."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeavyModeDecision:
    mode: str  # light | heavy
    reason: str
    estimated_cost: float


def choose_mode(task_complexity: int, budget_units: float, latency_sensitive: bool) -> HeavyModeDecision:
    complexity = max(1, min(task_complexity, 10))
    heavy_cost = round(0.8 + (complexity * 0.35), 2)
    light_cost = round(0.1 + (complexity * 0.08), 2)

    if latency_sensitive and complexity <= 6:
        return HeavyModeDecision("light", "latency_sensitive", light_cost)
    if complexity >= 7 and budget_units >= heavy_cost:
        return HeavyModeDecision("heavy", "high_complexity_and_budget_ok", heavy_cost)
    return HeavyModeDecision("light", "default_cost_guardrail", light_cost)
