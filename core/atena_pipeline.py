#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline automatizado ATENA: objetivo -> web -> análise -> relatório."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import quote_plus
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_browser_agent import AtenaBrowserAgent
from core.atena_mission_runner import run_async_mission
from core.atena_runtime_contracts import MissionOutcome
from core.atena_telemetry import emit_event

ATENA_RELEVANCE_TERMS = {
    "atena",
    "atenaauto",
    "agent",
    "ai",
    "automation",
    "orchestrator",
    "pipeline",
    "github",
}

NOISE_TERMS = {
    "your",
    "view",
    "search",
    "reload",
    "loading",
    "navigation",
    "support",
    "community",
    "actions",
}


def analyze_text(text: str) -> dict:
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in text.split()]
    tokens = [t for t in tokens if is_valid_term(t)]
    common = Counter(tokens).most_common(15)
    return {
        "chars": len(text),
        "words": len(text.split()),
        "top_terms": common,
    }


def is_valid_term(token: str) -> bool:
    if len(token) <= 3 or len(token) >= 40:
        return False
    if token in NOISE_TERMS:
        return False
    if token.startswith(("&lt", "&gt", "lt;", "gt;")):
        return False
    if token.startswith(("http://", "https://", "www.")):
        return False
    if token.count("_") >= 2 or token.count("-") >= 3:
        return False
    if re.search(r"[{}[\]<>:=]", token):
        return False
    if re.search(r"\d{4,}", token):
        return False
    return True


def clean_extracted_text(html: str) -> str:
    """Limpeza simples de boilerplate/JS para melhorar sinal semântico."""
    # Remove blocos que raramente carregam conteúdo textual útil para resumo.
    text = re.sub(r"(?is)<(script|style|noscript|svg|canvas|template)[^>]*>.*?</\1>", " ", html)
    # Remove qualquer tag restante.
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    # Remove URLs e blobs longos comuns de JSON/config embutidos.
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b[a-z0-9_]{30,}\b", " ", text)
    # Normaliza espaços.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_text_via_http(url: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            url,
            timeout=(8, 20),
            headers={"User-Agent": "ATENA/1.0 (+https://github.com/AtenaAuto/ATENA-)"},
        )
        if resp.status_code >= 400:
            return False, ""
        html = resp.text
        text = clean_extracted_text(html)
        return True, text
    except Exception:
        return False, ""


def score_source_relevance(source: str, text: str, objective: str) -> float:
    sample = f"{source} {objective} {text[:3000]}".lower()
    score = 0.0
    for term in ATENA_RELEVANCE_TERMS:
        if term in sample:
            score += 0.11
    if "github.com/atenaauto/atena-" in sample:
        score += 0.35
    if "the-athena-codex" in sample:
        score -= 0.2
    return round(max(0.0, min(1.0, score)), 3)


def normalize_search_result_url(raw_url: str) -> str:
    """
    Normaliza URL de resultado da busca:
    - resolve redirects do DDG (/l/?uddg=...)
    - remove trackers básicos
    """
    url = raw_url.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return url


def fetch_search_links(query: str, max_links: int = 8, per_domain_limit: int = 2) -> list[str]:
    """
    Busca links públicos via DuckDuckGo HTML (sem API key), retornando
    uma lista de fontes para análise multi-fonte.
    """
    try:
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(
            search_url,
            timeout=(8, 20),
            headers={"User-Agent": "ATENA/1.0 (+https://github.com/AtenaAuto/ATENA-)"},
        )
        if resp.status_code >= 400:
            return []
        html = resp.text
        # Prioriza links de resultados reais do DDG e faz fallback para links genéricos.
        candidates = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
        if not candidates:
            candidates = re.findall(r'href="(https?://[^"]+)"', html)

        links: list[str] = []
        domain_count: dict[str, int] = {}
        blocked_hosts = {"duckduckgo.com"}
        blocked_ext = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip")

        for raw_link in candidates:
            link = normalize_search_result_url(raw_link)
            if not link.startswith(("http://", "https://")):
                continue
            if link.lower().endswith(blocked_ext):
                continue
            parsed = urlparse(link)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            if any(h in host for h in blocked_hosts):
                continue
            if link not in links:
                if per_domain_limit > 0 and domain_count.get(host, 0) >= per_domain_limit:
                    continue
                links.append(link)
                domain_count[host] = domain_count.get(host, 0) + 1
            if len(links) >= max_links:
                break
        return links
    except Exception:
        return []


