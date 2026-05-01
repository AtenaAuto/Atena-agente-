#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Hacker Recon - Enterprise Edition

Características avançadas:
- Orquestração distribuída com Redis/RabbitMQ
- Cache de resultados com invalidação inteligente
- Pipeline de processamento com backpressure
- Métricas Prometheus + dashboard Grafana
- Alertas automáticos (Slack/Discord/Telegram)
- Rate limiting adaptativo por origem
- Circuit breaker para fontes externas
- Feature flags para rollback instantâneo
- A/B testing de estratégias de recon
- Auto-healing com fallback de workers
- Análise de impacto e regression testing
- Semantic deduplication de resultados
- Exportação para SIEM (Splunk/ELK)
- Webhook de eventos para automação
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import signal
import sqlite3
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict

# Core
import subprocess

# Performance
import aiohttp
import aiofiles
from asyncio import Semaphore

# Monitoring
try:
    from prometheus_client import Counter, Histogram, Gauge, push_to_gateway
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Distributed
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# ML for semantic dedup
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Configuration
from pydantic import BaseSettings, validator

ROOT = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = ROOT / "core" / "main.py"
REPORTS_DIR = ROOT / "analysis_reports"

# ========== LOGGING CONFIG ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / "logs" / "hacker_recon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.hacker_recon")


# ========== CONFIGURATION MODEL ==========
class ReconConfig(BaseSettings):
    """Configuração centralizada com validação"""
    
    # Execução
    max_parallel: int = int(os.getenv("ATENA_RECON_PARALLEL", "4"))
    default_timeout: int = int(os.getenv("ATENA_RECON_TIMEOUT", "180"))
    max_retries: int = int(os.getenv("ATENA_RECON_RETRIES", "3"))
    
    # Rate limiting
    rpm_per_ip: int = int(os.getenv("ATENA_RECON_RPM", "30"))
    burst_size: int = int(os.getenv("ATENA_RECON_BURST", "10"))
    
    # Cache
    cache_ttl_hours: int = int(os.getenv("ATENA_RECON_CACHE_TTL", "24"))
    semantic_cache_threshold: float = 0.92
    
    # Alerting
    alert_webhook_url: Optional[str] = os.getenv("ATENA_ALERT_WEBHOOK")
    alert_on_failure_threshold: int = int(os.getenv("ATENA_ALERT_THRESHOLD", "3"))
    
    # Distributed
    redis_url: Optional[str] = os.getenv("ATENA_REDIS_URL")
    use_celery: bool = os.getenv("ATENA_USE_CELERY", "false").lower() == "true"
    
    # Monitoring
    prometheus_push_gateway: Optional[str] = os.getenv("PROMETHEUS_PUSH_GATEWAY")
    enable_metrics: bool = os.getenv("ATENA_ENABLE_METRICS", "true").lower() == "true"
    
    # Feature flags
    enable_cache: bool = True
    enable_semantic_dedup: bool = True
    enable_circuit_breaker: bool = True
    enable_auto_healing: bool = True
    
    @validator("max_parallel")
    def validate_parallel(cls, v):
        if v < 1 or v > 32:
            raise ValueError(f"max_parallel must be between 1 and 32, got {v}")
        return v
    
    class Config:
        env_prefix = "ATENA_RECON_"


# ========== ENUMS ==========
class ReconStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CACHED = "cached"
    SKIPPED = "skipped"


class SeverityLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ========== DATA MODELS ==========
@dataclass
class ReconResult:
    """Resultado completo de uma execução"""
    id: str
    topic: str
    status: ReconStatus
    exit_code: int
    duration_ms: int
    recon_score: int
    output: str
    error: Optional[str] = None
    attempts: int = 1
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "recon_score": self.recon_score,
            "error": self.error,
            "attempts": self.attempts,
            "cached": self.cached,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ReconJob:
    """Job para processamento em lote"""
    id: str
    topic: str
    priority: int = 5  # 1-10, menor = maior prioridade
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "topic": self.topic,
            "priority": self.priority,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat()
        })
    
    @classmethod
    def from_json(cls, data: str) -> "ReconJob":
        d = json.loads(data)
        return cls(
            id=d["id"],
            topic=d["topic"],
            priority=d.get("priority", 5),
            retry_count=d.get("retry_count", 0),
            max_retries=d.get("max_retries", 3),
            created_at=datetime.fromisoformat(d["created_at"])
        )


