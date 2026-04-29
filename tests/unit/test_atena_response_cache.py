"""Testes para AtenaResponseCache."""
import time
import pytest
from core.atena_response_cache import AtenaResponseCache


def test_basic_set_get():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=60)
    cache.set("oi", "tudo bem", context="ctx", provider="test")
    result = cache.get("oi", context="ctx", provider="test")
    assert result == "tudo bem"


def test_miss_returns_none():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=60)
    assert cache.get("não existe", provider="x") is None


def test_ttl_expiry():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=0.05)
    cache.set("prompt", "resposta", provider="test")
    time.sleep(0.1)
    assert cache.get("prompt", provider="test") is None


def test_lru_eviction():
    cache = AtenaResponseCache(max_size=3, ttl_seconds=60)
    for i in range(4):
        cache.set(f"p{i}", f"r{i}", provider="t")
    # p0 deve ter sido eviccionado
    assert cache.get("p0", provider="t") is None
    assert cache.get("p3", provider="t") == "r3"


def test_disabled_cache():
    cache = AtenaResponseCache(enabled=False)
    cache.set("prompt", "resposta", provider="test")
    assert cache.get("prompt", provider="test") is None


def test_stats():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=60)
    cache.set("x", "y", provider="p")
    cache.get("x", provider="p")
    cache.get("miss", provider="p")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5


def test_clear():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=60)
    cache.set("k", "v", provider="p")
    cache.clear()
    assert cache.get("k", provider="p") is None
    assert cache.stats()["size"] == 0


def test_purge_expired():
    cache = AtenaResponseCache(max_size=10, ttl_seconds=0.05)
    cache.set("k1", "v1", provider="p")
    cache.set("k2", "v2", provider="p")
    time.sleep(0.1)
    removed = cache.purge_expired()
    assert removed == 2
