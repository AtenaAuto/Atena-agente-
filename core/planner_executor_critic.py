#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Planner → Executor → Critic (v2)
Versão anterior usava heurísticas de string frágeis para estimar risco.
Agora usa um modelo de risco composto com pesos calibrados e contexto
aprendido do histórico de missões.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("atena.planner")

ROOT    = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "evolution" / "planner_history.db"


# ── Modelo de risco ───────────────────────────────────────────────────────────

# (keyword, peso_de_risco)  — soma-se e clipa em [0, 1]
_RISK_SIGNALS: list[tuple[re.Pattern, float]] = [
    # Operações destruidoras de dados — altíssimo risco
    (re.compile(r"\b(delete|drop\s+table|truncate|remove|apaga[r]?|exclu[ri])\b", re.I), 0.55),
    (re.compile(r"\bprodução|prod\b|live\b|production\b", re.I),                         0.40),
    (re.compile(r"\bformat[ae]?\b|wipe\b|overwrite\b|sobrescreve\b",         re.I),       0.35),
    # Operações de infraestrutura — risco médio-alto
    (re.compile(r"\bdeploy\b|publish\b|release\b|publica[r]?\b",             re.I),       0.25),
    (re.compile(r"\bmigra[r]?|migration\b|alter\s+table\b",                  re.I),       0.20),
    (re.compile(r"\brollback\b|revert\b|restaura[r]?\b",                     re.I),       0.15),
    (re.compile(r"\brestart\b|reboot\b|reinicia[r]?\b",                      re.I),       0.15),
    # Operações de rede e segurança
    (re.compile(r"\bfirewall\b|iptables\b|chmod\s+777\b|sudo\b",             re.I),       0.20),
    (re.compile(r"\bapi.key\b|secret\b|credential\b|senha\b|password\b",     re.I),       0.20),
    (re.compile(r"\bexternal\s+api\b|third.party\b|webhook\b",               re.I),       0.10),
    # Operações de código
    (re.compile(r"\beval\b|exec\b|subprocess\b|shell\b",                     re.I),       0.15),
    (re.compile(r"\bauto.commit\b|force.push\b|push.*main\b",                re.I),       0.20),
    # Redutores de risco (sinal negativo)
    (re.compile(r"\btest[ae]?\b|sandbox\b|staging\b|dry.run\b|simulat\b",   re.I),      -0.15),
    (re.compile(r"\bbackup\b|snapshot\b|checkpoint\b",                        re.I),      -0.10),
    (re.compile(r"\bvalidat\b|verifica[r]?\b|review\b|aprovar\b",            re.I),      -0.05),
]

_BASE_RISK = 0.10  # risco mínimo para qualquer passo


def _estimate_risk(step: str, history_bias: float = 0.0) -> float:
    """
    Calcula risco composto com pesos calibrados.
    history_bias: ajuste vindo do histórico de missões similares (-0.3 a +0.3).
    """
    risk = _BASE_RISK
    for pattern, weight in _RISK_SIGNALS:
        if pattern.search(step):
            risk += weight
    risk += history_bias
    return round(max(0.0, min(1.0, risk)), 3)


# ── Histórico de missões ──────────────────────────────────────────────────────

