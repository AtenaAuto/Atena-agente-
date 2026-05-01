#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Advanced Rate Limiter + Smart Deduplicator v3.0
Sistema completo de controle de tráfego para APIs externas.

Recursos:
- 🚦 Rate limiting adaptativo por domínio (Token Bucket + Leaky Bucket)
- 🔄 Deduplicação inteligente de URLs com TTL customizável
- 💾 Persistência de estado para recuperação entre execuções
- 📊 Métricas detalhadas de uso e throttling
- 🧠 Aprendizado adaptativo de limites baseado em histórico
- 📝 Logging estruturado para auditoria
- ⚡ Monkey-patch automático para internet_challenge
- 🎯 Circuit breaker para falhas consecutivas
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("atena.rate_limiter")


# =============================================================================
# Enums and Data Classes
# =============================================================================

class CircuitBreakerState(Enum):
    """Estados do circuit breaker."""
    CLOSED = "closed"      # Operação normal
    OPEN = "open"          # Falhas detectadas, bloqueado
    HALF_OPEN = "half_open"  # Testando recuperação


@dataclass
class DomainMetrics:
    """Métricas de uso por domínio."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    dedup_hits: int = 0
    last_request_time: float = 0.0
    last_success_time: float = 0.0
    avg_response_time_ms: float = 0.0
    consecutive_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def record_success(self, response_time_ms: float = 0):
        self.total_requests += 1
        self.successful_requests += 1
        self.last_request_time = time.time()
        self.last_success_time = time.time()
        self.consecutive_failures = 0
        
        if response_time_ms > 0:
            # Média móvel
            total_prev = self.successful_requests - 1
            if total_prev > 0:
                self.avg_response_time_ms = (
                    (self.avg_response_time_ms * total_prev + response_time_ms) 
                    / self.successful_requests
                )
            else:
                self.avg_response_time_ms = response_time_ms
    
    def record_failure(self):
        self.total_requests += 1
        self.failed_requests += 1
        self.last_request_time = time.time()
        self.consecutive_failures += 1
    
    def record_rate_limited(self):
        self.rate_limited_requests += 1
    
    def record_dedup_hit(self):
        self.dedup_hits += 1
    
    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "dedup_hits": self.dedup_hits,
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "consecutive_failures": self.consecutive_failures,
            "last_request": datetime.fromtimestamp(self.last_request_time).isoformat() if self.last_request_time else None
        }


@dataclass
class RateLimitConfig:
    """Configuração de rate limit por domínio."""
    max_requests: int
    window_seconds: float
    burst_multiplier: float = 1.5  # Permite bursts curtos
    circuit_breaker_threshold: int = 5  # Falhas consecutivas para abrir
    circuit_breaker_timeout: float = 60.0  # Segundos para tentar recuperação
    adaptive_enabled: bool = True  # Se deve ajustar limites baseado em histórico
    
    def effective_max_requests(self, historical_success_rate: float = 1.0) -> int:
        """Calcula limite efetivo baseado em taxa de sucesso histórica."""
        if not self.adaptive_enabled:
            return self.max_requests
        
        if historical_success_rate < 0.5:
            return max(1, int(self.max_requests * 0.5))
        elif historical_success_rate < 0.8:
            return max(1, int(self.max_requests * 0.8))
        return self.max_requests


# =============================================================================
# Configuração de Limites por Domínio
# =============================================================================

_DEFAULT_CONFIG = RateLimitConfig(max_requests=30, window_seconds=60.0)

_DOMAIN_CONFIGS: dict[str, RateLimitConfig] = {
    # APIs de código/desenvolvimento (limites mais altos)
    "api.github.com":            RateLimitConfig(10, 60.0, burst_multiplier=2.0),
    "registry.npmjs.org":        RateLimitConfig(20, 60.0),
    "crates.io":                 RateLimitConfig(10, 60.0),
    "pypi.org":                  RateLimitConfig(10, 60.0),
    
    # APIs de conhecimento (limites moderados)
    "en.wikipedia.org":          RateLimitConfig(15, 60.0),
    "wikidata.org":              RateLimitConfig(10, 60.0),
    "api.stackexchange.com":     RateLimitConfig(10, 60.0),
    "openlibrary.org":           RateLimitConfig(10, 60.0),
    
    # APIs acadêmicas (mais restritivas)
    "export.arxiv.org":          RateLimitConfig(5, 60.0, circuit_breaker_threshold=3),
    "api.semanticscholar.org":   RateLimitConfig(5, 60.0),
    "api.crossref.org":          RateLimitConfig(5, 60.0),
    "api.openalex.org":          RateLimitConfig(5, 60.0),
    
    # APIs genéricas
    "api.publicapis.org":        RateLimitConfig(5, 60.0),
    "poetrydb.org":              RateLimitConfig(10, 60.0),
    "duckduckgo.com":            RateLimitConfig(10, 60.0),
}


# =============================================================================
# Token Bucket com Circuit Breaker
# =============================================================================

class TokenBucket:
    """
    Token bucket com suporte a bursts e circuit breaker.
    Thread-safe.
    """
    
    def __init__(self, capacity: int, refill_rate: float, refill_interval: float = 1.0):
        """
        Args:
            capacity: Número máximo de tokens
            refill_rate: Tokens por segundo
            refill_interval: Intervalo de recarga (segundos)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_interval = refill_interval
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        """Recarrega tokens baseado no tempo decorrido."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed >= self.refill_interval:
            new_tokens = elapsed * self.refill_rate
            self._tokens = min(self.capacity, self._tokens + new_tokens)
            self._last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """Consome tokens. Retorna True se bem-sucedido."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
    
    def get_available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


