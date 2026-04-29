#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Cache de Respostas LLM
Cache LRU com TTL para evitar chamadas repetidas ao LLM.
"""
from __future__ import annotations

import hashlib
import time
import threading
import logging
from collections import OrderedDict
from typing import Optional, Tuple

logger = logging.getLogger("atena.response_cache")


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: str, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl if ttl > 0 else float("inf")

    def is_alive(self) -> bool:
        return time.monotonic() < self.expires_at


class AtenaResponseCache:
    """
    Cache thread-safe LRU com TTL para respostas do LLM.

    Parâmetros
    ----------
    max_size : int
        Número máximo de entradas no cache. Entradas mais antigas são
        expulsas quando o limite é atingido (política LRU).
    ttl_seconds : float
        Tempo de vida de cada entrada em segundos. Use 0 para sem expiração.
    enabled : bool
        Ativa/desativa o cache sem precisar remover o wrapper.
    """

    def __init__(
        self,
        max_size: int = 256,
        ttl_seconds: float = 600.0,
        enabled: bool = True,
    ) -> None:
        self.max_size = max(1, max_size)
        self.ttl = ttl_seconds
        self.enabled = enabled
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    # ── API pública ─────────────────────────────────────────────────────────

    def get(self, prompt: str, context: str = "", provider: str = "") -> Optional[str]:
        """Retorna resposta cacheada ou None se não encontrada/expirada."""
        if not self.enabled:
            return None
        key = self._make_key(prompt, context, provider)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not entry.is_alive():
                del self._store[key]
                self._misses += 1
                return None
            # Move para o final (mais recente)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, prompt: str, response: str, context: str = "", provider: str = "") -> None:
        """Armazena resposta no cache."""
        if not self.enabled:
            return
        key = self._make_key(prompt, context, provider)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = _CacheEntry(response, self.ttl)
            # Evicção LRU
            while len(self._store) > self.max_size:
                oldest_key, _ = next(iter(self._store.items()))
                del self._store[oldest_key]
                logger.debug("cache: evicção LRU de %s", oldest_key[:16])

    def invalidate(self, prompt: str, context: str = "", provider: str = "") -> None:
        """Remove uma entrada específica do cache."""
        key = self._make_key(prompt, context, provider)
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Limpa todo o cache."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        """Retorna estatísticas de uso do cache."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "size": len(self._store),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "enabled": self.enabled,
            }

    def purge_expired(self) -> int:
        """Remove entradas expiradas. Retorna quantidade removida."""
        removed = 0
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if not v.is_alive()]
            for k in expired_keys:
                del self._store[k]
                removed += 1
        if removed:
            logger.debug("cache: %d entrada(s) expirada(s) removida(s)", removed)
        return removed

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _make_key(prompt: str, context: str, provider: str) -> str:
        raw = f"{provider}|{context[:200]}|{prompt}"
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


# Instância global compartilhada — pode ser importada diretamente
_global_cache: Optional[AtenaResponseCache] = None


def get_global_cache(max_size: int = 256, ttl_seconds: float = 600.0, enabled: bool = True) -> AtenaResponseCache:
    """Retorna (e inicializa se necessário) o cache global de respostas."""
    global _global_cache
    if _global_cache is None:
        _global_cache = AtenaResponseCache(max_size=max_size, ttl_seconds=ttl_seconds, enabled=enabled)
    return _global_cache