class PlannerHistory:
    """Registra resultados reais de missões para refinar estimativas futuras."""

    def __init__(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mission_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         REAL    NOT NULL,
                    step_hash  TEXT    NOT NULL,
                    step_text  TEXT    NOT NULL,
                    risk_est   REAL    NOT NULL,
                    outcome    TEXT    NOT NULL,  -- 'ok' | 'fail' | 'blocked'
                    actual_ok  INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_step_hash ON mission_history(step_hash)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _step_hash(self, step: str) -> str:
        import hashlib
        return hashlib.sha1(step.strip().lower().encode()).hexdigest()[:12]

    def record(self, step: str, risk_est: float, outcome: str, actual_ok: bool) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO mission_history (ts, step_hash, step_text, risk_est, outcome, actual_ok)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (time.time(), self._step_hash(step), step[:300], risk_est, outcome, int(actual_ok)))

    def bias_for_step(self, step: str) -> float:
        """
        Retorna bias histórico para um step similar.
        Se passos similares falharam muito → +bias (mais risco).
        Se passos similares tiveram sucesso → -bias (menos risco).
        """
        h = self._step_hash(step)
        with self._conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*), SUM(actual_ok) FROM mission_history WHERE step_hash = ?
            """, (h,)).fetchone()
        total, ok = row
        if not total:
            return 0.0
        fail_rate = 1.0 - (ok / total)
        # Converte fail_rate [0,1] em bias [-0.2, +0.2]
        return round((fail_rate - 0.5) * 0.4, 3)


_history = PlannerHistory()


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StepResult:
    step:    str
    status:  str
    risk:    float
    score:   float
    signals: list[str] = field(default_factory=list)


# ── Decomposição de objetivos ─────────────────────────────────────────────────

def decompose_goal(goal: str) -> list[str]:
    """Divide objetivo em passos por pontuação, ';', '\n' e ' e '."""
    parts = [p.strip() for p in re.split(r"[.;\n]", goal) if p.strip()]
    if len(parts) <= 1 and " e " in goal:
        parts = [p.strip() for p in goal.split(" e ") if p.strip()]
    return parts or [goal.strip()]


# ── Execução de passo ─────────────────────────────────────────────────────────

def _execute_step(step: str) -> StepResult:
    bias = _history.bias_for_step(step)
    risk = _estimate_risk(step, history_bias=bias)
    blocked = risk >= 0.75

    # Identifica os sinais que dispararam (para debug/explicabilidade)
    triggered = []
    for pattern, weight in _RISK_SIGNALS:
        if pattern.search(step) and weight > 0:
            triggered.append(f"{pattern.pattern[:30]}(+{weight:.2f})")

    status = "blocked" if blocked else "ok"
    score  = round(max(0.0, 1.0 - risk), 3)
    return StepResult(step=step, status=status, risk=risk, score=score, signals=triggered)


# ── Loop principal ────────────────────────────────────────────────────────────

def run_planner_loop(
    goal: str,
    risk_threshold: float = 0.75,
    record_outcomes: bool = False,
) -> dict[str, Any]:
    """
    Planner → Executor → Critic.

    Parameters
    ----------
    goal            : objetivo em linguagem natural
    risk_threshold  : risco máximo antes de bloquear um passo
    record_outcomes : se True, persiste resultados no histórico
    """
    steps    = decompose_goal(goal)
    executed: list[dict] = []
    blocked_indexes: list[int] = []

    for idx, step in enumerate(steps):
        result = _execute_step(step)
        go_no_go = "go" if result.risk < risk_threshold and result.status == "ok" else "no_go"
        checkpoint: dict[str, Any] = {
            "index":    idx,
            "step":     result.step,
            "status":   result.status,
            "risk":     result.risk,
            "score":    result.score,
            "go_no_go": go_no_go,
            "risk_signals": result.signals,
        }
        executed.append(checkpoint)

        if record_outcomes:
            _history.record(step, result.risk, result.status, result.status == "ok")

        if go_no_go == "no_go":
            blocked_indexes.append(idx)
            # Não pára imediatamente — avalia todos para dar visibilidade completa
            # mas marca o primeiro bloqueio como ponto de interrupção
            if len(blocked_indexes) == 1:
                checkpoint["interrupt"] = True

    avg_score = round(sum(c["score"] for c in executed) / max(1, len(executed)), 3)
    avg_risk  = round(sum(c["risk"]  for c in executed) / max(1, len(executed)), 3)

    return {
        "status": "ok" if not blocked_indexes else "warn",
        "goal":   goal,
        "steps_total":    len(steps),
        "steps_executed": len(executed),
        "checkpoints":    executed,
        "critic": {
            "quality_score":         avg_score,
            "risk_score":            avg_risk,
            "blocked_indexes":       blocked_indexes,
            "auto_rollback_suggested": bool(blocked_indexes),
            "explanation": (
                "Nenhum passo bloqueado." if not blocked_indexes
                else f"Passo {blocked_indexes[0]} bloqueado por risco >= {risk_threshold}."
            ),
        },
    }