class CircuitBreaker:
    """
    Circuit breaker para prevenir chamadas a serviços com falhas.
    Thread-safe.
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_successes = 0
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitBreakerState:
        return self._state
    
    def record_success(self) -> None:
        """Registra sucesso - fecha ou mantém circuito."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= 2:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    self._half_open_successes = 0
                    logger.debug("Circuit breaker closed after recovery")
            elif self._state == CircuitBreakerState.OPEN:
                pass  # Permanece aberto até timeout
            else:
                self._failure_count = 0
    
    def record_failure(self) -> bool:
        """
        Registra falha. Retorna True se circuito abriu agora.
        """
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                self._last_failure_time = time.time()
                logger.warning("Circuit breaker reopened after failed recovery")
                return False
            
            if self._state == CircuitBreakerState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitBreakerState.OPEN
                    self._last_failure_time = time.time()
                    logger.warning(f"Circuit breaker opened after {self._failure_count} failures")
                    return True
            return False
    
    def allow_request(self) -> bool:
        """Verifica se requisição é permitida."""
        with self._lock:
            if self._state == CircuitBreakerState.CLOSED:
                return True
            
            if self._state == CircuitBreakerState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.timeout_seconds:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_successes = 0
                    logger.info("Circuit breaker half-open - testing recovery")
                    return True
                return False
            
            # HALF_OPEN - permite uma requisição de teste
            return True
    
    def get_state_info(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "last_failure": datetime.fromtimestamp(self._last_failure_time).isoformat() if self._last_failure_time else None,
                "half_open_successes": self._half_open_successes
            }


# =============================================================================
# Advanced Rate Limiter
# =============================================================================

