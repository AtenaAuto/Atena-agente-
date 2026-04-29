"""Testa RateLimiter e URLDeduplicator."""
from core.atena_rate_limiter import RateLimiter, URLDeduplicator

def test_rate_limiter_allows_under_limit():
    rl = RateLimiter()
    rl._buckets.clear()
    # primeira requisição deve passar imediatamente
    ok = rl.acquire("https://example.com/test", block=False)
    assert ok

def test_dedup_marks_and_detects():
    d = URLDeduplicator(ttl_seconds=60)
    url = "https://api.github.com/repos/test"
    assert not d.check_and_mark(url)  # nova → não é duplicata
    assert d.check_and_mark(url)      # já marcada → duplicata

def test_dedup_expires():
    import time
    d = URLDeduplicator(ttl_seconds=0.05)
    url = "https://example.com/expire"
    d.check_and_mark(url)
    time.sleep(0.1)
    assert not d.check_and_mark(url)  # expirou → nova

def test_dedup_clear():
    d = URLDeduplicator(ttl_seconds=60)
    d.check_and_mark("https://a.com")
    d.check_and_mark("https://b.com")
    d.clear()
    assert d.stats()["tracked_urls"] == 0
