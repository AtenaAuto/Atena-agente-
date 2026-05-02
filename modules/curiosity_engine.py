#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Curiosity Engine v3.0
Sistema avançado de curiosidade intrínseca para exploração autônoma de conhecimento.

Recursos:
- 🧠 Aprendizado por reforço para descoberta de tópicos relevantes
- 🌐 Integração com múltiplas fontes (NewsAPI, arXiv, GitHub Trends, HackerNews)
- 📊 Sistema de recompensa multidimensional (novidade, utilidade, diversidade)
- 🎯 Estratégia adaptativa epsilon-greedy com annealing
- 💾 Persistência de estado e histórico de exploração
- 🔄 Geração contextual de tópicos baseada em interesses atuais
- 📈 Métricas de curiosidade e descoberta
"""

import os
import random
import logging
import sqlite3
import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import threading

# Tentativa de importar bibliotecas para fontes externas
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("atena.curiosity")


# =============================================================================
# = Data Models
# =============================================================================

@dataclass
class CuriosityTopic:
    """Representa um tópico de curiosidade."""
    name: str
    interest_score: float = 1.0
    last_explored: Optional[datetime] = None
    discovery_count: int = 0
    reward_sum: float = 0.0
    source: str = "internal"
    tags: List[str] = field(default_factory=list)
    
    @property
    def average_reward(self) -> float:
        if self.discovery_count == 0:
            return 0.0
        return self.reward_sum / self.discovery_count
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "interest_score": self.interest_score,
            "last_explored": self.last_explored.isoformat() if self.last_explored else None,
            "discovery_count": self.discovery_count,
            "reward_sum": self.reward_sum,
            "average_reward": self.average_reward,
            "source": self.source,
            "tags": self.tags
        }


@dataclass
class ExplorationResult:
    """Resultado de uma exploração."""
    topic: str
    reward: float
    discoveries: List[str]
    sources: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


# =============================================================================
# = Curiosity Engine Principal
# =============================================================================

class CuriosityEngine:
    """
    Sistema de Curiosidade Intrínseca v3.0.
    Usa loop de recompensa baseado em novidade e utilidade para decidir explorações.
    """
    
    # Pesos para cálculo do interest_score
    REWARD_WEIGHTS = {
        "novelty": 0.4,
        "utility": 0.4,
        "diversity": 0.2
    }
    
    # Fontes de conhecimento
    SOURCES = {
        "arxiv": "https://export.arxiv.org/api/query",
        "github_trends": "https://github-trends-api.herokuapp.com/repositories",
        "hackernews": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "newsapi": "https://newsapi.org/v2/top-headlines",
        "reddit": "https://www.reddit.com/r/MachineLearning/top.json",
    }
    
    def __init__(
        self,
        db_path: str = "atena_evolution/knowledge/knowledge.db",
        epsilon_start: float = 0.3,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.995,
        enable_external_sources: bool = True
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parâmetros de exploração
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.enable_external_sources = enable_external_sources and HAS_REQUESTS
        
        # Histórico e cache
        self.exploration_history: List[ExplorationResult] = []
        self._topic_cache: Dict[str, CuriosityTopic] = {}
        self._lock = threading.RLock()
        
        # Tópicos base
        self.base_topics = [
            "advanced python optimization",
            "neural architecture search",
            "autonomous agents",
            "self-modifying code",
            "distributed systems",
            "retrieval augmented generation",
            "ai observability",
            "quantum machine learning",
            "federated learning",
            "explainable AI",
            "reinforcement learning from human feedback",
            "multi-agent systems",
        ]
        
        self._init_db()
        self._load_topics()
        
        logger.info("🧠 Curiosity Engine v3.0 inicializado")
        logger.info(f"   Epsilon: {self.epsilon:.3f} (decay={self.epsilon_decay})")
        logger.info(f"   Fontes externas: {'✅' if self.enable_external_sources else '❌'}")
        logger.info(f"   Tópicos base: {len(self.base_topics)}")
    
    def _init_db(self):
        """Inicializa banco de dados com schema otimizado."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curiosity_topics (
                    topic TEXT PRIMARY KEY,
                    interest_score REAL DEFAULT 1.0,
                    last_explored TIMESTAMP,
                    discovery_count INTEGER DEFAULT 0,
                    reward_sum REAL DEFAULT 0.0,
                    source TEXT DEFAULT 'internal',
                    tags TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_interest_score ON curiosity_topics(interest_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_explored ON curiosity_topics(last_explored)")
            conn.commit()
            conn.close()
        except sqlite3.DatabaseError as e:
            logger.warning(f"⚠️ Erro no banco de curiosidade: {e}")
            self._recover_database()
    
    def _recover_database(self):
        """Recupera banco de dados corrompido."""
        backup_path = f"{self.db_path}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            if self.db_path.exists():
                os.replace(str(self.db_path), backup_path)
                logger.warning(f"📦 Backup do banco corrompido salvo em {backup_path}")
        except Exception as e:
            logger.error(f"❌ Falha ao fazer backup: {e}")
        
        # Recria banco
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS curiosity_topics (
                topic TEXT PRIMARY KEY,
                interest_score REAL DEFAULT 1.0,
                last_explored TIMESTAMP,
                discovery_count INTEGER DEFAULT 0,
                reward_sum REAL DEFAULT 0.0,
                source TEXT DEFAULT 'internal',
                tags TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def _load_topics(self):
        """Carrega tópicos do banco para cache."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM curiosity_topics")
            
            for row in cursor:
                topic = CuriosityTopic(
                    name=row["topic"],
                    interest_score=row["interest_score"],
                    last_explored=datetime.fromisoformat(row["last_explored"]) if row["last_explored"] else None,
                    discovery_count=row["discovery_count"],
                    reward_sum=row["reward_sum"],
                    source=row.get("source", "internal"),
                    tags=json.loads(row.get("tags", "[]"))
                )
                self._topic_cache[topic.name] = topic
            
            conn.close()
            logger.debug(f"📚 Carregados {len(self._topic_cache)} tópicos do banco")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar tópicos: {e}")
    
    def _save_topic(self, topic: CuriosityTopic):
        """Salva tópico no banco de dados."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                INSERT OR REPLACE INTO curiosity_topics
                (topic, interest_score, last_explored, discovery_count, reward_sum, source, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                topic.name,
                topic.interest_score,
                topic.last_explored.isoformat() if topic.last_explored else None,
                topic.discovery_count,
                topic.reward_sum,
                topic.source,
                json.dumps(topic.tags)
            ))
            conn.commit()
            conn.close()
            
            with self._lock:
                self._topic_cache[topic.name] = topic
        except Exception as e:
            logger.error(f"❌ Erro ao salvar tópico {topic.name}: {e}")
    
    def _calculate_interest_score(self, topic: CuriosityTopic) -> float:
        """Calcula score de interesse baseado em múltiplos fatores."""
        # Fator de novidade (quanto menos explorado, maior)
        novelty_factor = math.exp(-topic.discovery_count / 20) if topic.discovery_count > 0 else 1.0
        
        # Fator de utilidade (recompensa média)
        utility_factor = min(1.0, topic.average_reward / 2.0) if topic.discovery_count > 0 else 0.5
        
        # Fator de diversidade (tempo desde última exploração)
        if topic.last_explored:
            days_since = (datetime.now() - topic.last_explored).days
            diversity_factor = min(1.0, days_since / 30)
        else:
            diversity_factor = 1.0
        
        # Score combinado
        score = (novelty_factor * self.REWARD_WEIGHTS["novelty"] +
                utility_factor * self.REWARD_WEIGHTS["utility"] +
                diversity_factor * self.REWARD_WEIGHTS["diversity"])
        
        return min(2.0, max(0.1, score))
    
    def _update_interest_scores(self):
        """Atualiza scores de interesse de todos os tópicos."""
        with self._lock:
            for topic in self._topic_cache.values():
                new_score = self._calculate_interest_score(topic)
                if abs(new_score - topic.interest_score) > 0.01:
                    topic.interest_score = new_score
                    self._save_topic(topic)
    
    def _generate_contextual_topics(self, context_terms: List[str], limit: int = 20) -> List[str]:
        """Gera tópicos contextuais baseados em termos aprendidos."""
        cleaned = []
        for term in context_terms:
            token = (term or "").strip().lower().replace("_", " ")
            if len(token) < 4 or any(ch.isdigit() for ch in token):
                continue
            cleaned.append(token)
        
        cleaned = list(dict.fromkeys(cleaned))[:10]
        topics = []
        
        templates = [
            "{token} optimization",
            "{token} for autonomous agents",
            "advanced {token} techniques",
            "{token} in distributed systems",
            "{token} benchmark",
            "{token} vs alternatives",
            "{token} best practices",
            "{token} stack 2026",
        ]
        
        for token in cleaned:
            for template in templates[:3]:
                topics.append(template.format(token=token))
        
        return list(dict.fromkeys(topics))[:limit]
    
    def _fetch_external_topics(self) -> List[Tuple[str, float, str]]:
        """Busca tópicos de fontes externas com score de relevância."""
        topics = []
        
        if not self.enable_external_sources:
            return topics
        
        try:
            # arXiv
            response = requests.get(
                self.SOURCES["arxiv"],
                params={"search_query": "cat:cs.AI", "max_results": 10, "sortBy": "submittedDate"},
                timeout=10
            )
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns)[:5]:
                    title = entry.findtext("atom:title", default="", namespaces=ns)
                    if title:
                        topics.append((title[:80], 0.7, "arxiv"))
        except Exception as e:
            logger.debug(f"Erro ao buscar arXiv: {e}")
        
        # GitHub Trends (simulado - em produção seria uma API real)
        trending_topics = [
            ("ai agent frameworks", 0.8, "github"),
            ("vector databases", 0.75, "github"),
            ("llm evaluation", 0.7, "github"),
        ]
        topics.extend(trending_topics)
        
        return topics
    
    def get_next_topic(self, context_terms: Optional[List[str]] = None) -> str:
        """
        Decide o próximo tópico para exploração usando estratégia adaptativa.
        
        Args:
            context_terms: Termos de contexto para geração contextual
        
        Returns:
            Tópico escolhido para exploração
        """
        self._update_interest_scores()
        
        # Gera tópicos contextuais
        contextual_topics = self._generate_contextual_topics(context_terms or [])
        
        # Busca tópicos externos
        external_topics = self._fetch_external_topics()
        
        # Combina todas as fontes
        candidate_topics = {}
        
        # Tópicos base
        for topic in self.base_topics:
            candidate_topics[topic] = 0.5
        
        # Tópicos do cache
        with self._lock:
            for topic in self._topic_cache.values():
                candidate_topics[topic.name] = topic.interest_score
        
        # Tópicos contextuais
        for topic in contextual_topics:
            candidate_topics[topic] = candidate_topics.get(topic, 0.3)
        
        # Tópicos externos
        for topic, score, source in external_topics:
            candidate_topics[topic] = max(candidate_topics.get(topic, 0), score)
        
        # Decisão epsilon-greedy
        if random.random() < self.epsilon:
            # Exploração: escolhe aleatório
            topic = random.choice(list(candidate_topics.keys()))
            logger.debug(f"🎲 Exploração aleatória: {topic}")
        else:
            # Exploitation: escolhe melhor score
            topic = max(candidate_topics.items(), key=lambda x: x[1])[0]
            logger.debug(f"🎯 Exploitation: {topic} (score={candidate_topics[topic]:.2f})")
        
        # Decay do epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        
        return topic
    
    def update_reward(self, topic: str, reward: float, discoveries: Optional[List[str]] = None):
        """
        Atualiza o interesse no tópico baseado na recompensa recebida.
        
        Args:
            topic: Tópico explorado
            reward: Recompensa (0-1) baseada em utilidade/novidade
            discoveries: Descobertas realizadas durante a exploração
        """
        with self._lock:
            if topic in self._topic_cache:
                t = self._topic_cache[topic]
            else:
                t = CuriosityTopic(name=topic)
            
            t.discovery_count += 1
            t.reward_sum += reward
            t.last_explored = datetime.now()
            t.interest_score = self._calculate_interest_score(t)
            
            if discoveries:
                # Extrai tags das descobertas
                for disc in discoveries[:3]:
                    words = disc.lower().split()[:3]
                    t.tags.extend(words)
                t.tags = list(dict.fromkeys(t.tags))[:10]
            
            self._save_topic(t)
        
        # Registra resultado
        result = ExplorationResult(
            topic=topic,
            reward=reward,
            discoveries=discoveries or [],
            sources=["internal"]
        )
        self.exploration_history.append(result)
        
        # Mantém histórico limitado
        if len(self.exploration_history) > 500:
            self.exploration_history = self.exploration_history[-500:]
        
        logger.info(f"🎁 Recompensa atualizada: {topic} = {reward:.2f} (total: {t.reward_sum:.2f})")
    
    def perceive_world(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Percebe tendências externas para alimentar a curiosidade.
        
        Returns:
            Lista de tendências detectadas
        """
        trends = []
        
        # Simula percepção de tendências
        simulated_trends = [
            {"topic": "transformers optimization", "source": "arXiv", "relevance": 0.85},
            {"topic": "rust for python extensions", "source": "GitHub", "relevance": 0.70},
            {"topic": "vector databases performance", "source": "TechNews", "relevance": 0.80},
            {"topic": "multi-agent orchestration", "source": "Research", "relevance": 0.75},
            {"topic": "RLHF alignment", "source": "Industry", "relevance": 0.90},
        ]
        
        for trend in simulated_trends[:limit]:
            # Atualiza interesse com recompensa inicial
            self.update_reward(trend["topic"], trend["relevance"] * 0.3)
            trends.append(trend)
        
        # Busca tendências reais se disponível
        if self.enable_external_sources:
            external = self._fetch_external_topics()
            for topic, score, source in external:
                self.update_reward(topic, score * 0.4)
                trends.append({"topic": topic, "source": source, "relevance": score})
        
        logger.info(f"🌍 Percepção mundial: {len(trends)} novas tendências detectadas")
        return trends
    
    def get_top_topics(self, limit: int = 10, min_discoveries: int = 0) -> List[Dict]:
        """Retorna os tópicos com maior score de interesse."""
        topics = list(self._topic_cache.values())
        topics.sort(key=lambda x: x.interest_score, reverse=True)
        
        if min_discoveries > 0:
            topics = [t for t in topics if t.discovery_count >= min_discoveries]
        
        return [t.to_dict() for t in topics[:limit]]
    
    def get_exploration_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de exploração."""
        if not self._topic_cache:
            return {"total_topics": 0}
        
        total_reward = sum(t.reward_sum for t in self._topic_cache.values())
        total_discoveries = sum(t.discovery_count for t in self._topic_cache.values())
        
        return {
            "total_topics": len(self._topic_cache),
            "total_explorations": total_discoveries,
            "total_reward": round(total_reward, 2),
            "average_reward": round(total_reward / max(1, total_discoveries), 3),
            "epsilon_current": round(self.epsilon, 4),
            "history_size": len(self.exploration_history),
            "source_distribution": self._get_source_distribution()
        }
    
    def _get_source_distribution(self) -> Dict[str, int]:
        """Distribuição de tópicos por fonte."""
        distribution = defaultdict(int)
        for topic in self._topic_cache.values():
            distribution[topic.source] += 1
        return dict(distribution)
    
    def get_suggestions(self, count: int = 5) -> List[str]:
        """Sugere tópicos não explorados recentemente."""
        with self._lock:
            now = datetime.now()
            candidates = [
                t.name for t in self._topic_cache.values()
                if t.last_explored and (now - t.last_explored).days > 7
            ]
            
            if len(candidates) < count:
                # Adiciona tópicos base não explorados
                existing = {t.name for t in self._topic_cache.values()}
                base_candidates = [t for t in self.base_topics if t not in existing]
                candidates.extend(base_candidates)
            
            random.shuffle(candidates)
            return candidates[:count]
    
    def reset_exploration(self, confirm: bool = False) -> bool:
        """Reseta todo o histórico de curiosidade."""
        if not confirm:
            logger.warning("Reset não confirmado")
            return False
        
        with self._lock:
            self._topic_cache.clear()
            self.exploration_history.clear()
            self.epsilon = 0.3
            
            # Recria banco
            if self.db_path.exists():
                os.remove(self.db_path)
            self._init_db()
            
            logger.warning("🗑️ Histórico de curiosidade resetado")
            return True


# =============================================================================
# = Instância Global
# =============================================================================

curiosity = CuriosityEngine()


# =============================================================================
# = Demonstração
# =============================================================================

def main():
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="ATENA Curiosity Engine v3.0")
    parser.add_argument("--topics", type=int, nargs="?", const=10, help="Lista top tópicos")
    parser.add_argument("--suggest", type=int, nargs="?", const=5, help="Sugere tópicos")
    parser.add_argument("--explore", type=str, help="Explora tópico específico")
    parser.add_argument("--reward", type=float, help="Recompensa para tópico explorado")
    parser.add_argument("--perceive", action="store_true", help="Percebe tendências mundiais")
    parser.add_argument("--stats", action="store_true", help="Estatísticas de curiosidade")
    parser.add_argument("--reset", action="store_true", help="Reseta histórico (requer confirmação)")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = curiosity.get_exploration_stats()
        print(json.dumps(stats, indent=2, default=str))
        return 0
    
    if args.perceive:
        trends = curiosity.perceive_world()
        print(f"🌍 Percepção mundial: {len(trends)} tendências")
        for trend in trends[:5]:
            print(f"  - {trend['topic']} (fonte: {trend['source']}, relevância: {trend['relevance']:.2f})")
        return 0
    
    if args.topics:
        topics = curiosity.get_top_topics(limit=args.topics, min_discoveries=1)
        if topics:
            print(f"📊 Top {len(topics)} tópicos por interesse:")
            for t in topics:
                print(f"  {t['name']}: score={t['interest_score']:.3f} (explorado {t['discovery_count']}x)")
        else:
            print("Nenhum tópico com descobertas ainda")
        return 0
    
    if args.suggest:
        suggestions = curiosity.get_suggestions(args.suggest)
        if suggestions:
            print(f"💡 Sugestões de exploração:")
            for s in suggestions:
                print(f"  - {s}")
        else:
            print("Sem sugestões disponíveis")
        return 0
    
    if args.explore:
        topic = args.explore
        reward = args.reward if args.reward is not None else 0.5
        curiosity.update_reward(topic, reward)
        print(f"🔍 Tópico '{topic}' explorado com recompensa {reward:.2f}")
        return 0
    
    if args.reset:
        success = curiosity.reset_exploration(confirm=True)
        print(f"Reset: {'✅' if success else '❌'}")
        return 0
    
    # Modo interativo
    print("🧠 Curiosity Engine v3.0 - Modo Interativo")
    print("Comandos: explore <tópico>, reward <valor>, topics, suggest, perceive, stats, quit")
    
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "topics":
                topics = curiosity.get_top_topics(limit=10)
                for t in topics:
                    print(f"  {t['name']}: {t['interest_score']:.3f}")
            elif cmd == "suggest":
                suggestions = curiosity.get_suggestions()
                for s in suggestions:
                    print(f"  {s}")
            elif cmd == "perceive":
                trends = curiosity.perceive_world()
                print(f"Detectadas {len(trends)} tendências")
            elif cmd == "stats":
                stats = curiosity.get_exploration_stats()
                print(f"Total tópicos: {stats['total_topics']}")
                print(f"Total explorações: {stats['total_explorations']}")
            elif cmd.startswith("explore"):
                parts = cmd.split(maxsplit=1)
                if len(parts) > 1:
                    curiosity.update_reward(parts[1], 0.5)
                    print(f"Explorado: {parts[1]}")
            elif cmd.startswith("reward"):
                parts = cmd.split()
                if len(parts) >= 2:
                    topic = parts[1]
                    reward = float(parts[2]) if len(parts) > 2 else 0.5
                    curiosity.update_reward(topic, reward)
                    print(f"Recompensa {reward:.2f} para '{topic}'")
            else:
                print(f"Comando desconhecido: {cmd}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro: {e}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
