from core.enterprise_memory_rag import TenantMemoryRAG, build_reasoning_trace


def test_memory_upsert_query_and_retention(tmp_path):
    store = TenantMemoryRAG(tmp_path / "memory.db")
    up = store.upsert(
        tenant_id="t1",
        content="Use cache distribuído para reduzir latência p95",
        citation="runbook://cache",
        classification="internal",
        tags=["cache"],
    )
    assert up["status"] == "ok"

    result = store.query("t1", "como reduzir latência p95", top_k=2)
    assert result["status"] == "ok"
    assert result["citations_required"] is True
    assert len(result["results"]) >= 1

    purged = store.purge_expired({"public": 0, "internal": 0, "confidential": 0, "default": 0})
    assert purged["status"] == "ok"


def test_reasoning_trace_redacts_secret():
    trace = build_reasoning_trace(
        steps=["usar token ghp_ABCDEF1234567890XYZ1234"],
        citations=["doc://security"],
    )
    assert trace["status"] == "ok"
    assert "[REDACTED_SECRET]" in trace["steps"][0]


def test_reasoning_trace_redacts_shorter_github_token_like_string():
    trace = build_reasoning_trace(
        steps=["registrar credencial ghp_ABCDEF1234567890XYZ para auditoria"],
        citations=["doc://security"],
    )
    assert trace["status"] == "ok"
    assert "[REDACTED_SECRET]" in trace["steps"][0]
