import os
import random
import logging
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("atena.curiosity")

class CuriosityEngine:
    """
    Hacker Recon 2.0: Sistema de Curiosidade Intrínseca.
    Usa um loop de recompensa para decidir quais tópicos explorar
    baseado na novidade e utilidade para o DNA atual.
    """
    def __init__(self, db_path: str = "atena_evolution/knowledge/knowledge.db"):
        self.db_path = db_path
        self._init_db()
        self.exploration_history = []
        self.base_topics = [
            "advanced python optimization",
            "neural architecture search",
            "autonomous agents",
            "self-modifying code",
            "distributed systems",
            "retrieval augmented generation",
            "ai observability",
        ]
        
    def _init_db(self):
        """Garante que as tabelas de curiosidade existam."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curiosity_topics (
                    topic TEXT PRIMARY KEY,
                    interest_score REAL DEFAULT 1.0,
                    last_explored DATETIME,
                    discovery_count INTEGER DEFAULT 0,
                    reward_sum REAL DEFAULT 0.0
                )
            """)
            conn.commit()
            conn.close()
        except sqlite3.DatabaseError:
            # Recuperação automática quando o arquivo de estado estiver corrompido.
            try:
                if os.path.exists(self.db_path):
                    backup = f"{self.db_path}.corrupted"
                    if os.path.exists(backup):
                        os.remove(backup)
                    os.replace(self.db_path, backup)
                    logger.warning("[Curiosity] Banco corrompido detectado; backup salvo em %s", backup)
            except Exception as exc:
                logger.warning("[Curiosity] Falha ao fazer backup do banco corrompido: %s", exc)

            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curiosity_topics (
                    topic TEXT PRIMARY KEY,
                    interest_score REAL DEFAULT 1.0,
                    last_explored DATETIME,
                    discovery_count INTEGER DEFAULT 0,
                    reward_sum REAL DEFAULT 0.0
                )
            """)
            conn.commit()
            conn.close()

    def get_next_topic(self, context_terms: Optional[List[str]] = None) -> str:
        """Decide o próximo tópico para exploração usando estratégia Epsilon-Greedy."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        contextual_topics = self._generate_contextual_topics(context_terms or [])
        candidate_topics = list(dict.fromkeys(self.base_topics + contextual_topics))
        
        # 20% exploração aleatória, 80% exploração baseada em interesse
        if random.random() < 0.2:
            topic = random.choice(candidate_topics)
        else:
            cursor.execute("SELECT topic FROM curiosity_topics ORDER BY interest_score DESC LIMIT 5")
            results = cursor.fetchall()
            if not results:
                topic = "artificial general intelligence"
            else:
                learned = [r[0] for r in results]
                topic_pool = list(dict.fromkeys(learned + candidate_topics))
                topic = random.choice(topic_pool)
        
        conn.close()
        return topic

    def _generate_contextual_topics(self, context_terms: List[str]) -> List[str]:
        """Gera tópicos novos a partir de termos aprendidos para guiar pesquisa incremental."""
        cleaned = []
        for term in context_terms:
            token = (term or "").strip().lower().replace("_", " ")
            if len(token) < 4:
                continue
            if any(ch.isdigit() for ch in token):
                continue
            cleaned.append(token)
        cleaned = list(dict.fromkeys(cleaned))[:6]
        topics: List[str] = []
        for token in cleaned:
            topics.extend(
                [
                    f"{token} optimization",
                    f"{token} for autonomous agents",
                    f"{token} in distributed systems",
                ]
            )
        return list(dict.fromkeys(topics))[:12]

    def update_reward(self, topic: str, reward: float):
        """Atualiza o interesse no tópico baseado na recompensa recebida (ex: novas funções úteis)."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO curiosity_topics (topic, interest_score, last_explored, discovery_count, reward_sum)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(topic) DO UPDATE SET
                reward_sum = reward_sum + EXCLUDED.reward_sum,
                discovery_count = discovery_count + 1,
                interest_score = (reward_sum + EXCLUDED.reward_sum) / (discovery_count + 1),
                last_explored = EXCLUDED.last_explored
        """, (topic, reward, datetime.now().isoformat(), reward))
        conn.commit()
        conn.close()
        logger.info(f"[Curiosity] Tópico '{topic}' atualizado com recompensa {reward:.2f}")

    def perceive_world(self) -> List[Dict[str, Any]]:
        """Simula a percepção de novas tendências para alimentar a curiosidade."""
        # Stub para integração com NewsAPI ou GitHub Trends
        trends = [
            {"topic": "transformers optimization", "source": "arXiv"},
            {"topic": "rust for python extensions", "source": "GitHub"},
            {"topic": "vector databases performance", "source": "TechNews"}
        ]
        for trend in trends:
            self.update_reward(trend['topic'], 0.5) # Interesse inicial
        return trends

# Instância global
curiosity = CuriosityEngine()
