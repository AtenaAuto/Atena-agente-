#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_terminal_assistant as ta


def test_is_internet_request_detects_report_request():
    assert ta._is_internet_request("Me dá um relatório completo da internet sobre IA") is True


def test_is_internet_request_detects_plain_pesquisa_prompt():
    assert ta._is_internet_request("pesquisa que dia que o santos joga") is True


def test_extract_internet_topic_from_complete_report_prompt():
    topic = ta._extract_internet_topic(
        "Pesquise na internet e entregue um relatório completo sobre ai agent safety benchmarks 2026"
    )
    assert topic == "ai agent safety benchmarks 2026"


def test_run_user_internet_research_returns_complete_report(monkeypatch):
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "weighted_confidence": 0.88,
            "recommendation": "Consolidar síntese final",
            "all_sources": [
                {
                    "source": "github",
                    "ok": True,
                    "quality_score": 0.91,
                    "details": {"top_repos": [{"full_name": "org/agent-framework"}]},
                },
                {
                    "source": "crossref",
                    "ok": False,
                    "quality_score": 0.0,
                    "details": {"error": "timeout"},
                },
            ],
            "synthesis": {
                "coverage_summary": "1/2 fontes responderam",
                "next_action": "Refinar a query",
                "release_risk": "medium",
            },
        },
    )

    report = ta.run_user_internet_research("pesquise na internet sobre ai agents")

    assert "Resultado da pesquisa" in report
    assert "org/agent-framework" in report
    assert "crossref" not in report
    assert "Fonte:" not in report


def test_run_user_internet_research_without_topic_guides_user():
    report = ta.run_user_internet_research("/internet")
    assert "Use `/internet <tema>`" in report


def test_run_user_internet_research_prioritizes_sports_schedule(monkeypatch):
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {
            "all_sources": [
                {
                    "source": "thesportsdb",
                    "ok": True,
                    "details": {
                        "events": [
                            {"title": "Santos vs Palmeiras", "date": "2026-04-25"},
                            {"title": "Corinthians vs Santos", "date": "2026-05-02"},
                        ]
                    },
                },
            ]
        },
    )
    report = ta.run_user_internet_research("pesquisa que dia o santos joga")
    assert "Próximos jogos encontrados" in report
    assert "2026-04-25: Santos vs Palmeiras" in report


def test_run_user_internet_research_sports_schedule_without_relevant_match(monkeypatch):
    monkeypatch.setattr(ta, "_google_news_fallback_results", lambda topic, limit=5: [])
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {
            "all_sources": [
                {
                    "source": "thesportsdb",
                    "ok": True,
                    "details": {"events": [{"title": "Time X vs Time Y", "date": "2026-04-25"}]},
                },
            ]
        },
    )
    report = ta.run_user_internet_research("pesquisa que dia o santos joga")
    assert "Não encontrei um calendário confiável" in report


def test_run_user_internet_research_sports_schedule_without_sports_source(monkeypatch):
    monkeypatch.setattr(
        ta,
        "_google_news_fallback_results",
        lambda topic, limit=5: ["- Flamengo enfrenta Time X\n  https://news.google.com/example"],
    )
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {"all_sources": [{"source": "wikipedia", "ok": True, "details": {"title": "Santos"}}]},
    )
    report = ta.run_user_internet_research("pesquisa que dia o santos joga")
    assert "fallback Google" in report
    assert "news.google.com/example" in report


def test_run_user_internet_research_sports_schedule_ignores_filler_terms(monkeypatch):
    monkeypatch.setattr(ta, "_google_news_fallback_results", lambda topic, limit=5: [])
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {
            "all_sources": [
                {
                    "source": "thesportsdb",
                    "ok": True,
                    "details": {"events": [{"title": "Flamengo vs Vasco", "date": "2026-05-04"}]},
                },
            ]
        },
    )
    report = ta.run_user_internet_research("pesquisa pra mim que dia o flamengo joga")
    assert "Próximos jogos encontrados" in report
    assert "2026-05-04: Flamengo vs Vasco" in report


def test_run_user_internet_research_general_fallback_google(monkeypatch):
    monkeypatch.setattr(
        ta,
        "_google_news_fallback_results",
        lambda topic, limit=5: ["- Resultado Google\n  https://news.google.com/result"],
    )
    monkeypatch.setattr(ta, "run_internet_challenge", lambda topic: {"all_sources": []})
    report = ta.run_user_internet_research("pesquise na internet sobre assunto sem fonte")
    assert "Resultado Google" in report