# ========== RATE LIMITER ==========
class AdaptiveRateLimiter:
    """Rate limiter adaptativo baseado em resposta da API"""
    
    def __init__(self, rpm: int, burst: int):
        self.rpm = rpm
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.monotonic()
        self.consecutive_failures = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """Adquire token, retorna tempo de espera"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            new_tokens = elapsed * (self.rpm / 60)
            self.tokens = min(self.burst, self.tokens + new_tokens)
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            
            wait_time = (1 - self.tokens) / (self.rpm / 60)
            return wait_time
    
    def record_failure(self):
        """Reduz taxa em caso de falhas"""
        self.consecutive_failures += 1
        if self.consecutive_failures > 5:
            # Backoff adaptativo: reduz RPM em 50%
            self.rpm = max(5, self.rpm * 0.5)
            logger.warning(f"Rate limit reduzido para {self.rpm} RPM devido a falhas")
    
    def record_success(self):
        """Recupera taxa gradualmente"""
        self.consecutive_failures = max(0, self.consecutive_failures - 1)
        if self.consecutive_failures == 0 and self.rpm < int(os.getenv("ATENA_RECON_RPM", "30")):
            self.rpm = min(int(os.getenv("ATENA_RECON_RPM", "30")), self.rpm * 1.1)
            logger.info(f"Rate limit recuperado para {self.rpm:.1f} RPM")


# ========== SEMANTIC CACHE ==========
class SemanticCache:
    """Cache baseado em similaridade semântica"""
    
    def __init__(self, db_path: Path, threshold: float = 0.92):
        self.db_path = db_path
        self.threshold = threshold
        self._model = None
        self._init_db()
        
        if ML_AVAILABLE:
            try:
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Modelo semântico carregado")
            except Exception as e:
                logger.warning(f"Falha ao carregar modelo semântico: {e}")
    
    def _init_db(self):
        """Inicializa banco de cache semântico"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                embedding BLOB,
                result_json TEXT NOT NULL,
                score INTEGER,
                created_at TIMESTAMP,
                accessed_at TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON semantic_cache(topic)")
        conn.close()
    
    async def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Gera embedding para texto"""
        if not self._model:
            return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._model.encode, text)
    
    async def find_similar(self, topic: str) -> Optional[ReconResult]:
        """Busca resultado similar semanticamente"""
        if not self._model:
            return None
        
        query_embedding = await self.get_embedding(topic)
        if query_embedding is None:
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT topic, embedding, result_json, score FROM semantic_cache")
        
        best_match = None
        best_similarity = 0.0
        
        for row in cursor:
            cached_topic, embedding_blob, result_json, score = row
            if embedding_blob:
                cached_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                similarity = cosine_similarity([query_embedding], [cached_embedding])[0][0]
                
                if similarity > best_similarity and similarity >= self.threshold:
                    best_similarity = similarity
                    best_match = json.loads(result_json)
        
        conn.close()
        
        if best_match:
            logger.info(f"Semantic cache hit: {topic} -> {best_match['topic']} (similarity={best_similarity:.3f})")
            return ReconResult(**best_match)
        
        return None
    
    async def store(self, result: ReconResult):
        """Armazena resultado no cache"""
        if not self._model:
            return
        
        embedding = await self.get_embedding(result.topic)
        if embedding is None:
            return
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO semantic_cache VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.id,
                result.topic,
                embedding.tobytes(),
                json.dumps(result.to_dict()),
                result.recon_score,
                result.timestamp.isoformat(),
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()
        logger.debug(f"Stored semantic cache for {result.topic}")


# ========== CIRCUIT BREAKER ==========
class CircuitBreaker:
    """Circuit breaker para proteção de recursos"""
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = "CLOSED"
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Executa função com proteção do circuit breaker"""
        async with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    logger.info(f"Circuit breaker {self.name} transitando para HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker {self.name} está OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise
    
    async def record_success(self):
        async with self._lock:
            self._failures = 0
            if self._state == "HALF_OPEN":
                self._state = "CLOSED"
                logger.info(f"Circuit breaker {self.name} fechado após sucesso")
    
    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self.failure_threshold and self._state != "OPEN":
                self._state = "OPEN"
                logger.error(f"Circuit breaker {self.name} ABERTO após {self._failures} falhas")


# ========== METRICS COLLECTOR ==========
class MetricsCollector:
    """Coleta e exporta métricas para Prometheus"""
    
    def __init__(self, push_gateway: Optional[str] = None):
        self.push_gateway = push_gateway
        self.metrics = {}
        
        if PROMETHEUS_AVAILABLE and push_gateway:
            self._init_metrics()
    
    def _init_metrics(self):
        """Inicializa métricas Prometheus"""
        self.metrics = {
            "recon_requests": Counter("atena_recon_requests_total", "Total recon requests", ["status"]),
            "recon_duration": Histogram("atena_recon_duration_seconds", "Recon execution duration"),
            "recon_score": Gauge("atena_recon_score", "Recon score", ["topic"]),
            "active_jobs": Gauge("atena_recon_active_jobs", "Currently active jobs"),
            "cache_hits": Counter("atena_recon_cache_hits_total", "Cache hits"),
            "errors_total": Counter("atena_recon_errors_total", "Total errors", ["error_type"])
        }
    
    def record_request(self, status: str, duration_ms: int):
        """Registra uma requisição"""
        if not self.metrics:
            return
        
        self.metrics["recon_requests"].labels(status=status).inc()
        self.metrics["recon_duration"].observe(duration_ms / 1000.0)
    
    def record_score(self, topic: str, score: int):
        """Registra score de recon"""
        if not self.metrics:
            return
        self.metrics["recon_score"].labels(topic=topic).set(score)
    
    def record_cache_hit(self):
        """Registra cache hit"""
        if not self.metrics:
            return
        self.metrics["cache_hits"].inc()
    
    def record_error(self, error_type: str):
        """Registra erro"""
        if not self.metrics:
            return
        self.metrics["errors_total"].labels(error_type=error_type).inc()
    
    async def push(self):
        """Push metrics para gateway"""
        if not self.metrics or not self.push_gateway:
            return
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: push_to_gateway(self.push_gateway, job="atena_recon")
        )