class AdvancedRateLimiter:
    """
    Rate limiter adaptativo com token bucket, circuit breaker e métricas.
    Thread-safe.
    """

    def __init__(self, state_persistence_path: Optional[Path] = None):
        self._buckets: Dict[str, TokenBucket] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._metrics: Dict[str, DomainMetrics] = {}
        self._configs: Dict[str, RateLimitConfig] = _DOMAIN_CONFIGS.copy()
        self._lock = threading.RLock()
        self._persistence_path = state_persistence_path
        self._running = True
        
        if self._persistence_path:
            self._load_state()
            self._start_persistence_thread()
        
        logger.info("🚦 AdvancedRateLimiter v3.0 inicializado")
    
    def _start_persistence_thread(self):
        """Inicia thread para persistência periódica de estado."""
        def persist_worker():
            while self._running:
                time.sleep(60)  # Persiste a cada minuto
                if self._running:
                    self._save_state()
        
        thread = threading.Thread(target=persist_worker, daemon=True)
        thread.start()
    
    def _get_bucket(self, domain: str) -> TokenBucket:
        """Obtém ou cria token bucket para domínio."""
        with self._lock:
            if domain not in self._buckets:
                config = self._configs.get(domain, _DEFAULT_CONFIG)
                # Capacidade = max_requests * burst_multiplier
                capacity = int(config.max_requests * config.burst_multiplier)
                refill_rate = config.max_requests / config.window_seconds
                self._buckets[domain] = TokenBucket(capacity, refill_rate)
            return self._buckets[domain]
    
    def _get_circuit_breaker(self, domain: str) -> CircuitBreaker:
        """Obtém ou cria circuit breaker para domínio."""
        with self._lock:
            if domain not in self._circuit_breakers:
                config = self._configs.get(domain, _DEFAULT_CONFIG)
                self._circuit_breakers[domain] = CircuitBreaker(
                    failure_threshold=config.circuit_breaker_threshold,
                    timeout_seconds=config.circuit_breaker_timeout
                )
            return self._circuit_breakers[domain]
    
    def _get_metrics(self, domain: str) -> DomainMetrics:
        with self._lock:
            if domain not in self._metrics:
                self._metrics[domain] = DomainMetrics()
            return self._metrics[domain]
    
    def _domain(self, url: str) -> str:
        """Extrai domínio da URL."""
        try:
            from urllib.parse import urlparse
            netloc = urlparse(url).netloc.split(":")[0].lower()
            # Remove subdomínios comuns
            if netloc.startswith("api."):
                netloc = netloc[4:]
            elif netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return "unknown"
    
    def acquire(self, url: str, block: bool = True, timeout: float = 30.0) -> Tuple[bool, Optional[float]]:
        """
        Adquire permissão para fazer requisição.
        
        Args:
            url: URL da requisição
            block: Se deve bloquear até liberar
            timeout: Timeout máximo para espera (se block=True)
        
        Returns:
            Tuple[autorizado, tempo_espera]
        """
        domain = self._domain(url)
        metrics = self._get_metrics(domain)
        
        # Verifica circuit breaker
        cb = self._get_circuit_breaker(domain)
        if not cb.allow_request():
            metrics.record_failure()
            logger.warning(f"Circuit breaker OPEN for {domain} - request blocked")
            return False, None
        
        bucket = self._get_bucket(domain)
        start_wait = time.time()
        
        while True:
            if bucket.consume(1):
                metrics.record_success()
                wait_time = time.time() - start_wait
                return True, wait_time
            
            if not block:
                metrics.record_rate_limited()
                return False, None
            
            # Calcula tempo de espera baseado nos tokens disponíveis
            available = bucket.get_available_tokens()
            if available <= 0:
                # Estima tempo para próximo token
                config = self._configs.get(domain, _DEFAULT_CONFIG)
                wait = 1.0 / (config.max_requests / config.window_seconds)
                wait = min(wait, timeout - (time.time() - start_wait))
            else:
                wait = 0.1
            
            if wait <= 0 or (time.time() - start_wait) >= timeout:
                metrics.record_rate_limited()
                logger.debug(f"Rate limit timeout for {domain} after {timeout}s")
                return False, None
            
            logger.debug(f"Rate limited {domain} - waiting {wait:.2f}s")
            time.sleep(wait)
    
    def record_success(self, url: str, response_time_ms: float = 0):
        """Registra sucesso de requisição para métricas e circuit breaker."""
        domain = self._domain(url)
        metrics = self._get_metrics(domain)
        metrics.record_success(response_time_ms)
        
        cb = self._get_circuit_breaker(domain)
        cb.record_success()
    
    def record_failure(self, url: str):
        """Registra falha de requisição para métricas e circuit breaker."""
        domain = self._domain(url)
        metrics = self._get_metrics(domain)
        metrics.record_failure()
        
        cb = self._get_circuit_breaker(domain)
        cb.record_failure()
    
    def get_metrics(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Retorna métricas de rate limiting."""
        with self._lock:
            if domain:
                metrics = self._metrics.get(domain)
                return {
                    "domain": domain,
                    "metrics": metrics.to_dict() if metrics else None,
                    "config": {
                        "max_requests": self._configs.get(domain, _DEFAULT_CONFIG).max_requests,
                        "window_seconds": self._configs.get(domain, _DEFAULT_CONFIG).window_seconds
                    },
                    "circuit_breaker": self._circuit_breakers.get(domain, CircuitBreaker()).get_state_info() if domain in self._circuit_breakers else None
                }
            
            return {
                "total_domains": len(self._metrics),
                "metrics": {d: m.to_dict() for d, m in self._metrics.items()}
            }
    
    def _save_state(self):
        """Salva estado atual para disco."""
        if not self._persistence_path:
            return
        
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    domain: metrics.to_dict()
                    for domain, metrics in self._metrics.items()
                },
                "circuit_breakers": {
                    domain: cb.get_state_info()
                    for domain, cb in self._circuit_breakers.items()
                }
            }
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save rate limiter state: {e}")
    
    def _load_state(self):
        """Carrega estado do disco."""
        if not self._persistence_path or not self._persistence_path.exists():
            return
        
        try:
            state = json.loads(self._persistence_path.read_text())
            # Restaura métricas
            for domain, metrics_data in state.get("metrics", {}).items():
                metrics = DomainMetrics()
                metrics.total_requests = metrics_data.get("total_requests", 0)
                metrics.successful_requests = metrics_data.get("successful_requests", 0)
                metrics.failed_requests = metrics_data.get("failed_requests", 0)
                metrics.rate_limited_requests = metrics_data.get("rate_limited_requests", 0)
                metrics.dedup_hits = metrics_data.get("dedup_hits", 0)
                metrics.avg_response_time_ms = metrics_data.get("avg_response_time_ms", 0)
                metrics.consecutive_failures = metrics_data.get("consecutive_failures", 0)
                self._metrics[domain] = metrics
            
            logger.info(f"Loaded rate limiter state: {len(self._metrics)} domains")
        except Exception as e:
            logger.warning(f"Failed to load rate limiter state: {e}")
    
    def shutdown(self):
        """Finaliza o rate limiter, salvando estado."""
        self._running = False
        self._save_state()
        logger.info("Rate limiter shutdown complete")


# =============================================================================
# Smart URL Deduplicator
# =============================================================================

class SmartURLDeduplicator:
    """
    Deduplicador inteligente de URLs com cache persistente e normalização.
    Thread-safe.
    """

    def __init__(
        self,
        ttl_seconds: float = 300.0,
        max_entries: int = 10000,
        persistence_path: Optional[Path] = None,
        normalize_urls: bool = True
    ):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.normalize_urls = normalize_urls
        self.persistence_path = persistence_path
        
        self._seen: Dict[str, Tuple[float, int]] = {}  # url_key -> (timestamp, hit_count)
        self._lock = threading.RLock()
        
        self._load_state()
        
        # Thread de limpeza periódica
        self._running = True
        self._start_cleanup_thread()
        
        logger.info(f"🔗 SmartURLDeduplicator v3.0 inicializado (TTL={ttl_seconds}s)")
    
    def _normalize_url(self, url: str) -> str:
        """Normaliza URL para melhor deduplicação."""
        if not self.normalize_urls:
            return url
        
        try:
            from urllib.parse import urlparse, parse_qs, urlunparse
            
            parsed = urlparse(url)
            
            # Remove parâmetros de tracking comuns
            query_params = parse_qs(parsed.query)
            tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 
                              'ref', 'source', 'utm_id', 'fbclid', 'gclid', 'msclkid', '_ga'}
            
            for param in tracking_params:
                query_params.pop(param, None)
            
            # Reconstroi query string sem parâmetros de tracking
            new_query = '&'.join(f"{k}={v[0]}" for k, v in query_params.items())
            
            # Remove fragmento (#anchor)
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ''  # Sem fragmento
            ))
        except Exception:
            return url
    
    def _key(self, url: str) -> str:
        """Gera chave única para URL."""
        normalized = self._normalize_url(url)
        return hashlib.sha256(normalized.encode()).hexdigest()[:20]
    
    def _start_cleanup_thread(self):
        """Inicia thread de limpeza periódica."""
        def cleanup_worker():
            while self._running:
                time.sleep(60)  # Limpa a cada minuto
                if self._running:
                    self._cleanup_expired()
        
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()
    
    def _cleanup_expired(self):
        """Remove entradas expiradas."""
        now = time.time()
        with self._lock:
            expired = [
                key for key, (ts, _) in self._seen.items()
                if now - ts >= self.ttl
            ]
            for key in expired:
                del self._seen[key]
            
            if expired:
                logger.debug(f"Cleaned {len(expired)} expired URLs from deduplicator")
    
    def _evict_oldest(self):
        """Remove entrada mais antiga se cache estiver cheio."""
        if len(self._seen) < self.max_entries:
            return
        
        oldest = min(self._seen.items(), key=lambda x: x[1][0])
        del self._seen[oldest[0]]
    
    def is_duplicate(self, url: str) -> Tuple[bool, int]:
        """
        Verifica se URL já foi vista.
        
        Returns:
            Tuple[é_duplicada, hit_count]
        """
        key = self._key(url)
        now = time.time()
        
        with self._lock:
            entry = self._seen.get(key)
            if entry is not None:
                ts, hit_count = entry
                if now - ts < self.ttl:
                    return True, hit_count
                else:
                    # Expirada, remove
                    del self._seen[key]
            return False, 0
    
    def mark(self, url: str) -> int:
        """
        Marca URL como visitada.
        
        Returns:
            Número de vezes que esta URL já foi visitada (1-indexed)
        """
        key = self._key(url)
        now = time.time()
        
        with self._lock:
            entry = self._seen.get(key)
            if entry:
                ts, hit_count = entry
                if now - ts < self.ttl:
                    hit_count += 1
                    self._seen[key] = (now, hit_count)
                    return hit_count
                else:
                    # Expirada, recria
                    self._seen[key] = (now, 1)
                    return 1
            else:
                # Nova entrada
                self._seen[key] = (now, 1)
                self._evict_oldest()
                return 1
    
    def check_and_mark(self, url: str) -> Tuple[bool, int]:
        """
        Verifica e marca URL em uma operação atômica.
        
        Returns:
            Tuple[é_duplicada, hit_count]
        """
        is_dup, hit_count = self.is_duplicate(url)
        if is_dup:
            return True, hit_count
        new_hit_count = self.mark(url)
        return False, new_hit_count
    
    def clear(self) -> None:
        """Limpa todo o cache de deduplicação."""
        with self._lock:
            self._seen.clear()
        logger.info("URL deduplicator cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do deduplicador."""
        with self._lock:
            total_entries = len(self._seen)
            total_hits = sum(hc for _, hc in self._seen.values())
            
            return {
                "tracked_urls": total_entries,
                "total_hits": total_hits,
                "max_entries": self.max_entries,
                "usage_percent": round(total_entries / self.max_entries * 100, 2) if self.max_entries > 0 else 0,
                "ttl_seconds": self.ttl,
                "normalize_urls": self.normalize_urls
            }
    
    def _save_state(self):
        """Salva estado para disco."""
        if not self.persistence_path:
            return
        
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "entries": [
                    {"key": k, "timestamp": ts, "hit_count": hc}
                    for k, (ts, hc) in self._seen.items()
                ]
            }
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self.persistence_path.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save deduplicator state: {e}")
    
    def _load_state(self):
        """Carrega estado do disco."""
        if not self.persistence_path or not self.persistence_path.exists():
            return
        
        try:
            state = json.loads(self.persistence_path.read_text())
            now = time.time()
            for entry in state.get("entries", []):
                ts = entry.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts).timestamp()
                if now - ts < self.ttl:
                    self._seen[entry["key"]] = (ts, entry.get("hit_count", 1))
            
            logger.info(f"Loaded deduplicator state: {len(self._seen)} URLs")
        except Exception as e:
            logger.warning(f"Failed to load deduplicator state: {e}")
    
    def shutdown(self):
        """Finaliza o deduplicador, salvando estado."""
        self._running = False
        self._save_state()
        logger.info("URL deduplicator shutdown complete")