def collect_multi_source_text(
    sources: list[str],
    objective: str,
    max_chars_per_source: int = 5000,
    max_total_chars: int = 20000,
) -> tuple[bool, str, dict]:
    source_quality: list[dict] = []
    fetched_candidates: list[dict] = []
    for src in sources:
        ok_src, text_src = fetch_text_via_http(src)
        if ok_src and text_src:
            relevance = score_source_relevance(src, text_src, objective)
            quality = round(min(1.0, len(text_src.split()) / 1200), 3)
            fetched_candidates.append(
                {
                    "source": src,
                    "text": text_src,
                    "chars": len(text_src),
                    "words": len(text_src.split()),
                    "quality_score": quality,
                    "relevance_score": relevance,
                }
            )
        else:
            source_quality.append(
                {
                    "source": src,
                    "chars": 0,
                    "words": 0,
                    "quality_score": 0.0,
                    "relevance_score": 0.0,
                    "selected": False,
                }
            )

    selected = [c for c in fetched_candidates if c["relevance_score"] >= 0.30]
    if not selected:
        selected = [c for c in fetched_candidates if c["relevance_score"] >= 0.20]
    if not selected and fetched_candidates:
        selected = sorted(
            fetched_candidates,
            key=lambda c: (c["relevance_score"], c["quality_score"]),
            reverse=True,
        )[:1]

    selected_sources = {c["source"] for c in selected}
    for c in fetched_candidates:
        source_quality.append(
            {
                "source": c["source"],
                "chars": c["chars"],
                "words": c["words"],
                "quality_score": c["quality_score"] if c["source"] in selected_sources else 0.0,
                "relevance_score": c["relevance_score"],
                "selected": c["source"] in selected_sources,
            }
        )

    chunks: list[str] = []
    for c in selected:
        chunks.append(c["text"][:max_chars_per_source])
        if sum(len(x) for x in chunks) >= max_total_chars:
            break

    ok_any = len(selected) > 0
    success_sources = len(selected)
    failed_sources = max(0, len(sources) - success_sources)
    merged = "\n".join(chunks)[:max_total_chars]
    stats = {
        "requested_sources": len(sources),
        "successful_sources": success_sources,
        "failed_sources": failed_sources,
        "collected_chars": len(merged),
        "source_quality": source_quality,
    }
    return ok_any, merged, stats


async def run_pipeline(objective: str, base_query: str) -> dict:
    mission_id = f"pipeline:{int(datetime.utcnow().timestamp())}"
    emit_event("pipeline_start", mission_id, "started", objective=objective, base_query=base_query)
    report_holder: dict[str, dict] = {}

    async def _execute_pipeline() -> MissionOutcome:
        agent = AtenaBrowserAgent()
        query = agent.next_objective_query(objective, base_query)
        target_url = "https://github.com/AtenaAuto/ATENA-"
        screenshot_name: str | None = "atena_pipeline_screenshot.png"
        mode = "browser_agent"
        sources: list[str] = [target_url]
        collection_stats = {
            "requested_sources": 1,
            "successful_sources": 0,
            "failed_sources": 0,
            "collected_chars": 0,
        }

        try:
            await agent.launch(headless=True)
            ok = await agent.navigate(target_url, allow_repeat=True)
            text = await agent.get_text_content() if ok else ""
            await agent.take_screenshot(screenshot_name)
            await agent.close()
        except ModuleNotFoundError:
            mode = "http_fallback"
            screenshot_name = None
            links = fetch_search_links(query, max_links=8, per_domain_limit=2)
            if links:
                sources = links
            elif target_url not in sources:
                sources.append(target_url)
            ok, text, collection_stats = collect_multi_source_text(sources, objective=objective)
        except Exception:
            mode = "http_fallback"
            screenshot_name = None
            links = fetch_search_links(query, max_links=8, per_domain_limit=2)
            if links:
                sources = links
            elif target_url not in sources:
                sources.append(target_url)
            ok, text, collection_stats = collect_multi_source_text(sources, objective=objective)

        analysis = analyze_text(text[:12000]) if text else {"chars": 0, "words": 0, "top_terms": []}
        score = 0.85 if ok and analysis["words"] > 20 else 0.35
        agent.record_search_outcome(objective, query, target_url, score, "pipeline_auto_run")

        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "objective": objective,
            "query_used": query,
            "target_url": target_url,
            "sources": sources,
            "mode": mode,
            "navigation_ok": ok,
            "collection": collection_stats,
            "analysis": analysis,
            "screenshot": screenshot_name,
        }
        report_holder["report"] = report
        emit_event(
            "pipeline_finish",
            mission_id,
            "ok" if ok else "degraded",
            mode=mode,
            words=analysis["words"],
            successful_sources=collection_stats.get("successful_sources", 0),
        )
        return MissionOutcome(
            mission_id=mission_id,
            status="ok" if ok else "degraded",
            score=score,
            details=f"mode={mode}",
        )

    await run_async_mission(mission_id, _execute_pipeline)
    return report_holder["report"]