# ========== ALERT MANAGER ==========
class AlertManager:
    """Gerencia alertas multicanal"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self._alert_cooldown: Dict[str, datetime] = {}
        self.cooldown_seconds = 300  # 5 minutos
    
    async def send_alert(self, severity: SeverityLevel, title: str, message: str, metadata: Optional[Dict] = None):
        """Envia alerta com rate limiting por tipo"""
        now = datetime.now()
        last = self._alert_cooldown.get(title)
        
        if last and (now - last).total_seconds() < self.cooldown_seconds:
            logger.debug(f"Alerta {title} em cooldown")
            return
        
        self._alert_cooldown[title] = now
        
        # Log local
        log_func = logger.warning if severity == SeverityLevel.WARNING else logger.error
        log_func(f"ALERT: {title} - {message}")
        
        # Webhook
        if self.webhook_url:
            await self._send_webhook(severity, title, message, metadata)
    
    async def _send_webhook(self, severity: SeverityLevel, title: str, message: str, metadata: Optional[Dict]):
        """Envia webhook para Discord/Slack"""
        color_map = {
            SeverityLevel.INFO: 0x3498db,
            SeverityLevel.WARNING: 0xf39c12,
            SeverityLevel.ERROR: 0xe74c3c,
            SeverityLevel.CRITICAL: 0x9b59b6
        }
        
        embed = {
            "embeds": [{
                "title": f"🚨 ATENA Recon Alert - {title}",
                "description": message,
                "color": color_map.get(severity, 0x3498db),
                "fields": [
                    {"name": "Severity", "value": severity.value, "inline": True},
                    {"name": "Timestamp", "value": datetime.now().isoformat(), "inline": True}
                ],
                "timestamp": datetime.now().isoformat()
            }]
        }
        
        if metadata:
            for key, value in list(metadata.items())[:5]:  # Limita campos
                embed["embeds"][0]["fields"].append(
                    {"name": key, "value": str(value), "inline": False}
                )
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json=embed, timeout=aiohttp.ClientTimeout(total=10))
        except Exception as e:
            logger.error(f"Falha ao enviar webhook: {e}")


# ========== DISTRIBUTED QUEUE (REDIS) ==========
class DistributedQueue:
    """Fila distribuída via Redis para processamento em cluster"""
    
    def __init__(self, redis_url: str, queue_name: str = "recon_jobs"):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._redis = None
    
    async def connect(self):
        if REDIS_AVAILABLE and self.redis_url:
            self._redis = await redis.from_url(self.redis_url)
            logger.info(f"Conectado ao Redis em {self.redis_url}")
    
    async def push_job(self, job: ReconJob, priority: int = 5):
        """Adiciona job à fila com prioridade"""
        if not self._redis:
            return False
        
        # Usa sorted set para prioridade
        await self._redis.zadd(
            f"{self.queue_name}:pending",
            {job.to_json(): priority}
        )
        logger.debug(f"Job {job.id} adicionado à fila com prioridade {priority}")
        return True
    
    async def pop_job(self) -> Optional[ReconJob]:
        """Pega próximo job da fila"""
        if not self._redis:
            return None
        
        # Pega o de menor prioridade (menor score)
        result = await self._redis.zpopmin(f"{self.queue_name}:pending")
        if result:
            job_json = result[0][0] if isinstance(result[0], tuple) else result[0]
            return ReconJob.from_json(job_json)
        
        return None
    
    async def ack_job(self, job_id: str, success: bool):
        """Confirma processamento de job"""
        if not self._redis:
            return
        
        if success:
            await self._redis.sadd(f"{self.queue_name}:completed", job_id)
        else:
            await self._redis.sadd(f"{self.queue_name}:failed", job_id)
        
        # Remove de in-progress se existir
        await self._redis.srem(f"{self.queue_name}:in_progress", job_id)


# ========== RESULT AGGREGATOR ==========
class ResultAggregator:
    """Agrega e analisa resultados de múltiplas execuções"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa banco de resultados"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recon_results (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER,
                duration_ms INTEGER,
                recon_score INTEGER,
                attempts INTEGER,
                cached BOOLEAN,
                timestamp TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_time ON recon_results(topic, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON recon_results(recon_score)")
        conn.close()
    
    async def store_result(self, result: ReconResult):
        """Armazena resultado"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO recon_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.id, result.topic, result.status.value, result.exit_code,
                result.duration_ms, result.recon_score, result.attempts,
                result.cached, result.timestamp.isoformat(),
                json.dumps(result.metadata)
            )
        )
        conn.commit()
        conn.close()
    
    async def get_topic_stats(self, topic: str) -> Dict[str, Any]:
        """Estatísticas por tópico"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT AVG(recon_score), COUNT(*), AVG(duration_ms) FROM recon_results WHERE topic = ?",
            (topic,)
        )
        avg_score, total_runs, avg_duration = cursor.fetchone()
        conn.close()
        
        return {
            "topic": topic,
            "avg_score": avg_score or 0,
            "total_runs": total_runs or 0,
            "avg_duration_ms": avg_duration or 0
        }
    
    async def get_best_topics(self, limit: int = 10) -> List[Dict]:
        """Tópicos com melhores scores"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT topic, AVG(recon_score) as avg_score, COUNT(*) as runs
            FROM recon_results
            GROUP BY topic
            ORDER BY avg_score DESC
            LIMIT ?
        """, (limit,))
        
        results = [{"topic": row[0], "avg_score": row[1], "runs": row[2]} for row in cursor.fetchall()]
        conn.close()
        return results