# =============================================================================
# Instâncias Globais
# =============================================================================

_state_dir = Path("atena_evolution/rate_limiter_state")
_state_dir.mkdir(parents=True, exist_ok=True)

_rate_limiter = AdvancedRateLimiter(state_persistence_path=_state_dir / "rate_limiter_state.json")
_deduplicator = SmartURLDeduplicator(
    ttl_seconds=120.0,
    max_entries=10000,
    persistence_path=_state_dir / "deduplicator_state.json",
    normalize_urls=True
)


def install_on_internet_challenge() -> bool:
    """
    Monkey-patch _fetch_raw no internet_challenge para adicionar
    rate limiting, deduplicação e circuit breaker.
    
    Returns:
        True se instalado com sucesso
    """
    try:
        import core.internet_challenge as ic
        
        original_fetch = ic._fetch_raw
        
        def guarded_fetch(url: str, timeout: int = 15) -> str:
            """Wrapper com rate limiting e deduplicação."""
            # 1. Deduplicação
            is_dup, hit_count = _deduplicator.check_and_mark(url)
            if is_dup:
                logger.debug(f"Dedup: URL already visited ({hit_count}x): {url[:80]}")
                return ""
            
            # 2. Rate limiting
            allowed, wait_time = _rate_limiter.acquire(url, block=True, timeout=30.0)
            if not allowed:
                logger.warning(f"Rate limit timeout for {url[:80]}")
                return ""
            
            # 3. Executa requisição
            start_time = time.time()
            try:
                result = original_fetch(url, timeout=timeout)
                elapsed_ms = (time.time() - start_time) * 1000
                _rate_limiter.record_success(url, elapsed_ms)
                return result
            except Exception as e:
                _rate_limiter.record_failure(url)
                logger.error(f"Request failed for {url[:80]}: {e}")
                raise
        
        ic._fetch_raw = guarded_fetch
        logger.info("✅ RateLimiter + Deduplicator + Circuit Breaker installed on internet_challenge._fetch_raw")
        return True
        
    except Exception as exc:
        logger.warning(f"Failed to install rate limiter: {exc}")
        return False