def save_reports(report: dict):
    out_json = ROOT / "atena_evolution" / "pipeline_report.json"
    out_md = ROOT / "atena_evolution" / "pipeline_report.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    terms = "\n".join([f"- {k}: {v}" for k, v in report["analysis"]["top_terms"]])
    source_quality = report.get("collection", {}).get("source_quality", [])
    selected_sources = [s for s in source_quality if s.get("selected")]
    top_source = "-"
    if selected_sources:
        ranked = sorted(
            selected_sources,
            key=lambda x: (x.get("relevance_score", 0.0), x.get("quality_score", 0.0)),
            reverse=True,
        )
        best = ranked[0]
        top_source = (
            f"{best.get('source')} (relevance={best.get('relevance_score')}, "
            f"quality={best.get('quality_score')})"
        )

    executive_summary = (
        f"Pipeline executado em modo **{report.get('mode', 'n/a')}** com "
        f"**{report.get('collection', {}).get('successful_sources', 0)}** fontes úteis. "
        f"A melhor fonte foi: {top_source}."
    )
    recommended_actions = [
        "Revisar top termos para detectar foco técnico real vs. ruído de navegação.",
        "Executar nova coleta com query mais específica quando houver poucas fontes úteis.",
        "Promover apenas insights com relevance_score >= 0.30 para decisões de produto.",
    ]
    md = f"""# ATENA Pipeline Report

- Timestamp: {report['timestamp']}
- Objective: {report['objective']}
- Query usada: `{report['query_used']}`
- URL alvo: {report['target_url']}
- Fontes analisadas: {len(report.get('sources', []))}
- Modo de coleta: {report.get('mode', 'n/a')}
- Navegação OK: {report['navigation_ok']}
- Fontes com sucesso: {report.get('collection', {}).get('successful_sources', 0)}
- Fontes com falha: {report.get('collection', {}).get('failed_sources', 0)}
- Palavras analisadas: {report['analysis']['words']}

## Resumo executivo
{executive_summary}

## Fontes
{chr(10).join([f"- {s}" for s in report.get("sources", [])]) if report.get("sources") else "- (sem fontes)"}

## Qualidade das fontes
{chr(10).join([f"- {q.get('source')}: selected={q.get('selected')} | relevance={q.get('relevance_score')} | quality={q.get('quality_score')}" for q in source_quality]) if source_quality else "- (sem métricas de qualidade)"}

## Top termos
{terms if terms else '- (sem termos)'}

## Recomendações profissionais
{chr(10).join([f"- {r}" for r in recommended_actions])}

## Artefato visual
`{report['screenshot'] or 'não disponível (fallback HTTP)'}`
"""
    out_md.write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Pipeline")
    parser.add_argument("--objective", default="Gerar inteligência acionável sobre o repositório ATENA")
    parser.add_argument("--query", default="ATENA AGI architecture")
    args = parser.parse_args()

    report = asyncio.run(run_pipeline(args.objective, args.query))
    save_reports(report)
    print("✅ Pipeline concluído.")
    print(f"Objective: {report['objective']}")
    print(f"Query: {report['query_used']}")
    print(f"Words: {report['analysis']['words']}")
    print("Relatórios: atena_evolution/pipeline_report.json e .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
