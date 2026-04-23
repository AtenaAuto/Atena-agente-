#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Camada de capacidades avançadas essenciais para a ATENA."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class EssentialCapability:
    key: str
    name: str
    description: str


class AtenaAdvancedEssentials:
    """Gerencia 10 capacidades avançadas essenciais para operação evolutiva."""

    def __init__(self) -> None:
        self._catalog: List[EssentialCapability] = [
            EssentialCapability("health_monitoring", "Health Monitoring", "Monitora saúde operacional por ciclo."),
            EssentialCapability("safety_guardrails", "Safety Guardrails", "Bloqueia mutações com risco alto e garante segurança mínima."),
            EssentialCapability("objective_planner", "Objective Planner", "Prioriza objetivos com base em impacto e estagnação."),
            EssentialCapability("memory_tiering", "Memory Tiering", "Organiza memória recente, episódica e histórica."),
            EssentialCapability("reflection_engine", "Reflection Engine", "Gera sinais de auto-reflexão por performance e falhas."),
            EssentialCapability("experiment_tracker", "Experiment Tracker", "Versiona experimentos e métricas por geração."),
            EssentialCapability("rollback_manager", "Rollback Manager", "Mantém estratégia de rollback seguro quando necessário."),
            EssentialCapability("telemetry_pipeline", "Telemetry Pipeline", "Padroniza telemetria para observabilidade."),
            EssentialCapability("self_healing_hooks", "Self-healing Hooks", "Dispara rotinas de auto-correção após degradação."),
            EssentialCapability("policy_governance", "Policy Governance", "Aplica políticas de governança para evolução controlada."),
        ]
        self._history: deque[Dict[str, Any]] = deque(maxlen=50)
        self._boot: Dict[str, Any] = {}

    def bootstrap(self, core_generation: int, best_score: float) -> Dict[str, Any]:
        self._boot = {
            "generation": core_generation,
            "best_score": round(best_score, 4),
            "ts": datetime.now(timezone.utc).isoformat(),
            "capabilities": [c.key for c in self._catalog],
        }
        return dict(self._boot)

    def essentials_catalog(self) -> List[Dict[str, str]]:
        return [asdict(c) for c in self._catalog]

    def on_cycle_end(
        self,
        generation: int,
        score: float,
        score_delta: float,
        stagnation_cycles: int,
        replaced: bool,
    ) -> Dict[str, Any]:
        recommendations: List[str] = []
        if stagnation_cycles >= 3:
            recommendations.append("Aumentar exploração e revisar operadores de mutação com baixo impacto.")
        if score_delta <= 0 and not replaced:
            recommendations.append("Executar experimento guiado por problema para recuperar ganho de fitness.")
        if score >= 95:
            recommendations.append("Ativar modo conservador para reduzir risco de regressão.")

        item = {
            "generation": generation,
            "score": round(score, 4),
            "score_delta": round(score_delta, 4),
            "stagnation_cycles": stagnation_cycles,
            "replaced": replaced,
            "recommendations": recommendations,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(item)
        return item

    def status(self) -> Dict[str, Any]:
        return {
            "boot": dict(self._boot),
            "catalog_size": len(self._catalog),
            "catalog": self.essentials_catalog(),
            "recent_cycles": list(self._history),
        }