def get_rate_limiter() -> AdvancedRateLimiter:
    return _rate_limiter


def get_deduplicator() -> SmartURLDeduplicator:
    return _deduplicator


def shutdown():
    """Finaliza todos os componentes."""
    _rate_limiter.shutdown()
    _deduplicator.shutdown()
    logger.info("Rate limiter and deduplicator shut down")


# =============================================================================
# Demonstração e CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Advanced Rate Limiter v3.0")
    parser.add_argument("--install", action="store_true", help="Instala monkey-patch no internet_challenge")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas atuais")
    parser.add_argument("--clear-dedup", action="store_true", help="Limpa cache de deduplicação")
    parser.add_argument("--test", type=str, help="Testa rate limiting para uma URL")
    
    args = parser.parse_args()
    
    if args.install:
        success = install_on_internet_challenge()
        print(f"Installation: {'✅ Success' if success else '❌ Failed'}")
        return 0
    
    if args.stats:
        print("\n📊 Rate Limiter Statistics:")
        print("-" * 50)
        metrics = _rate_limiter.get_metrics()
        for domain, m in metrics.get("metrics", {}).items():
            print(f"\n🌐 {domain}:")
            print(f"   Total requests: {m['total_requests']}")
            print(f"   Success rate: {m['success_rate']*100:.1f}%")
            print(f"   Avg response: {m['avg_response_time_ms']:.1f}ms")
            print(f"   Rate limited: {m['rate_limited_requests']}")
        
        print("\n🔗 Deduplicator Statistics:")
        print("-" * 50)
        dedup_stats = _deduplicator.get_stats()
        for k, v in dedup_stats.items():
            print(f"   {k}: {v}")
        return 0
    
    if args.clear_dedup:
        _deduplicator.clear()
        print("✅ Deduplicator cache cleared")
        return 0
    
    if args.test:
        url = args.test
        print(f"\n🧪 Testing URL: {url}")
        
        is_dup, hit_count = _deduplicator.check_and_mark(url)
        print(f"Deduplication: {'DUPLICATE' if is_dup else 'NEW'} (hit count: {hit_count})")
        
        allowed, wait = _rate_limiter.acquire(url, block=False)
        print(f"Rate limit: {'ALLOWED' if allowed else 'BLOCKED'} (wait: {wait:.2f}s)")
        
        return 0
    
    print("Use --help for available options")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
