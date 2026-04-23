import os
import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("atena.rlhf")

class RLHFEngine:
    """
    RLHF Interno: Modelo de Recompensa Local.
    Permite que a ATENA aprenda preferências de codificação (estilo, segurança, elegância)
    através de um histórico de escolhas validadas.
    """
    def __init__(self, db_path: str = "atena_evolution/knowledge/knowledge.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Garante que as tabelas de RLHF existam."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rlhf_preferences (
                pattern_type TEXT PRIMARY KEY,
                reward_score REAL DEFAULT 1.0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                last_updated DATETIME
            )
        """)
        conn.commit()
        conn.close()

    def get_reward_multiplier(self, mutation_type: str) -> float:
        """Retorna o multiplicador de recompensa baseado no histórico de preferências."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT reward_score FROM rlhf_preferences WHERE pattern_type = ?", (mutation_type,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return max(0.1, min(2.0, result[0]))
        return 1.0

    def record_feedback(self, mutation_type: str, success: bool):
        """Registra o feedback (sucesso ou falha) para um tipo de mutação."""
        reward_delta = 0.1 if success else -0.2
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO rlhf_preferences (pattern_type, reward_score, success_count, fail_count, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(pattern_type) DO UPDATE SET
                reward_score = MAX(0.1, MIN(2.0, reward_score + EXCLUDED.reward_score)),
                success_count = success_count + (CASE WHEN ? THEN 1 ELSE 0 END),
                fail_count = fail_count + (CASE WHEN ? THEN 0 ELSE 1 END),
                last_updated = EXCLUDED.last_updated
        """, (mutation_type, 1.0 + reward_delta, 1 if success else 0, 0 if success else 1, 
              datetime.now().isoformat(), success, success))
        conn.commit()
        conn.close()
        logger.info(f"[RLHF] Feedback registrado para '{mutation_type}': {'Sucesso' if success else 'Falha'}")

# Instância global
rlhf = RLHFEngine()
