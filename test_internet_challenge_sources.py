#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import internet_challenge


def test_internet_challenge_collects_extended_sources(monkeypatch):
    def _fake_fetch_json(url: str, timeout: int = 15):  # noqa: ARG001
        if "wikipedia.org" in url:
            return {"title": "AI Agent", "extract": "Resumo"}
        if "api.github.com/search/repositories" in url:
            return {"items": [{"full_name": "org/repo", "stargazers_count": 123}]}
        if "hn.algolia.com" in url:
            return {"hits": [{"title": "HN post", "points": 77}]}
        if "api.crossref.org" in url:
            return {"message": {"items": [{"title": ["Paper X"], "DOI": "10.1/x", "is-referenced-by-count": 42}]}}
        if "api.openalex.org" in url:
            return {"results": [{"display_name": "OpenAlex Work", "cited_by_count": 9}]}
        if "api.stackexchange.com" in url:
            return {"items": [{"title": "SO Q", "score": 5}]}
        if "reddit.com/search.json" in url:
            return {"data": {"children": [{"data": {"title": "Reddit topic", "score": 15}}]}}
        if "registry.npmjs.org" in url:
            return {"objects": [{"package": {"name": "agent-kit", "version": "1.0.0"}}]}
        if "europepmc" in url:
            return {"resultList": {"result": [{"title": "EPMC Paper", "journalTitle": "Nature"}]}}
        raise AssertionError(f"URL não mockada: {url}")

    def _fake_fetch_text(url: str, timeout: int = 15):  # noqa: ARG001
        if "export.arxiv.org" not in url:
            raise AssertionError(f"URL não mockada para texto: {url}")
        return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>arXiv Paper</title></entry>
</feed>"""

    monkeypatch.setattr(internet_challenge, "_fetch_json", _fake_fetch_json)
    monkeypatch.setattr(internet_challenge, "_fetch_text", _fake_fetch_text)

    result = internet_challenge.run_internet_challenge("ai agents")

    assert result["status"] == "ok"
    assert result["confidence"] == 1.0
    assert result["weighted_confidence"] == 1.0
    assert result["source_count"] == 10
    source_names = [s["source"] for s in result["sources"]]
    assert source_names == [
        "wikipedia",
        "github",
        "hackernews",
        "arxiv",
        "crossref",
        "openalex",
        "stackoverflow",
        "reddit",
        "npm",
        "europepmc",
    ]
    for source in result["sources"]:
        assert "quality_score" in source
        assert "weight" in source