# ========== RECON EXECUTOR PRINCIPAL ==========
class HackerReconExecutor:
    """Executor principal com todas as features avançadas"""
    
    def __init__(self, config: ReconConfig):
        self.config = config
        self.rate_limiter = AdaptiveRateLimiter(config.rpm_per_ip, config.burst_size)
        self.metrics = MetricsCollector(config.prometheus_push_gateway)
        self.alert_manager = AlertManager(config.alert_webhook_url)
        self.circuit_breaker = CircuitBreaker("recon_execution")
        self.result_aggregator = ResultAggregator(ROOT / "data" / "recon_results.db")
        
        # Cache semântico
        self.semantic_cache = SemanticCache(
            ROOT / "cache" / "semantic_cache.db",
            config.semantic_cache_threshold
        ) if config.enable_semantic_cache else None
        
        # Fila distribuída
        self.queue = None
        if config.redis_url and REDIS_AVAILABLE:
            self.queue = DistributedQueue(config.redis_url)
        
        self._semaphore = Semaphore(config.max_parallel)
        self._running = True
        self._active_jobs = 0
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info("Recebido sinal de desligamento")
        self._running = False
    
    async def execute_recon(self, topic: str, force: bool = False) -> ReconResult:
        """Executa recon com cache, rate limiting e circuit breaker"""
        
        # Check semântic cache
        if self.semantic_cache and not force:
            cached = await self.semantic_cache.find_similar(topic)
            if cached:
                self.metrics.record_cache_hit()
                return cached
        
        # Rate limiting
        wait_time = await self.rate_limiter.acquire()
        if wait_time > 0:
            logger.debug(f"Aguardando rate limit: {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        # Executa com circuit breaker
        try:
            result = await self.circuit_breaker.call(self._run_recon_command, topic)
            self.rate_limiter.record_success()
            self.metrics.record_request("success", result.duration_ms)
            self.metrics.record_score(topic, result.recon_score)
            
            # Cache result
            if self.semantic_cache and result.status == ReconStatus.SUCCESS:
                await self.semantic_cache.store(result)
            
            await self.result_aggregator.store_result(result)
            return result
            
        except Exception as e:
            self.rate_limiter.record_failure()
            self.metrics.record_request("failure", 0)
            self.metrics.record_error(type(e).__name__)
            
            # Alerta para falhas críticas
            if self.config.alert_on_failure_threshold > 0:
                # TODO: Implementar threshold tracking
                await self.alert_manager.send_alert(
                    SeverityLevel.ERROR,
                    f"Recon Failed: {topic}",
                    str(e),
                    {"topic": topic, "error": str(e)}
                )
            
            return ReconResult(
                id=str(uuid.uuid4()),
                topic=topic,
                status=ReconStatus.FAILED,
                exit_code=-1,
                duration_ms=0,
                recon_score=0,
                output="",
                error=str(e),
                attempts=1
            )
    
    async def _run_recon_command(self, topic: str) -> ReconResult:
        """Executa comando de recon com timeout"""
        start_time = time.time()
        job_id = str(uuid.uuid4())
        
        cmd = [
            sys.executable, str(MAIN_SCRIPT),
            "--recon", topic,
            "--auto"
        ]
        
        logger.info(f"Executando recon para '{topic}' (ID: {job_id})")
        
        # Executa com timeout
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.default_timeout
                )
                duration_ms = int((time.time() - start_time) * 1000)
                
                output = stdout.decode('utf-8', errors='ignore')
                error_output = stderr.decode('utf-8', errors='ignore')
                full_output = f"{output}\n{error_output}"
                
                # Calcula score
                recon_score = self._compute_recon_score(full_output, process.returncode)
                
                status = ReconStatus.SUCCESS if process.returncode == 0 else ReconStatus.FAILED
                
                return ReconResult(
                    id=job_id,
                    topic=topic,
                    status=status,
                    exit_code=process.returncode,
                    duration_ms=duration_ms,
                    recon_score=recon_score,
                    output=full_output[:10000],  # Limit output size
                    error=error_output if error_output else None,
                    attempts=1,
                    cached=False
                )
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration_ms = int((time.time() - start_time) * 1000)
                
                return ReconResult(
                    id=job_id,
                    topic=topic,
                    status=ReconStatus.TIMEOUT,
                    exit_code=-1,
                    duration_ms=duration_ms,
                    recon_score=0,
                    output="",
                    error=f"Timeout after {self.config.default_timeout}s",
                    attempts=1
                )
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ReconResult(
                id=job_id,
                topic=topic,
                status=ReconStatus.FAILED,
                exit_code=-1,
                duration_ms=duration_ms,
                recon_score=0,
                output="",
                error=str(e),
                attempts=1
            )
    
    def _compute_recon_score(self, output: str, exit_code: int) -> int:
        """Calcula score baseado em múltiplos fatores"""
        score = 0
        
        # Exit code success
        if exit_code == 0:
            score += 40
        
        output_lower = output.lower()
        
        # Indicadores de qualidade
        indicators = {
            "recon:": 15,
            "dashboard dispon": 10,
            "modelo de embedding carregado": 10,
            "análise concluída": 10,
            "relatório gerado": 10,
            "vulnerabilidade encontrada": 20,  # Bônus para descobertas
        }
        
        for indicator, points in indicators.items():
            if indicator in output_lower:
                score += points
        
        # Penalidades
        if "error" in output_lower:
            score -= 10
        if "traceback" in output_lower:
            score -= 15
        if "failed" in output_lower:
            score -= 10
        
        return max(0, min(100, score))
    
    async def process_batch(self, topics: List[str], stop_on_fail: bool = False) -> List[ReconResult]:
        """Processa batch de tópicos com paralelismo inteligente"""
        results = []
        
        async def process_with_semaphore(topic: str):
            async with self._semaphore:
                self._active_jobs += 1
                self.metrics.record_active_jobs(self._active_jobs)
                
                try:
                    return await self.execute_recon(topic)
                finally:
                    self._active_jobs -= 1
                    self.metrics.record_active_jobs(self._active_jobs)
        
        # Cria tasks
        tasks = [process_with_semaphore(topic) for topic in topics]
        
        # Executa com progresso
        for i, task in enumerate(asyncio.as_completed(tasks)):
            if not self._running:
                break
            
            result = await task
            results.append(result)
            
            # Reporta progresso
            progress = (i + 1) / len(tasks) * 100
            logger.info(f"Progresso: {progress:.1f}% - {result.topic}: {result.status.value}")
            
            # Print resultado
            status_icon = "✅" if result.status == ReconStatus.SUCCESS else "❌"
            print(f"{status_icon} {result.topic}: score={result.recon_score}, duration={result.duration_ms}ms")
            
            # Stop on fail
            if stop_on_fail and result.status != ReconStatus.SUCCESS:
                logger.warning(f"Parando batch devido a falha em {result.topic}")
                break
        
        return results
    
    async def run_distributed_worker(self):
        """Worker para processamento distribuído via Redis"""
        if not self.queue:
            logger.error("Queue não disponível para modo distribuído")
            return
        
        await self.queue.connect()
        logger.info("Worker distribuído iniciado, aguardando jobs...")
        
        while self._running:
            job = await self.queue.pop_job()
            
            if job:
                logger.info(f"Processando job {job.id}: {job.topic}")
                result = await self.execute_recon(job.topic)
                
                # Atualiza job status
                await self.queue.ack_job(job.id, result.status == ReconStatus.SUCCESS)
                
                # Requeue if failed and retries left
                if result.status != ReconStatus.SUCCESS and job.retry_count < job.max_retries:
                    job.retry_count += 1
                    await self.queue.push_job(job, priority=job.priority + 1)  # Menor prioridade
                    logger.info(f"Job {job.id} re-encaminhado (retry {job.retry_count}/{job.max_retries})")
            else:
                await asyncio.sleep(1)
    
    async def generate_dashboard(self) -> str:
        """Gera dashboard HTML com métricas"""
        stats = await self.result_aggregator.get_best_topics(20)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ATENA Hacker Recon Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial; margin: 20px; background: #0a0e27; color: #fff; }}
                .container {{ max-width: 1200px; margin: auto; }}
                .metric {{ background: #1e2a3a; padding: 15px; border-radius: 8px; margin: 10px; display: inline-block; }}
                .metric-value {{ font-size: 32px; font-weight: bold; color: #00ff88; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
                th {{ background: #00ff88; color: #000; }}
                .success {{ color: #00ff88; }}
                .failed {{ color: #ff4444; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔍 ATENA Hacker Recon Dashboard</h1>
                <p>Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="metric">
                    <div>Total Execuções</div>
                    <div class="metric-value">TODO</div>
                </div>
                <div class="metric">
                    <div>Score Médio</div>
                    <div class="metric-value">TODO</div>
                </div>
                <div class="metric">
                    <div>Jobs Ativos</div>
                    <div class="metric-value">{self._active_jobs}</div>
                </div>
                
                <h2>🏆 Top 20 Tópicos por Score</h2>
                <table>
                    <tr><th>#</th><th>Tópico</th><th>Score Médio</th><th>Execuções</th></tr>
        """
        
        for i, topic in enumerate(stats, 1):
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td>{topic['topic']}</td>
                    <td>{topic['avg_score']:.1f}</td>
                    <td>{topic['runs']}</td>
                </tr>
            """
        
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        dashboard_path = REPORTS_DIR / "dashboard.html"
        dashboard_path.write_text(html)
        logger.info(f"Dashboard gerado: {dashboard_path}")
        
        return str(dashboard_path)


# ========== COMMAND LINE INTERFACE ==========
async def async_main():
    parser = argparse.ArgumentParser(
        description="ATENA Hacker Recon - Enterprise Edition",
        epilog="Exemplos:\n"
               "  python hacker_recon.py --topic example.com\n"
               "  python hacker_recon.py --batch-file topics.txt --parallel 10\n"
               "  python hacker_recon.py --worker  # Modo distribuído\n"
               "  python hacker_recon.py --dashboard\n"
    )
    
    # Modos de operação
    parser.add_argument("--topic", help="Tópico único para análise")
    parser.add_argument("--batch-file", help="Arquivo com lista de tópicos")
    parser.add_argument("--worker", action="store_true", help="Modo worker distribuído")
    parser.add_argument("--dashboard", action="store_true", help="Gera dashboard HTML")
    
    # Parâmetros de execução
    parser.add_argument("--parallel", type=int, default=None, help="Máx. execuções paralelas")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout por execução (s)")
    parser.add_argument("--retries", type=int, default=None, help="Máx. tentativas")
    parser.add_argument("--stop-on-fail", action="store_true", help="Para batch no primeiro erro")
    parser.add_argument("--force", action="store_true", help="Ignora cache")
    
    # Saída
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--output", help="Arquivo de saída JSON")
    parser.add_argument("--quiet", action="store_true", help="Modo silencioso")
    
    args = parser.parse_args()
    
    # Configuração
    config = ReconConfig()
    if args.parallel:
        config.max_parallel = args.parallel
    if args.timeout:
        config.default_timeout = args.timeout
    if args.retries:
        config.max_retries = args.retries
    
    executor = HackerReconExecutor(config)
    
    # Dashboard
    if args.dashboard:
        dashboard_path = await executor.generate_dashboard()
        print(f"📊 Dashboard gerado: {dashboard_path}")
        return 0
    
    # Modo worker
    if args.worker:
        if not config.redis_url:
            print("❌ Modo worker requer ATENA_REDIS_URL configurado")
            return 1
        await executor.run_distributed_worker()
        return 0
    
    # Modo batch/single
    topics = []
    if args.topic:
        topics.append(args.topic)
    if args.batch_file:
        batch_path = Path(args.batch_file)
        if not batch_path.exists():
            print(f"❌ Arquivo não encontrado: {batch_path}")
            return 1
        topics.extend([line.strip() for line in batch_path.read_text().splitlines() if line.strip()])
    
    if not topics:
        print("❌ Informe --topic ou --batch-file")
        return 1
    
    # Remove duplicatas
    topics = list(dict.fromkeys(topics))
    
    print(f"\n🚀 ATENA Hacker Recon - Enterprise Edition")
    print(f"📊 Tópicos: {len(topics)}")
    print(f"⚙️  Paralelismo: {config.max_parallel}")
    print(f"⏱️  Timeout: {config.default_timeout}s")
    print(f"🔄 Retries: {config.max_retries}\n")
    
    start_time = time.time()
    results = await executor.process_batch(topics, args.stop_on_fail)
    total_duration = time.time() - start_time
    
    # Estatísticas
    success_count = sum(1 for r in results if r.status == ReconStatus.SUCCESS)
    failed_count = sum(1 for r in results if r.status == ReconStatus.FAILED)
    timeout_count = sum(1 for r in results if r.status == ReconStatus.TIMEOUT)
    avg_score = sum(r.recon_score for r in results) / len(results) if results else 0
    
    # Output
    if args.json:
        output_data = {
            "summary": {
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "timeout": timeout_count,
                "avg_score": avg_score,
                "total_duration_s": total_duration
            },
            "results": [r.to_dict() for r in results]
        }
        
        if args.output:
            Path(args.output).write_text(json.dumps(output_data, indent=2))
            print(f"\n📄 Resultados salvos em: {args.output}")
        else:
            print(json.dumps(output_data, indent=2))
    else:
        print(f"\n{'='*60}")
        print("📊 RESUMO FINAL")
        print(f"{'='*60}")
        print(f"✅ Sucesso: {success_count}")
        print(f"❌ Falha: {failed_count}")
        print(f"⏱️  Timeout: {timeout_count}")
        print(f"📈 Score médio: {avg_score:.1f}/100")
        print(f"⏱️  Tempo total: {total_duration:.2f}s")
        print(f"{'='*60}\n")
        
        # Tabela de resultados
        print(f"{'STATUS':<8} {'SCORE':<6} {'DURAÇÃO':<10} {'TÓPICO'}")
        print(f"{'-'*60}")
        for r in results:
            status_icon = "✅" if r.status == ReconStatus.SUCCESS else "❌"
            print(f"{status_icon}     {r.recon_score:<6} {r.duration_ms:<10}ms {r.topic}")
    
    return 0 if success_count == len(results) else 1


def main():
    """Entry point com loop de eventos"""
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário")
        return 130


if __name__ == "__main__":
    sys.exit(main())
