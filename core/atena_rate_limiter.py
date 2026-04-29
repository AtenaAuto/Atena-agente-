#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Rate Limiter + Deduplicador de URLs
Protege contra spam de API e chamadas repetidas em janelas curtas.
Instalado como monkey-patch em _fetch_raw do internet_challenge.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("atena.rate_limiter")

# ── Configuração por domínio ──────────────────────────────────────────────────
# (max_requests, janela_segundos)
_DOMAIN_LIMITS: dict[str, tuple[int, float]] = {
    "api.github.com":            (10, 60.0),
    "en.wikipedia.org":          (15, 60.0),
    "registry.npmjs.org":        (20, 60.0),
    "pub.dev":                   (10, 60.0),
    "crates.io":                 (10, 60.0),
    "api.stackexchange.com":     (10, 60.0),
    "export.arxiv.org":          (5,  60.0),
    "openlibrary.org":           (10, 60.0),
    "api.semanticscholar.org":   (5,  60.0),
    "api.publicapis.org":        (5,  60.0),
    "poetrydb.org":              (10, 60.0),
}
_DEFAULT_LIMIT = (30, 60.0)   # fallback genérico


class RateLimiter:
    """
    Token bucket por domínio — thread-safe.
    Bloqueia (sleep) até haver capacidade disponível.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.split(":")[0].lower()
        except Exception:
            return "unknown"

    def acquire(self, url: str, block: bool = True) -> bool:
        """
        Adquire permissão para fazer a requisição.
        Se block=True, dorme até liberar slot.
        Retorna True se autorizado, False se rejeitado (block=False).
        """
        domain = self._domain(url)
        max_req, window = _DOMAIN_LIMITS.get(domain, _DEFAULT_LIMIT)

        while True:
            now = time.monotonic()
            with self._lock:
                bucket = self._buckets[domain]
                # Remove timestamps fora da janela
                while bucket and now - bucket[0] >= window:
                    bucket.popleft()

                if len(bucket) < max_req:
                    bucket.append(now)
                    return True

                if not block:
                    return False

                # Calcula quanto tempo esperar
                wait = window - (now - bucket[0]) + 0.01

            logger.debug("rate limit %s — aguardando %.1fs", domain, wait)
            time.sleep(max(0.01, wait))


class URLDeduplicator:
    """
    Evita requisições duplicadas para a mesma URL dentro de uma janela TTL.
    Thread-safe.
    """

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._seen: dict[str, float] = {}   # url_hash → timestamp
        self._lock = threading.Lock()

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def is_duplicate(self, url: str) -> bool:
        key = self._key(url)
        now = time.monotonic()
        with self._lock:
            ts = self._seen.get(key)
            if ts is not None and now - ts < self._ttl:
                return True
            return False

    def mark(self, url: str) -> None:
        key = self._key(url)
        now = time.monotonic()
        with self._lock:
            self._seen[key] = now
            # Evicção simples por tamanho
            if len(self._seen) > self._max:
                # Remove o mais antigo
                oldest = min(self._seen, key=lambda k: self._seen[k])
                del self._seen[oldest]

    def check_and_mark(self, url: str) -> bool:
        """Retorna True se é duplicada (não marca). False se nova (marca)."""
        if self.is_duplicate(url):
            return True
        self.mark(url)
        return False

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"tracked_urls": len(self._seen), "ttl_s": self._ttl}


# ── Instâncias globais ────────────────────────────────────────────────────────
_rate_limiter  = RateLimiter()
_deduplicator  = URLDeduplicator(ttl_seconds=120.0)


def install_on_internet_challenge() -> bool:
    """
    Monkey-patches _fetch_raw no internet_challenge para adicionar
    rate limiting e deduplicação automaticamente.
    Retorna True se instalado com sucesso.
    """
    try:
        import core.internet_challenge as ic

        original_fetch = ic._fetch_raw

        def guarded_fetch(url: str, timeout: int = 15) -> str:
            # 1. Deduplicação
            if _deduplicator.check_and_mark(url):
                logger.debug("dedup: URL já visitada recentemente: %s", url[:80])
                return ""   # retorna vazio — o chamador trata como fonte vazia

            # 2. Rate limiting
            _rate_limiter.acquire(url, block=True)

            return original_fetch(url, timeout=timeout)

        ic._fetch_raw = guarded_fetch  # type: ignore[attr-defined]
        logger.info("✅ RateLimiter + Deduplicador instalados em internet_challenge._fetch_raw")
        return True
    except Exception as exc:
        logger.warning("falha ao instalar rate limiter: %s", exc)
        return False


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def get_deduplicator() -> URLDeduplicator:
    return _deduplicator
