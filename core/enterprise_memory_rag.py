#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Corporate Memory & RAG Engine v3.0 - Memória Corporativa com Governança Avançada
Sistema completo de memória organizacional com RAG, governança e auditoria.

Recursos:
- 🧠 RAG (Retrieval-Augmented Generation) com múltiplas estratégias
- 🛡️ Governança por classificação (niveis de acesso, retenção)
- 📊 Métricas de uso e performance
- 🔍 Busca semântica com embeddings e BM25
- 📝 Auditoria completa de acesso e modificações
- 🔄 Rotação e expiração automática de memórias
- 🔒 Redação automática de segredos
- 🌐 Suporte a múltiplos tenants
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import threading

# Tentativa de importar bibliotecas avançadas
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False

logger = logging.getLogger(__name__)


# =============================================================================
# Constantes e Configurações
# =============================================================================

class ClassificationLevel(Enum):
    """Níveis de classificação para governança."""
    PUBLIC = "public"           # Acesso público
    INTERNAL = "internal"       # Uso interno
    CONFIDENTIAL = "confidential"  # Confidencial
    RESTRICTED = "restricted"   # Altamente restrito
    SECRET = "secret"           # Secreto


class AccessLevel(Enum):
    """Níveis de acesso para diferentes roles."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    AUDIT = "audit"


# Padrões de segredos para redação
SECRET_PATTERNS = [
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "GITHUB_TOKEN"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "GITHUB_PAT"),
    (re.compile(r"sk-[A-Za-z0-9]{30,}"), "OPENAI_KEY"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{30,}"), "ANTHROPIC_KEY"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS_ACCESS_KEY"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "GOOGLE_API_KEY"),
    (re.compile(r"xox[bap]-[0-9A-Za-z\-]{30,}"), "SLACK_TOKEN"),
    (re.compile(r"-----BEGIN.*PRIVATE KEY-----"), "PRIVATE_KEY"),
]


@dataclass
class MemoryEntry:
    """Entrada de memória estruturada."""
    id: Optional[int]
    tenant_id: str
    content: str
    citation: str
    classification: str
    tags: List[str]
    created_at: str
    updated_at: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    source: Optional[str] = None
    embedding: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "content": self.content[:500],
            "citation": self.citation,
            "classification": self.classification,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "source": self.source,
            "metadata": self.metadata
        }


@dataclass
class QueryResult:
    """Resultado de consulta RAG."""
    content: str
    citation: str
    classification: str
    tags: List[str]
    score: float
    semantic_score: float
    bm25_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content[:500],
            "citation": self.citation,
            "classification": self.classification,
            "tags": self.tags,
            "score": round(self.score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "bm25_score": round(self.bm25_score, 4)
        }


# =============================================================================
# Utilitários
# =============================================================================

def redact_secrets(text: str) -> str:
    """Redige segredos no texto."""
    redacted = text
    for pattern, label in SECRET_PATTERNS:
        redacted = pattern.sub(f"[{label}_REDACTED]", redacted)
    return redacted


def tokenize(text: str) -> Set[str]:
    """Tokeniza texto para BM25."""
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 2 and not t.isdigit()}


def compute_tfidf(tokens: Set[str], all_tokens: List[Set[str]]) -> Dict[str, float]:
    """Calcula TF-IDF para tokens."""
    doc_freq = defaultdict(int)
    for doc_tokens in all_tokens:
        for token in set(doc_tokens):
            doc_freq[token] += 1
    
    n_docs = len(all_tokens)
    tfidf = {}
    for token in tokens:
        tf = 1.0  # Term frequency simplificada
        idf = math.log((n_docs + 1) / (doc_freq.get(token, 1) + 1)) + 1
        tfidf[token] = tf * idf
    
    return tfidf


# =============================================================================
# BM25 Search Engine
# =============================================================================

class BM25:
    """Implementação BM25 para busca de relevância."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[str] = []
        self.doc_tokens: List[Set[str]] = []
        self.avgdl: float = 0.0
    
    def index(self, corpus: List[str]):
        """Indexa corpus para BM25."""
        self.corpus = corpus
        self.doc_tokens = [tokenize(doc) for doc in corpus]
        self.avgdl = sum(len(tokens) for tokens in self.doc_tokens) / max(1, len(self.doc_tokens))
    
    def score(self, query: str, doc_idx: int) -> float:
        """Calcula score BM25 para um documento."""
        query_tokens = tokenize(query)
        doc_tokens = self.doc_tokens[doc_idx]
        doc_len = len(doc_tokens)
        
        score = 0.0
        for token in query_tokens:
            tf = doc_tokens.count(token)
            if tf == 0:
                continue
            
            idf = math.log((len(self.corpus) - self.doc_freq(token) + 0.5) / (self.doc_freq(token) + 0.5) + 1)
            tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))
            score += idf * tf_norm
        
        return score
    
    def doc_freq(self, token: str) -> int:
        """Frequência de documentos contendo o token."""
        return sum(1 for tokens in self.doc_tokens if token in tokens)
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Busca por BM25."""
        scores = [(idx, self.score(query, idx)) for idx in range(len(self.corpus))]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# =============================================================================
# Tenant Memory RAG Avançado
# =============================================================================

class TenantMemoryRAG:
    """
    Sistema de memória corporativa com RAG e governança.
    Suporta busca semântica, BM25, classificações e auditoria.
    """
    
    def __init__(
        self,
        db_path: str | Path,
        embedding_model: Optional[str] = "all-MiniLM-L6-v2",
        enable_embeddings: bool = True
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.enable_embeddings = enable_embeddings and HAS_EMBEDDINGS
        self.embedding_model = None
        self.bm25_indexes: Dict[str, BM25] = {}
        self._cache: Dict[str, List[QueryResult]] = {}
        self._lock = threading.RLock()
        
        if self.enable_embeddings:
            try:
                self.embedding_model = SentenceTransformer(embedding_model)
                logger.info(f"Modelo de embeddings carregado: {embedding_model}")
            except Exception as e:
                logger.warning(f"Falha ao carregar modelo de embeddings: {e}")
                self.enable_embeddings = False
        
        self._init_db()
        self._load_bm25_indexes()
    
    def _init_db(self) -> None:
        """Inicializa banco de dados com tabelas otimizadas."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citation TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT,
                    source TEXT,
                    embedding BLOB,
                    metadata_json TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_tenant_class ON memory(tenant_id, classification);
                CREATE INDEX IF NOT EXISTS idx_created_at ON memory(created_at);
                CREATE INDEX IF NOT EXISTS idx_access_count ON memory(access_count DESC);
                CREATE INDEX IF NOT EXISTS idx_tags ON memory(tags_json);
                
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    memory_id INTEGER,
                    user_id TEXT,
                    timestamp TEXT NOT NULL,
                    details_json TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log(tenant_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
            """)
            conn.commit()
    
    def _connect(self) -> sqlite3.Connection:
        """Retorna conexão com o banco."""
        return sqlite3.connect(str(self.db_path))
    
    def _log_audit(
        self,
        tenant_id: str,
        action: str,
        memory_id: Optional[int] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> None:
        """Registra ação no log de auditoria."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (tenant_id, action, memory_id, user_id, timestamp, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    action,
                    memory_id,
                    user_id or "system",
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(details or {})
                )
            )
            conn.commit()
    
    def _generate_embedding(self, text: str) -> Optional[bytes]:
        """Gera embedding para texto."""
        if not self.enable_embeddings or not self.embedding_model:
            return None
        try:
            embedding = self.embedding_model.encode(text[:1000]).astype(np.float32)
            return embedding.tobytes()
        except Exception as e:
            logger.debug(f"Erro ao gerar embedding: {e}")
            return None
    
    def _compute_cosine_similarity(self, emb1: bytes, emb2: bytes) -> float:
        """Calcula similaridade de cosseno entre embeddings."""
        if not HAS_NUMPY:
            return 0.0
        try:
            a = np.frombuffer(emb1, dtype=np.float32)
            b = np.frombuffer(emb2, dtype=np.float32)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        except Exception:
            return 0.0
    
    def _load_bm25_indexes(self) -> None:
        """Carrega índices BM25 para todos os tenants."""
        with self._connect() as conn:
            tenants = conn.execute("SELECT DISTINCT tenant_id FROM memory").fetchall()
            for (tenant_id,) in tenants:
                rows = conn.execute(
                    "SELECT content FROM memory WHERE tenant_id=?",
                    (tenant_id,)
                ).fetchall()
                if rows:
                    bm25 = BM25()
                    bm25.index([r[0] for r in rows])
                    self.bm25_indexes[tenant_id] = bm25
    
    def _rebuild_bm25_index(self, tenant_id: str) -> None:
        """Reconstrói índice BM25 para um tenant."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT content FROM memory WHERE tenant_id=?",
                (tenant_id,)
            ).fetchall()
            if rows:
                bm25 = BM25()
                bm25.index([r[0] for r in rows])
                self.bm25_indexes[tenant_id] = bm25
    
    def upsert(
        self,
        tenant_id: str,
        content: str,
        citation: str,
        classification: str = "internal",
        tags: List[str] | None = None,
        source: Optional[str] = None,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Insere ou atualiza entrada de memória.
        
        Args:
            tenant_id: Identificador do tenant
            content: Conteúdo da memória
            citation: Fonte/citação
            classification: Nível de classificação
            tags: Tags para categorização
            source: Fonte original
            metadata: Metadados adicionais
            user_id: ID do usuário (para auditoria)
        """
        now = datetime.now(timezone.utc).isoformat()
        tags = tags or []
        metadata = metadata or {}
        
        # Redige segredos
        content_redacted = redact_secrets(content)
        citation_redacted = redact_secrets(citation)
        
        # Gera embedding
        embedding = self._generate_embedding(content_redacted)
        
        with self._connect() as conn:
            # Verifica duplicata por content hash
            content_hash = hashlib.md5(content_redacted.encode()).hexdigest()
            existing = conn.execute(
                "SELECT id FROM memory WHERE tenant_id=? AND content_hash=?",
                (tenant_id, content_hash)
            ).fetchone() if 'content_hash' in [c[1] for c in conn.execute("PRAGMA table_info(memory)").fetchall()] else None
            
            # Adiciona coluna content_hash se não existir
            try:
                conn.execute("ALTER TABLE memory ADD COLUMN content_hash TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON memory(content_hash)")
            except sqlite3.OperationalError:
                pass
            
            if existing:
                # Atualiza existente
                conn.execute(
                    """
                    UPDATE memory
                    SET content=?, citation=?, classification=?, tags_json=?,
                        updated_at=?, source=?, metadata_json=?, embedding=?
                    WHERE id=?
                    """,
                    (
                        content_redacted, citation_redacted, classification,
                        json.dumps(tags), now, source, json.dumps(metadata),
                        embedding, existing[0]
                    )
                )
                memory_id = existing[0]
                action = "update"
            else:
                # Insere novo
                result = conn.execute(
                    """
                    INSERT INTO memory
                    (tenant_id, content, citation, classification, tags_json,
                     created_at, updated_at, source, metadata_json, embedding, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id, content_redacted, citation_redacted, classification,
                        json.dumps(tags), now, now, source, json.dumps(metadata),
                        embedding, content_hash
                    )
                )
                memory_id = result.lastrowid
                action = "insert"
            
            conn.commit()
        
        # Reconstrói índice BM25
        self._rebuild_bm25_index(tenant_id)
        
        # Limpa cache
        with self._lock:
            self._cache.pop(tenant_id, None)
        
        # Log de auditoria
        self._log_audit(tenant_id, action, memory_id, user_id, {
            "classification": classification,
            "tags": tags,
            "source": source
        })
        
        return {
            "status": "ok",
            "action": action,
            "memory_id": memory_id,
            "tenant_id": tenant_id,
            "classification": classification,
            "created_at": now if action == "insert" else None,
            "updated_at": now,
            "citation": citation_redacted[:200]
        }
    
    def query(
        self,
        tenant_id: str,
        question: str,
        top_k: int = 5,
        classification: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_score: float = 0.1,
        use_cache: bool = True,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consulta memórias usando RAG (BM25 + semantic search).
        
        Args:
            tenant_id: Identificador do tenant
            question: Pergunta/consulta
            top_k: Número de resultados
            classification: Filtrar por classificação
            tags: Filtrar por tags
            min_score: Score mínimo para retornar
            use_cache: Usar cache de resultados
            user_id: ID do usuário (para auditoria)
        """
        # Verifica cache
        cache_key = f"{tenant_id}:{question}:{classification}:{str(tags)}"
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            # Cache válido por 5 minutos
            if cached and (datetime.now() - timedelta(minutes=5)).isoformat() < cached[0].updated_at:
                results = cached
            else:
                with self._lock:
                    self._cache.pop(cache_key, None)
                results = []
        else:
            results = []
        
        if not results:
            # Busca no banco
            with self._connect() as conn:
                query = """
                    SELECT id, content, citation, classification, tags_json,
                           created_at, updated_at, access_count, embedding
                    FROM memory
                    WHERE tenant_id=?
                """
                params = [tenant_id]
                
                if classification:
                    query += " AND classification=?"
                    params.append(classification)
                
                rows = conn.execute(query, params).fetchall()
            
            # Filtra por tags se necessário
            if tags:
                tag_set = set(tags)
                rows = [
                    row for row in rows
                    if tag_set.intersection(set(json.loads(row[4])))
                ]
            
            if not rows:
                return {
                    "status": "ok",
                    "tenant_id": tenant_id,
                    "question": question,
                    "results": [],
                    "total_found": 0
                }
            
            # Prepara corpus para BM25
            corpus = [row[1] for row in rows]  # content
            bm25 = BM25()
            bm25.index(corpus)
            
            # Busca BM25
            bm25_results = bm25.search(question, top_k * 2)
            
            # Prepara embeddings para busca semântica
            embeddings_dict = {}
            if self.enable_embeddings:
                for row in rows:
                    if row[8]:  # embedding
                        embeddings_dict[row[0]] = row[8]
                
                # Gera embedding da query
                query_embedding = self._generate_embedding(question)
            
            # Combina scores
            scored_results = []
            for idx, bm25_score in bm25_results:
                row = rows[idx]
                memory_id = row[0]
                content = row[1]
                citation = row[2]
                classification_val = row[3]
                tags_val = json.loads(row[4])
                created_at = row[5]
                updated_at = row[6]
                access_count = row[7]
                
                # Score BM25 (normalizado)
                bm25_norm = min(1.0, bm25_score / 10.0)
                
                # Score semântico
                semantic_score = 0.0
                if self.enable_embeddings and query_embedding and memory_id in embeddings_dict:
                    semantic_score = self._compute_cosine_similarity(
                        query_embedding, embeddings_dict[memory_id]
                    )
                
                # Score combinado
                combined_score = (bm25_norm * 0.4 + semantic_score * 0.6)
                
                if combined_score >= min_score:
                    scored_results.append({
                        "content": content,
                        "citation": citation,
                        "classification": classification_val,
                        "tags": tags_val,
                        "bm25_score": bm25_norm,
                        "semantic_score": semantic_score,
                        "combined_score": combined_score,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "access_count": access_count,
                        "memory_id": memory_id
                    })
            
            # Ordena por score combinado
            scored_results.sort(key=lambda x: x["combined_score"], reverse=True)
            results = scored_results[:top_k]
            
            # Atualiza cache
            with self._lock:
                self._cache[cache_key] = results
        
        # Atualiza contadores de acesso
        for r in results:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE memory SET access_count=access_count+1, last_accessed=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), r["memory_id"])
                )
                conn.commit()
        
        # Log de auditoria
        self._log_audit(tenant_id, "query", user_id=user_id, details={
            "question": question[:200],
            "classification_filter": classification,
            "tags_filter": tags,
            "results_count": len(results)
        })
        
        # Formata resultados
        formatted_results = [
            QueryResult(
                content=r["content"],
                citation=r["citation"],
                classification=r["classification"],
                tags=r["tags"],
                score=r["combined_score"],
                semantic_score=r["semantic_score"],
                bm25_score=r["bm25_score"]
            ) for r in results
        ]
        
        return {
            "status": "ok",
            "tenant_id": tenant_id,
            "question": question,
            "results": [r.to_dict() for r in formatted_results],
            "total_found": len(formatted_results),
            "semantic_search_enabled": self.enable_embeddings,
            "bm25_enabled": True
        }
    
    def delete(
        self,
        tenant_id: str,
        memory_id: int,
        user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove entrada de memória."""
        with self._connect() as conn:
            # Verifica existência
            row = conn.execute(
                "SELECT content FROM memory WHERE id=? AND tenant_id=?",
                (memory_id, tenant_id)
            ).fetchone()
            
            if not row:
                return {"status": "error", "error": "Memory entry not found"}
            
            # Remove
            conn.execute("DELETE FROM memory WHERE id=?", (memory_id,))
            conn.commit()
        
        # Reconstrói índice
        self._rebuild_bm25_index(tenant_id)
        
        # Limpa cache
        with self._lock:
            self._cache.clear()
        
        # Log de auditoria
        self._log_audit(tenant_id, "delete", memory_id, user_id, {"reason": reason})
        
        return {
            "status": "ok",
            "action": "delete",
            "memory_id": memory_id,
            "tenant_id": tenant_id
        }
    
    def purge_expired(self, retention_days: Dict[str, int]) -> Dict[str, Any]:
        """
        Remove memórias expiradas baseado em política de retenção.
        
        Args:
            retention_days: Dict com retenção por classificação,
                           ex: {"internal": 90, "confidential": 30, "default": 365}
        """
        now = datetime.now(timezone.utc)
        deleted = 0
        deleted_details = []
        
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, classification, created_at, tenant_id FROM memory"
            ).fetchall()
            
            for row_id, classification, created_at, tenant_id in rows:
                retention = retention_days.get(classification, retention_days.get("default", 365))
                try:
                    created = datetime.fromisoformat(created_at)
                except ValueError:
                    created = now
                
                if created < now - timedelta(days=retention):
                    conn.execute("DELETE FROM memory WHERE id=?", (row_id,))
                    deleted += 1
                    deleted_details.append({
                        "id": row_id,
                        "classification": classification,
                        "tenant_id": tenant_id,
                        "created_at": created_at
                    })
                    self._log_audit(
                        tenant_id, "auto_purge", row_id,
                        details={"retention_days": retention, "expired_at": created_at}
                    )
            
            conn.commit()
        
        # Reconstrói índices afetados
        tenants_affected = set(d["tenant_id"] for d in deleted_details)
        for tenant_id in tenants_affected:
            self._rebuild_bm25_index(tenant_id)
        
        # Limpa cache
        with self._lock:
            self._cache.clear()
        
        return {
            "status": "ok",
            "deleted": deleted,
            "deleted_details": deleted_details[:10],
            "retention_policy": retention_days
        }
    
    def get_statistics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Retorna estatísticas do sistema."""
        stats = {
            "total_entries": 0,
            "by_classification": defaultdict(int),
            "by_tag": defaultdict(int),
            "avg_access_count": 0.0,
            "total_accesses": 0,
            "last_7_days_queries": 0
        }
        
        with self._connect() as conn:
            if tenant_id:
                rows = conn.execute(
                    "SELECT classification, tags_json, access_count FROM memory WHERE tenant_id=?",
                    (tenant_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT classification, tags_json, access_count FROM memory"
                ).fetchall()
            
            stats["total_entries"] = len(rows)
            total_accesses = 0
            
            for classification, tags_json, access_count in rows:
                stats["by_classification"][classification] += 1
                total_accesses += access_count
                
                for tag in json.loads(tags_json):
                    stats["by_tag"][tag] += 1
            
            if stats["total_entries"] > 0:
                stats["avg_access_count"] = total_accesses / stats["total_entries"]
            stats["total_accesses"] = total_accesses
            
            # Consultas nos últimos 7 dias
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            stats["last_7_days_queries"] = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action='query' AND timestamp > ?",
                (week_ago,)
            ).fetchone()[0]
        
        # Converte defaultdicts para dict
        stats["by_classification"] = dict(stats["by_classification"])
        stats["by_tag"] = dict(sorted(stats["by_tag"].items(), key=lambda x: x[1], reverse=True)[:20])
        
        return stats
    
    def get_audit_log(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        action: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retorna log de auditoria."""
        with self._connect() as conn:
            query = "SELECT id, tenant_id, action, memory_id, user_id, timestamp, details_json FROM audit_log"
            params = []
            
            conditions = []
            if tenant_id:
                conditions.append("tenant_id=?")
                params.append(tenant_id)
            if action:
                conditions.append("action=?")
                params.append(action)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    "id": row[0],
                    "tenant_id": row[1],
                    "action": row[2],
                    "memory_id": row[3],
                    "user_id": row[4],
                    "timestamp": row[5],
                    "details": json.loads(row[6]) if row[6] else {}
                }
                for row in rows
            ]


# =============================================================================
# Reasoning Trace Builder (Compatibilidade com código original)
# =============================================================================

def build_reasoning_trace(steps: List[str], citations: List[str]) -> Dict[str, Any]:
    """
    Constrói trilha de raciocínio para auditoria e transparência.
    """
    redacted_steps = [redact_secrets(step) for step in steps]
    missing = [i for i, c in enumerate(citations) if not c]
    
    return {
        "status": "ok" if not missing else "warn",
        "steps": redacted_steps,
        "citations": citations,
        "citations_required": len(missing) == 0,
        "missing_citation_indexes": missing,
        "total_steps": len(steps),
        "complete_citations": sum(1 for c in citations if c)
    }


# =============================================================================
# Instância global para uso em toda a aplicação
# =============================================================================

_default_memory: Optional[TenantMemoryRAG] = None


def get_memory_instance(db_path: str | Path = "atena_evolution/corporate_memory.db") -> TenantMemoryRAG:
    """Retorna instância global do sistema de memória."""
    global _default_memory
    if _default_memory is None:
        _default_memory = TenantMemoryRAG(db_path)
    return _default_memory


# =============================================================================
# CLI e Demonstração
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Corporate Memory & RAG Engine")
    parser.add_argument("--init", action="store_true", help="Inicializa banco de dados")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas")
    parser.add_argument("--query", type=str, help="Faz uma consulta RAG")
    parser.add_argument("--tenant", type=str, default="default", help="Tenant ID")
    parser.add_argument("--classification", type=str, help="Filtrar por classificação")
    
    args = parser.parse_args()
    
    memory = get_memory_instance()
    
    if args.init:
        print("✅ Banco de memória inicializado")
        return 0
    
    if args.stats:
        stats = memory.get_statistics(args.tenant)
        print(json.dumps(stats, indent=2, default=str))
        return 0
    
    if args.query:
        result = memory.query(
            tenant_id=args.tenant,
            question=args.query,
            classification=args.classification
        )
        print(f"\n🔍 Resultados para: {args.query}")
        print("=" * 60)
        for i, r in enumerate(result["results"], 1):
            print(f"\n{i}. [Score: {r['score']:.2%}]")
            print(f"   {r['content'][:200]}...")
            print(f"   📎 {r['citation']}")
            if r['tags']:
                print(f"   🏷️ Tags: {', '.join(r['tags'])}")
        return 0
    
    print("Use --help para ver opções disponíveis")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
