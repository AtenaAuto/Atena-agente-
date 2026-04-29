#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — RLHF Engine (corrigido)
Bug original: ON CONFLICT usava EXCLUDED.reward_score que apontava
para o valor do INSERT (1.0 + delta), não para o delta em si.
Agora usa dois parâmetros separados: valor_insert e delta.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("atena.rlhf")

ROOT    = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT / "atena_evolution" / "knowledge" / "knowledge.db")


class RLHFEngine:
    """
    Modelo de Recompensa Local com aprendizado por reforço real.

    reward_score: começa em 1.0, vai de 0.1 (ruim) a 2.0 (ótimo).
    - sucesso: +0.10
    - falha  : -0.20  (penalidade maior para convergência mais rápida)
    """

    REWARD_SUCCESS =  0.10
    REWARD_FAIL    = -0.20
    SCORE_MIN      =  0.10
    SCORE_MAX      =  2.00

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Esquema ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rlhf_preferences (
                    pattern_type  TEXT    PRIMARY KEY,
                    reward_score  REAL    NOT NULL DEFAULT 1.0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    fail_count    INTEGER NOT NULL DEFAULT 0,
                    last_updated  REAL    NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rlhf_history (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts            REAL    NOT NULL,
                    pattern_type  TEXT    NOT NULL,
                    success       INTEGER NOT NULL,
                    fitness       REAL    NOT NULL DEFAULT 0.0,
                    delta         REAL    NOT NULL
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ── API pública ──────────────────────────────────────────────────────────

    def get_reward_multiplier(self, mutation_type: str) -> float:
        """Retorna multiplicador de recompensa [0.1, 2.0]."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT reward_score FROM rlhf_preferences WHERE pattern_type = ?",
                (mutation_type,),
            ).fetchone()
        return float(max(self.SCORE_MIN, min(self.SCORE_MAX, row[0]))) if row else 1.0

    def record_feedback(
        self,
        mutation_type: str,
        success: bool,
        fitness: float = 0.0,
    ) -> float:
        """
        Registra feedback e atualiza reward_score corretamente.
        Retorna o novo reward_score.
        """
        delta = self.REWARD_SUCCESS if success else self.REWARD_FAIL
        ts    = time.time()

        with self._conn() as conn:
            # Garante que a linha existe com score inicial 1.0
            conn.execute("""
                INSERT INTO rlhf_preferences (pattern_type, reward_score, success_count, fail_count, last_updated)
                VALUES (?, 1.0, 0, 0, ?)
                ON CONFLICT(pattern_type) DO NOTHING
            """, (mutation_type, ts))

            # Atualiza usando o delta (não o valor do INSERT)
            conn.execute("""
                UPDATE rlhf_preferences SET
                    reward_score  = MAX(?, MIN(?, reward_score + ?)),
                    success_count = success_count + ?,
                    fail_count    = fail_count    + ?,
                    last_updated  = ?
                WHERE pattern_type = ?
            """, (
                self.SCORE_MIN, self.SCORE_MAX, delta,
                1 if success else 0,
                0 if success else 1,
                ts,
                mutation_type,
            ))

            # Histórico completo
            conn.execute("""
                INSERT INTO rlhf_history (ts, pattern_type, success, fitness, delta)
                VALUES (?, ?, ?, ?, ?)
            """, (ts, mutation_type, int(success), fitness, delta))

            new_score = conn.execute(
                "SELECT reward_score FROM rlhf_preferences WHERE pattern_type = ?",
                (mutation_type,),
            ).fetchone()

        score = float(new_score[0]) if new_score else 1.0 + delta
        logger.info(
            "[RLHF] %s → %s | score=%.3f (delta=%.2f) fitness=%.1f",
            mutation_type,
            "✅ sucesso" if success else "❌ falha",
            score, delta, fitness,
        )
        return score

    def top_mutations(self, n: int = 5) -> list[dict]:
        """Retorna as N mutações com maior reward_score."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT pattern_type, reward_score, success_count, fail_count
                FROM rlhf_preferences
                ORDER BY reward_score DESC
                LIMIT ?
            """, (n,)).fetchall()
        return [
            {"type": r[0], "score": r[1], "success": r[2], "fail": r[3]}
            for r in rows
        ]

    def worst_mutations(self, n: int = 5) -> list[dict]:
        """Retorna as N mutações com menor reward_score."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT pattern_type, reward_score, success_count, fail_count
                FROM rlhf_preferences
                WHERE (success_count + fail_count) > 0
                ORDER BY reward_score ASC
                LIMIT ?
            """, (n,)).fetchall()
        return [
            {"type": r[0], "score": r[1], "success": r[2], "fail": r[3]}
            for r in rows
        ]

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*), SUM(success_count), SUM(fail_count) FROM rlhf_preferences"
            ).fetchone()
        types, successes, fails = total
        return {
            "unique_types":  types    or 0,
            "total_success": successes or 0,
            "total_fail":    fails    or 0,
        }


# Instância global
rlhf = RLHFEngine()
