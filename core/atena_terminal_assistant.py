#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Terminal Assistant (Claude Code Style)
Versão aprimorada com interface moderna e comandos intuitivos.
"""

import shlex
import subprocess
import threading
import time
import sys
import os
import hashlib
import logging
import json
import re
import socket
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_llm_router import AtenaLLMRouter
from core.internet_challenge import run_internet_challenge
from core.atena_module_preloader import preload_all_modules

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    from rich.table import Table
    from rich.box import ROUNDED
    HAS_RICH = True
except Exception:
    HAS_RICH = False

# Configurações Globais
DASHBOARD_PORT = int(os.getenv("ATENA_DASHBOARD_PORT", "8765"))
ENABLE_DASHBOARD = os.getenv("ATENA_DASHBOARD_ENABLED", "0") == "1"
ROUTER_TIMEOUT_SECONDS = float(os.getenv("ATENA_ROUTER_TIMEOUT_S", "90"))
class PlainConsole:
    """Fallback simples para ambientes sem rich."""

    @staticmethod
    def print(*args, end: str = "\n", **kwargs) -> None:  # noqa: ANN003
        # ignora kwargs de estilo do rich
        text = " ".join(str(a) for a in args)
        print(text, end=end)


CONSOLE = Console() if HAS_RICH else PlainConsole()


def console_print(message: str) -> None:
    if HAS_RICH:
        CONSOLE.print(message)
    else:
        print(message)


def router_generate_with_timeout(
    router: AtenaLLMRouter,
    prompt: str,
    context: str,
    timeout_seconds: float = ROUTER_TIMEOUT_SECONDS,
) -> str:
    """Executa router.generate em thread daemon para evitar travas em TTY."""
    done = threading.Event()
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = router.generate(prompt, context=context)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=_worker, daemon=True).start()
    if not done.wait(timeout_seconds):
        raise TimeoutError(f"router.generate timeout>{timeout_seconds}s")
    if "error" in box:
        raise box["error"]
    return str(box.get("value", ""))


def _wants_five_topics(user_input: str) -> bool:
    text = user_input.lower()
    return ("5 tópicos" in text) or ("5 topicos" in text)


def _build_five_topics_prompt(user_input: str) -> str:
    return (
        f"{user_input}\n\n"
        "Responda SOMENTE com JSON válido no formato:\n"
        '{"topicos":["tópico 1","tópico 2","tópico 3","tópico 4","tópico 5"]}\n'
        "Exatamente 5 itens curtos."
    )


def _format_five_topics_response(raw_answer: str, original_prompt: str) -> str:
    text = (raw_answer or "").strip()
    # 1) JSON direto
    try:
        payload = json.loads(text)
        items = payload.get("topicos") if isinstance(payload, dict) else None
        if isinstance(items, list) and items:
            cleaned = [str(x).strip() for x in items if str(x).strip()][:5]
            if cleaned:
                return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))
    except Exception:
        pass

    # 2) Extrai bloco JSON embutido na resposta
    json_match = re.search(r"\{[\s\S]*\"topicos\"\s*:\s*\[[\s\S]*?\][\s\S]*?\}", text)
    if json_match:
        try:
            payload = json.loads(json_match.group(0))
            items = payload.get("topicos") if isinstance(payload, dict) else None
            if isinstance(items, list) and items:
                cleaned = [str(x).strip() for x in items if str(x).strip()][:5]
                if cleaned:
                    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))
        except Exception:
            pass

    # 3) Extrai linhas numeradas
    lines = [ln.strip(" -•\t") for ln in text.splitlines() if ln.strip()]
    numbered = [ln for ln in lines if re.match(r"^\d+[\).\s-]+", ln)]
    if numbered:
        cleaned = [re.sub(r"^\d+[\).\s-]+", "", ln).strip() for ln in numbered][:5]
        if cleaned:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))

    # 4) Fallback determinístico
    base = original_prompt.strip().rstrip("?")
    fallback = [
        f"Evoluir benchmark contínuo para '{base}'",
        "Aprimorar memória de longo prazo com validação de relevância",
        "Fortalecer segurança (redaction + secret scan + gates CI)",
        "Melhorar confiabilidade SRE (canary + auto-rollback)",
        "Automatizar avaliação de qualidade com métricas e auditoria",
    ]
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(fallback))


INTERNET_REQUEST_PATTERNS = (
    r"^\s*pesquis[ae]\b",
    r"\bpesquis[ae]\b",
    r"\bpesquis[ae]\b.*\binternet\b",
    r"\bna internet\b",
    r"\bprocure\b.*\binternet\b",
    r"\bbusque\b.*\binternet\b",
    r"\bache\b.*\binternet\b",
    r"\bencontre\b.*\binternet\b",
    r"\bsearch\b.*\bweb\b",
    r"\bweb search\b",
    r"\brelat[oó]rio\b.*\binternet\b",
)

WEB_FACT_QUESTION_PATTERNS = (
    r"^(quem|qual|quais|o que|oque|quando|onde|como)\b",
    r"^(what|who|when|where|which|how)\b",
)

WEB_FACT_SIGNAL_PATTERNS = (
    r"\b(hoje|atual|atualmente|agora|recente|últim|ultimo|latest|today|recent)\b",
    r"\b(preço|preco|cotação|cotacao|valor|dólar|dolar|bitcoin|btc|eth)\b",
    r"\b(oscar|grammy|nba|nfl|eleiç|election|presidente|ceo|lançamento|release|futebol|flamengo|santos|palmeiras|corinthians)\b",
    r"\b(202[0-9]|19[0-9]{2})\b",
    r"\?$",
)


def _is_internet_request(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text:
        return False
    if text.startswith("/internet "):
        return True
    if text.startswith("/internet"):
        return True
    return any(re.search(pattern, text) for pattern in INTERNET_REQUEST_PATTERNS)


def _is_web_fact_question(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text or text.startswith("/"):
        return False
    starts_like_question = any(re.search(pattern, text) for pattern in WEB_FACT_QUESTION_PATTERNS)
    has_web_signal = any(re.search(pattern, text) for pattern in WEB_FACT_SIGNAL_PATTERNS)
    return starts_like_question and has_web_signal


def _extract_internet_topic(user_input: str) -> str:
    text = (user_input or "").strip()
    if text.lower() == "/internet":
        return ""
    if text.lower().startswith("/internet "):
        return text[len("/internet "):].strip()

    cleaned = re.sub(r"(?i)^\s*(ask\s+atena|pergunte\s+atena|atena)\s*[:,\-]?\s*", "", text)
    text = cleaned if cleaned else text

    cleaned = re.sub(r"(?i)\bpesquis[ae]\b", "", text)
    cleaned = re.sub(r"(?i)\b(procure|busque)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(entregue|gere|monte|fa[çc]a)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(me|um|uma|o|a|e|and|pra|para|mim|por favor)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(na|no)\s+internet\b", "", cleaned)
    cleaned = re.sub(r"(?i)\binternet\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(relat[oó]rio|completo|final|atualizado|sobre|da|do|de)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(?i)^[:\-\s]+", "", cleaned).strip()
    return cleaned if cleaned else text


def _source_link(source_name: str, topic: str) -> str:
    query = urllib.parse.quote(topic)
    source = source_name.lower()
    if source == "wikipedia":
        return f"https://en.wikipedia.org/w/index.php?search={query}"
    if source == "github":
        return f"https://github.com/search?q={query}&type=repositories"
    if source == "hackernews":
        return f"https://hn.algolia.com/?q={query}"
    if source == "arxiv":
        return f"https://arxiv.org/search/?query={query}&searchtype=all"
    if source == "crossref":
        return f"https://search.crossref.org/?q={query}"
    if source == "openalex":
        return f"https://openalex.org/works?search={query}"
    if source == "stackoverflow":
        return f"https://stackoverflow.com/search?q={query}"
    if source == "reddit":
        return f"https://www.reddit.com/search/?q={query}"
    if source == "npm":
        return f"https://www.npmjs.com/search?q={query}"
    if source == "europepmc":
        return f"https://europepmc.org/search?query={query}"
    return f"https://duckduckgo.com/?q={query}"


def _summarize_source_detail(details: dict[str, object]) -> str:
    if not isinstance(details, dict):
        return "sem detalhes."
    for key in ("extract", "title"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:220]
    for key in ("top_repos", "hits", "papers", "works", "questions", "posts", "packages", "events"):
        value = details.get(key)
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                candidate = first.get("title") or first.get("full_name") or first.get("name")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()[:220]
    err = details.get("error")
    return str(err)[:220] if err else "sem detalhes relevantes."


def _build_source_findings(details: dict[str, object], limit: int = 3) -> list[str]:
    findings: list[str] = []
    if not isinstance(details, dict):
        return findings
    for key in ("extract", "title"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            findings.append(value.strip())
            return findings[:limit]
    for key in ("top_repos", "hits", "papers", "works", "questions", "posts", "packages", "events"):
        items = details.get(key)
        if not isinstance(items, list):
            continue
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            candidate = (
                item.get("title")
                or item.get("full_name")
                or item.get("name")
                or item.get("display_name")
            )
            if isinstance(candidate, str) and candidate.strip():
                findings.append(candidate.strip())
    return findings[:limit]


def _google_news_fallback_results(query: str, limit: int = 5) -> list[str]:
    try:
        encoded = urllib.parse.quote(query)
        url = (
            "https://news.google.com/rss/search"
            f"?q={encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (ATENA research fallback)"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec - controlled URL
            raw = resp.read().decode("utf-8", errors="ignore")
        root = ElementTree.fromstring(raw)
        rows: list[str] = []
        for item in root.findall("./channel/item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source_node = item.find("source")
            source_url = ""
            if source_node is not None:
                source_url = str(source_node.attrib.get("url", "")).strip()
            display_link = source_url or link
            if title and link:
                rows.append(f"- {title}\n  {display_link}")
        return rows
    except Exception:
        return []


def run_user_internet_research(user_input: str) -> str:
    topic = _extract_internet_topic(user_input)
    if not topic:
        return (
            "## Pesquisa na internet\n\n"
            "Use `/internet <tema>` para eu pesquisar e mostrar só o resultado final.\n"
            "Exemplo: `/internet ai agent safety evaluation benchmarks 2026`."
        )
    payload = run_internet_challenge(topic)
    all_sources = payload.get("all_sources", [])
    topic_lower = topic.lower()
    is_sports_schedule = ("joga" in topic_lower) or ("jogo" in topic_lower and "que dia" in topic_lower)
    stop_terms = {
        "que", "dia", "o", "a", "de", "do", "da", "na", "no", "joga", "jogo",
        "pra", "para", "mim", "me", "por", "favor", "quando", "qual", "quais",
    }
    topic_terms = [t for t in re.findall(r"[a-z0-9à-ú]+", topic_lower) if t not in stop_terms and len(t) >= 3]

    if is_sports_schedule and isinstance(all_sources, list):
        had_sports_source = False
        for item in all_sources:
            if not isinstance(item, dict):
                continue
            if str(item.get("source", "")).lower() != "thesportsdb" or not bool(item.get("ok")):
                continue
            had_sports_source = True
            details = item.get("details", {})
            events = details.get("events", []) if isinstance(details, dict) else []
            if isinstance(events, list) and events:
                event_lines: list[str] = []
                for evt in events[:3]:
                    if not isinstance(evt, dict):
                        continue
                    title = str(evt.get("title", "")).strip()
                    date = str(evt.get("date", "")).strip()
                    title_lower = title.lower()
                    is_relevant = any(term in title_lower for term in topic_terms) if topic_terms else True
                    if title and date and is_relevant:
                        event_lines.append(f"- {date}: {title}")
                if event_lines:
                    return (
                        "## Resultado da pesquisa\n\n"
                        f"**Tema:** {topic}\n\n"
                        "Próximos jogos encontrados:\n"
                        f"{chr(10).join(event_lines)}"
                    )
        google_rows = _google_news_fallback_results(topic)
        if google_rows:
            return (
                "## Resultado da pesquisa (fallback Google)\n\n"
                f"**Tema:** {topic}\n\n"
                "Não consegui confirmar pelo feed esportivo direto. "
                "Segue resultado completo encontrado no Google News:\n\n"
                + "\n".join(google_rows)
            )
        if had_sports_source:
            return (
                "## Resultado da pesquisa\n\n"
                f"**Tema:** {topic}\n\n"
                "Não encontrei um calendário confiável com esse termo."
            )
        return (
            "## Resultado da pesquisa\n\n"
            f"**Tema:** {topic}\n\n"
            "Não consegui confirmar a próxima partida com confiança nas fontes esportivas nem no fallback do Google."
        )

    all_findings: list[str] = []
    fallback_findings: list[str] = []
    if isinstance(all_sources, list):
        for item in all_sources:
            if not isinstance(item, dict):
                continue
            source_name = str(item.get("source", "unknown"))
            ok = bool(item.get("ok"))
            details = item.get("details", {})
            if ok:
                findings = _build_source_findings(details if isinstance(details, dict) else {})
                for finding in findings:
                    fallback_findings.append(f"- **{source_name}**: {finding[:240]}")
                    finding_lower = finding.lower()
                    is_relevant = any(term in finding_lower for term in topic_terms) if topic_terms else True
                    if is_relevant:
                        all_findings.append(f"- **{source_name}**: {finding[:240]}")
    final_findings = all_findings if all_findings else fallback_findings
    if not final_findings:
        google_rows = _google_news_fallback_results(topic)
        if google_rows:
            final_findings = google_rows
    key_findings = "\n".join(final_findings[:8]) if final_findings else "- Não encontrei resultados úteis para esse tema."
    return (
        f"## Resultado da pesquisa\n\n"
        f"**Tema:** {topic}\n\n"
        f"{key_findings}"
    )


@dataclass
class EvolutionState:
    cycles: int = 0
    running: bool = True
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_success: Optional[bool] = None
    last_error: Optional[str] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    wake_event: threading.Event = field(default_factory=threading.Event)


def _slugify(text: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return raw[:48] if raw else "insight"


def _extract_internet_signals(payload: dict[str, object]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return signals
    for src in sources:
        if not isinstance(src, dict) or not src.get("ok"):
            continue
        source_name = str(src.get("source", "unknown"))
        details = src.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("top_repos", "hits", "papers"):
            items = details.get(key)
            if not isinstance(items, list):
                continue
            for item in items[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("full_name") or item.get("title") or "").strip()
                if title:
                    signals.append({"source": source_name, "title": title})
    return signals


def _load_self_build_manifest() -> dict[str, object]:
    manifest_path = ROOT / "atena_evolution" / "self_generated_assets.json"
    if not manifest_path.exists():
        return {"assets": {}, "updated_at": None}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("assets", {})
            return payload
    except Exception:  # noqa: BLE001
        pass
    return {"assets": {}, "updated_at": None}


def materialize_self_generated_assets(topic: str, payload: dict[str, object]) -> list[dict[str, str]]:
    if str(payload.get("status", "")).lower() != "ok":
        return []
    signals = _extract_internet_signals(payload)
    if not signals:
        return []

    manifest = _load_self_build_manifest()
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        assets = {}
        manifest["assets"] = assets

    created: list[dict[str, str]] = []
    auto_modules_dir = ROOT / "modules" / "auto_generated"
    auto_skills_dir = ROOT / "skills" / "auto-evolution"
    auto_plugins_dir = ROOT / "plugins" / "auto-evolution"
    auto_modules_dir.mkdir(parents=True, exist_ok=True)
    auto_skills_dir.mkdir(parents=True, exist_ok=True)
    auto_plugins_dir.mkdir(parents=True, exist_ok=True)

    for signal in signals[:2]:
        manifest_key = f"{signal['source']}::{_slugify(signal['title'])}"
        if manifest_key in assets:
            continue
        slug = _slugify(signal["title"])

        module_path = auto_modules_dir / f"auto_{slug}.py"
        module_path.write_text(
            (
                "# Auto-generated by ATENA background evolution\n"
                f"INSIGHT_SOURCE = {signal['source']!r}\n"
                f"INSIGHT_TITLE = {signal['title']!r}\n\n"
                "def describe() -> str:\n"
                "    return f\"Auto-module from {INSIGHT_SOURCE}: {INSIGHT_TITLE}\"\n"
            ),
            encoding="utf-8",
        )

        skill_dir = auto_skills_dir / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            (
                f"# Skill: {slug}\n\n"
                f"- Origem: `{signal['source']}`\n"
                f"- Sinal: `{signal['title']}`\n"
                f"- Tema alvo: `{topic}`\n"
            ),
            encoding="utf-8",
        )

        plugin_dir = auto_plugins_dir / slug
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "README.md").write_text(
            (
                f"# Plugin Auto-Evolution: {slug}\n\n"
                f"Gerado pela ATENA com base no insight `{signal['title']}` ({signal['source']}).\n"
            ),
            encoding="utf-8",
        )

        assets[manifest_key] = {
            "topic": topic,
            "source": signal["source"],
            "title": signal["title"],
            "module_path": str(module_path.relative_to(ROOT)),
            "skill_path": str((skill_dir / "SKILL.md").relative_to(ROOT)),
            "plugin_path": str((plugin_dir / "README.md").relative_to(ROOT)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        created.append({"manifest_key": manifest_key, **assets[manifest_key]})

    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path = ROOT / "atena_evolution" / "self_generated_assets.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return created


def validate_self_generated_assets(created_assets: list[dict[str, str]]) -> dict[str, object]:
    """
    Valida assets recém-gerados:
    - módulo Python: compila com py_compile
    - skill/plugin: verifica existência do arquivo
    """
    total = len(created_assets)
    checks: list[dict[str, object]] = []
    passed = 0

    for asset in created_assets:
        module_path = ROOT / str(asset.get("module_path", ""))
        skill_path = ROOT / str(asset.get("skill_path", ""))
        plugin_path = ROOT / str(asset.get("plugin_path", ""))
        key = str(asset.get("manifest_key", "unknown"))

        module_ok = False
        module_error = ""
        if module_path.exists():
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(module_path)],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                module_ok = proc.returncode == 0
                if not module_ok:
                    module_error = (proc.stderr or proc.stdout or "").strip()[:400]
            except Exception as exc:  # noqa: BLE001
                module_error = str(exc)
        else:
            module_error = "module file not found"

        skill_ok = skill_path.exists()
        plugin_ok = plugin_path.exists()
        ok = module_ok and skill_ok and plugin_ok
        if ok:
            passed += 1

        checks.append(
            {
                "manifest_key": key,
                "ok": ok,
                "module_ok": module_ok,
                "skill_ok": skill_ok,
                "plugin_ok": plugin_ok,
                "module_error": module_error if not module_ok else None,
            }
        )

    status = "ok" if passed == total else ("partial" if passed > 0 else "failed")
    return {
        "status": status if total > 0 else "skipped",
        "total": total,
        "passed": passed,
        "failed": max(0, total - passed),
        "checks": checks,
    }


def parse_background_topics(raw: Optional[str]) -> list[str]:
    if raw:
        values = [part.strip() for part in raw.split(",") if part.strip()]
        if values:
            return values
    return [
        "autonomous coding agents reliability 2026",
        "open-source ai copilots terminal automation",
        "agentic safety benchmarks and evals",
    ]


def run_background_internet_learning_cycle(topic: str) -> dict[str, object]:
    payload = run_internet_challenge(topic)
    append_learning_memory(
        {
            "event": "background_internet_learning",
            "topic": topic,
            "status": payload.get("status", "unknown"),
            "confidence": payload.get("confidence", 0),
            "sources": len(payload.get("sources", [])) if isinstance(payload.get("sources"), list) else 0,
        }
    )
    created = materialize_self_generated_assets(topic=topic, payload=payload)
    if created:
        append_learning_memory(
            {
                "event": "background_self_build",
                "topic": topic,
                "created_assets": len(created),
                "manifest_paths": [item["manifest_key"] for item in created],
            }
        )
        validation = validate_self_generated_assets(created)
        append_learning_memory(
            {
                "event": "background_self_build_validation",
                "topic": topic,
                "status": validation.get("status"),
                "total": validation.get("total"),
                "passed": validation.get("passed"),
                "failed": validation.get("failed"),
            }
        )
    else:
        append_learning_memory(
            {
                "event": "background_self_build_validation",
                "topic": topic,
                "status": "skipped",
                "total": 0,
                "passed": 0,
                "failed": 0,
            }
        )
    return payload


def start_background_evolution(state: EvolutionState) -> Optional[threading.Thread]:
    if os.getenv("ATENA_ENABLE_BG_EVOLUTION", "1") != "1":
        return None

    topics = parse_background_topics(os.getenv("ATENA_BG_TOPICS"))
    interval_s = max(60, int(os.getenv("ATENA_BG_INTERVAL_S", "900")))

    def _worker() -> None:
        idx = 0
        while state.running:
            topic = topics[idx % len(topics)]
            idx += 1
            with state.lock:
                state.last_started_at = datetime.now(timezone.utc).isoformat()
            try:
                payload = run_background_internet_learning_cycle(topic)
                with state.lock:
                    state.cycles += 1
                    state.last_success = str(payload.get("status", "")).lower() == "ok"
                    state.last_error = None if state.last_success else str(payload.get("error", "unknown"))
                    state.last_finished_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:  # noqa: BLE001
                with state.lock:
                    state.cycles += 1
                    state.last_success = False
                    state.last_error = str(exc)
                    state.last_finished_at = datetime.now(timezone.utc).isoformat()
            state.wake_event.wait(interval_s)
            state.wake_event.clear()

    thread = threading.Thread(target=_worker, daemon=True, name="atena-bg-evolution")
    thread.start()
    return thread


def get_evolution_status(state: EvolutionState) -> str:
    with state.lock:
        return (
            f"cycles={state.cycles}\n"
            f"last_started_at={state.last_started_at}\n"
            f"last_finished_at={state.last_finished_at}\n"
            f"last_success={state.last_success}\n"
            f"last_error={state.last_error}\n"
            "mode=always-on-background-learning"
        )

def git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or "main"
    except Exception:
        return "local"

def get_prompt_label(model: str) -> Any:
    display_model = "local" if model.startswith("local:") else model
    branch = git_branch()
    cwd = Path.cwd().name
    if HAS_RICH:
        prompt = Text()
        prompt.append(f" {branch} ", style="bold white on blue")
        prompt.append(f" {cwd} ", style="bold white on black")
        prompt.append(f" {display_model} ", style="bold black on cyan")
        prompt.append("\n ❯ ", style="bold magenta")
        return prompt
    return f"[{branch}][{cwd}][{display_model}] ❯ "

def render_banner():
    if HAS_RICH:
        CONSOLE.print("\n")
        CONSOLE.print(Panel(
            Text.assemble(
                ("🔱 ATENA Ω ", "bold cyan"),
                ("Assistant ", "bold white"),
                ("\n\n", ""),
                ("Inspirado no Claude Code. Digite ", "dim"),
                ("/help", "bold green"),
                (" para começar.", "dim")
            ),
            border_style="cyan",
            box=ROUNDED,
            padding=(1, 2)
        ))
    else:
        print("\n🔱 ATENA Ω Assistant - Digite /help para comandos.\n")

def print_help():
    if HAS_RICH:
        table = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
        table.add_column("Comando", style="cyan")
        table.add_column("Descrição", style="white")
        
        commands = [
            ("/task <msg>", "Executa tarefa; perguntas factuais disparam relatório de internet automaticamente"),
            ("/internet <tema>", "Pesquisa tema na internet em múltiplas fontes com links"),
            ("/task-exec <objetivo>", "Planeja e executa comandos seguros com relatório"),
            ("/self-test [quick]", "Executa validações automáticas da ATENA e gera relatório"),
            ("/release-governor", "Executa gates security/release/perf e decide GO/NO-GO"),
            ("/saas-bootstrap <nome>", "Gera stack SaaS web/api/cli + artefatos"),
            ("/telemetry-insights", "Resumo de falhas/sucessos por missão"),
            ("/orchestrate <objetivo>", "Executa orquestração multiagente por papéis"),
            ("/memory-suggest <objetivo>", "Sugere ação com base em memória histórica"),
            ("/benchmark", "Roda benchmark contínuo e atualiza leaderboard"),
            ("/device-control <pedido> [--confirm]", "Controla dispositivo local com permissões seguras"),
            ("/security-scan [repo|system]", "Executa scanner de segurança e salva artefatos em analysis_reports"),
            ("/secret-audit", "Audita possíveis segredos no repositório e salva só versão mascarada"),
            ("/policy", "Mostra política de segurança para execução"),
            ("/plan <objetivo>", "Gera um plano de execução detalhado"),
            ("/review", "Revisa as mudanças atuais no código (git diff)"),
            ("/commit <msg>", "Realiza o commit das alterações atuais"),
            ("/run <cmd>", "Executa um comando no terminal"),
            ("/context", "Mostra o contexto atual da sessão"),
            ("/evolution-status", "Mostra status da evolução em background"),
            ("/model", "Gerencia o modelo de IA utilizado"),
            ("/clear", "Limpa o terminal"),
            ("/exit", "Encerra o assistente")
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        CONSOLE.print(Panel(table, title="[bold cyan]Comandos Disponíveis[/bold cyan]", border_style="cyan"))
    else:
        print("\nComandos: /task, /internet, /task-exec, /self-test, /release-governor, /saas-bootstrap, /telemetry-insights, /orchestrate, /memory-suggest, /benchmark, /device-control, /security-scan, /secret-audit, /policy, /plan, /review, /commit, /run, /context, /evolution-status, /model, /clear, /exit\n")


def run_self_test(mode: str = "full") -> tuple[str, str]:
    presets = {
        "quick": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
        ],
        "full": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("go-no-go", ["./atena", "go-no-go"]),
        ],
        "security": [("guardian", ["./atena", "guardian"])],
        "release": [("production-ready", ["./atena", "production-ready"])],
        "perf": [
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("telemetry-report", ["./atena", "telemetry-report"]),
        ],
    }
    checks = presets.get(mode, presets["full"])

    report_dir = ROOT / "atena_evolution" / "assistant_self_tests"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"assistant_self_test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    results: list[dict[str, object]] = []
    for name, cmd in checks:
        started = datetime.now(timezone.utc).isoformat()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=180 if name in {"go-no-go", "production-ready"} else 120,
            )
            rc = proc.returncode
            stdout = (proc.stdout or "")[-4000:]
            stderr = (proc.stderr or "")[-2000:]
        except subprocess.TimeoutExpired as exc:
            rc = 124
            stdout = (exc.stdout or "")[-4000:] if exc.stdout else ""
            stderr = f"timeout: {exc}"
        results.append(
            {
                "name": name,
                "command": " ".join(cmd),
                "started_at": started,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
        )

    status = "ok" if all(item["ok"] for item in results) else "failed"
    payload = {
        "status": status,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "self_test", "mode": mode, "status": status, "report_path": str(report_path)})
    return status, str(report_path)


ALLOWED_PREFIXES = (
    "./atena",
    "python",
    "python3",
    "pytest",
    "uv ",
    "pip ",
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "uname",
    "git status",
    "git diff",
)

DENY_PATTERNS = (
    r"(^|\s)rm\s+-rf\s+/",
    r"(^|\s)sudo(\s|$)",
    r"(^|\s)shutdown(\s|$)",
    r"(^|\s)reboot(\s|$)",
    r"mkfs\.",
    r"dd\s+if=",
    r"curl\s+.*\|\s*sh",
    r"wget\s+.*\|\s*sh",
    r"git\s+push",
)

READ_ONLY_PREFIXES = (
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "uname",
    "df",
    "free",
    "rg ",
    "find ",
    "wc ",
    "head ",
    "tail ",
    "python3 --version",
    "pip --version",
    "mkdir -p ",
    "python3 atena_evolution/generated_apps/",
    "python atena_evolution/generated_apps/",
    "pytest atena_evolution/generated_apps/",
    "bash atena_evolution/generated_apps/",
    "git status",
    "git diff",
    "./atena doctor",
    "./atena learn-status",
    "./atena evolution-scorecard",
    "./atena memory-relevance-audit",
    "./atena secret-scan",
)
SLO_TARGETS = {
    "max_fail_rate": 0.20,
    "min_success_rate": 0.80,
}
APPROVAL_TIERS = {
    "tier0": {"desc": "read-only", "allowed": READ_ONLY_PREFIXES},
    "tier1": {"desc": "build-and-test", "allowed": ("./atena", "python", "python3", "pytest", "uv ", "pip ")},
    "tier2": {"desc": "mutable", "allowed": ALLOWED_PREFIXES},
}


def append_learning_memory(entry: dict[str, object]) -> None:
    memory_path = ROOT / "atena_evolution" / "assistant_learning_memory.jsonl"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **entry}
    with memory_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def validate_command_policy(command: str, context: str = "interactive", tier: str = "tier1") -> tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return False, "comando vazio"
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd):
            return False, f"bloqueado por política: {pattern}"
    tier_cfg = APPROVAL_TIERS.get(tier, APPROVAL_TIERS["tier1"])
    allowed_prefixes = tuple(tier_cfg["allowed"])
    if not cmd.startswith(allowed_prefixes):
        return False, "comando fora da allowlist"
    current_branch = git_branch()
    if current_branch == "main" and context in {"run", "task-exec"} and not cmd.startswith(READ_ONLY_PREFIXES):
        return False, "em branch main apenas comandos read-only são permitidos neste contexto"
    return True, "ok"


def run_safe_command(command: str, timeout: int = 120, context: str = "interactive", tier: str = "tier1") -> tuple[int, str, str]:
    allowed, reason = validate_command_policy(command, context=context, tier=tier)
    if not allowed:
        return 126, "", reason
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def extract_commands_from_plan(plan_text: str) -> list[str]:
    commands: list[str] = []
    for line in plan_text.splitlines():
        candidate = line.strip().strip("`")
        candidate = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", candidate).strip()
        if candidate.startswith(ALLOWED_PREFIXES):
            commands.append(candidate)
    unique = []
    for command in commands:
        if command not in unique:
            unique.append(command)
    return unique[:5]


def extract_dag_commands(plan_text: str) -> list[dict[str, object]]:
    commands = extract_commands_from_plan(plan_text)
    nodes = []
    for idx, cmd in enumerate(commands):
        deps = [] if idx == 0 else [idx - 1]
        nodes.append({"id": idx, "command": cmd, "deps": deps})
    return nodes


def build_local_task_exec_fallback(objective: str) -> list[str]:
    """Gera fallback local útil quando o planner LLM não retorna comandos executáveis."""
    text = objective.lower()
    if (
        ("funcionar" in text or "rodar" in text or "executar" in text or "testar" in text)
        and ("código" in text or "codigo" in text)
        and ("achou" in text or "extern" in text)
    ):
        return [
            "python3 -c \"from pathlib import Path; import subprocess; files=sorted(Path('analysis_reports').glob('EXTERNAL_CODE_DISCOVERY_*.json')); print(files[-1] if files else 'NO_DISCOVERY_FILE')\"",
            "python3 -c \"from pathlib import Path; import subprocess,sys; files=sorted(Path('analysis_reports').glob('EXTERNAL_CODE_DISCOVERY_*.json')); subprocess.run(['python3','core/external_code_smoke_runner.py','--discovery-json',str(files[-1]),'--max-repos','3','--max-py-files','20'], check=False) if files else print('NO_DISCOVERY_FILE')\"",
        ]
    if (
        "novo c" in text
        or "novos c" in text
        or "outros c" in text
        or "extern" in text
        or "n\u00e3o dela" in text
        or "nao dela" in text
        or "github" in text
    ):
        return [
            "python3 core/external_code_discovery.py --query \"autonomous ai agents\" --max-repos 25",
            "python3 core/external_code_discovery.py --query \"llm multi-agent frameworks\" --max-repos 25",
            "python3 core/external_code_discovery.py --query \"open-source agent orchestration python\" --max-repos 25",
        ]
    if "vuln" in text or "seguran" in text or "security" in text:
        return [
            "python3 --version",
            "./atena doctor",
            "./atena secret-scan",
            "rg -n \"TODO|FIXME|HACK|XXX|password|secret|token|eval\\(|exec\\(\" core modules protocols",
            "find . -xdev -type f -perm -0002",
            "find / -xdev -type f -perm -4000 2>/dev/null | head -n 200",
        ]
    if "varr" in text or "scan" in text or "diagn" in text:
        return [
            "python3 --version",
            "./atena doctor",
            "./atena learn-status",
            "./atena evolution-scorecard",
            "./atena memory-relevance-audit",
        ]
    if "tests" in text and ("quant" in text or "count" in text or ".py" in text):
        return [
            "python3 -c \"from pathlib import Path; p=Path('tests'); files=list(p.rglob('*.py')) if p.exists() else []; print({'tests_exists': p.exists(), 'py_files': len(files)})\""
        ]
    if ("quant" in text or "count" in text or "conte" in text) and "arquivo" in text:
        folder_match = re.search(r"(?:pasta|diret[oó]rio|folder|dir)\s+([a-zA-Z0-9_./-]+)", text)
        folder = folder_match.group(1).strip(".,;:") if folder_match else "."
        ext = None
        ext_match = re.search(r"\.([a-z0-9]{1,8})\b", text)
        if ext_match:
            ext = ext_match.group(1)
        elif " json" in text:
            ext = "json"
        elif " py" in text or "python" in text:
            ext = "py"
        elif " md" in text or "markdown" in text:
            ext = "md"
        pattern = f"*.{ext}" if ext else "*"
        return [
            "python3 -c \"from pathlib import Path; p=Path('"
            + folder
            + "'); files=list(p.rglob('"
            + pattern
            + "')) if p.exists() else []; print({'path': str(p), 'exists': p.exists(), 'pattern': '"
            + pattern
            + "', 'count': len(files)})\""
        ]
    if "git status" in text or ("status" in text and "git" in text):
        return ["git status --short", "git status"]
    if "listar" in text or "list" in text:
        return ["python3 -c \"from pathlib import Path; print('\\n'.join(sorted(x.name for x in Path('.').iterdir())))\""]
    return ["./atena doctor"]


SAFE_ATENA_SUBCOMMANDS = {
    "doctor",
    "secret-scan",
    "modules-smoke",
    "guardian",
    "production-ready",
    "orchestrator-mission",
    "bootstrap",
}


def sanitize_task_exec_commands(commands: list[str]) -> list[str]:
    """Remove comandos interativos/perigosos do /task-exec."""
    sanitized: list[str] = []
    for cmd in commands:
        candidate = cmd.strip()
        if candidate in {"python", "python3"}:
            # Evita abrir REPL interativo que trava a sessão.
            continue
        if candidate.startswith("python ") or candidate.startswith("python3 "):
            parts = shlex.split(candidate)
            # permite apenas execuções explícitas de script/flags.
            if len(parts) == 1:
                continue
        if candidate.startswith("./atena"):
            parts = shlex.split(candidate)
            sub = parts[1] if len(parts) > 1 else ""
            if sub not in SAFE_ATENA_SUBCOMMANDS:
                continue
        sanitized.append(candidate)
    return sanitized


def execute_command_dag(nodes: list[dict[str, object]], context: str, tier: str = "tier1") -> list[dict[str, object]]:
    completed: set[int] = set()
    results: list[dict[str, object]] = []
    for node in nodes:
        deps = set(node["deps"])
        if not deps.issubset(completed):
            continue
        command = str(node["command"])
        rc, out, err = run_safe_command(command, timeout=180, context=context, tier=tier)
        results.append(
            {
                "id": node["id"],
                "deps": list(deps),
                "command": command,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": out[-2500:],
                "stderr_tail": err[-1200:],
            }
        )
        if rc == 0:
            completed.add(int(node["id"]))
        else:
            break
    return results


def rollback_from_command(command: str) -> str:
    match = re.search(r"--name\s+([a-zA-Z0-9_-]+)", command)
    if "code-build" in command and match:
        target = ROOT / "atena_evolution" / "generated_apps" / match.group(1)
        if target.exists():
            for path in sorted(target.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    path.rmdir()
            target.rmdir()
            return f"rollback aplicado: removido {target}"
    return "rollback não necessário"


def run_task_exec(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    planner_prompt = (
        "Retorne no máximo 5 comandos shell seguros para executar o objetivo. "
        "Use somente: ./atena, python3, pytest, uv, pip. "
        "Responda com 1 comando por linha.\n\n"
        f"Objetivo: {objective}"
    )
    try:
        plan_text = router_generate_with_timeout(
            router=router,
            prompt=planner_prompt,
            context="Atena task executor",
            timeout_seconds=25,
        )
    except Exception as exc:
        fallback_commands = build_local_task_exec_fallback(objective)
        plan_text = "\n".join(
            [
                "fallback_plan_timeout",
                f"motivo={type(exc).__name__}",
                *fallback_commands,
            ]
        )
    planned = extract_commands_from_plan(plan_text) or build_local_task_exec_fallback(objective)
    commands = sanitize_task_exec_commands(planned) or build_local_task_exec_fallback(objective)
    dag_nodes = extract_dag_commands("\n".join(commands))
    if not dag_nodes and commands:
        dag_nodes = [{"id": i, "command": c, "deps": [] if i == 0 else [i - 1]} for i, c in enumerate(commands)]
    results = execute_command_dag(dag_nodes, context="task-exec", tier="tier2")
    rollback_logs: list[str] = []
    for item in results:
        if not item["ok"]:
            rollback_logs.append(rollback_from_command(str(item["command"])))
            break
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_dir = ROOT / "atena_evolution" / "task_exec_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"task_exec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(
            {
                "status": status,
                "objective": objective,
                "plan_text": plan_text,
                "commands": commands,
                "dag_nodes": dag_nodes,
                "results": results,
                "rollback_logs": rollback_logs,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    append_learning_memory(
        {
            "event": "task_exec",
            "status": status,
            "objective": objective,
            "commands": commands,
            "report_path": str(report_path),
        }
    )
    return status, str(report_path)


def summarize_task_exec_report(report_path: str) -> str:
    """Resumo curto e humano do resultado do /task-exec."""
    try:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    commands = payload.get("commands") or []
    results = payload.get("results") or []
    lines: list[str] = []
    if commands:
        lines.append(f"Comandos executados: {len(commands)}")
    for item in results[:2]:
        cmd = str(item.get("command", "")).strip()
        stdout_tail = str(item.get("stdout_tail", "")).strip()
        if cmd:
            lines.append(f"- {cmd}")
        if stdout_tail:
            snippet = " ".join(stdout_tail.splitlines())[:240]
            lines.append(f"  saída: {snippet}")
    return "\n".join(lines)


def run_saas_bootstrap(project_name: str) -> tuple[str, str]:
    safe_name = "".join(ch for ch in project_name if ch.isalnum() or ch in ("-", "_")).strip("-_") or "atena_saas"
    commands = [
        f"./atena code-build --type site --template dashboard --name {safe_name}_web --validate",
        f"./atena code-build --type api --name {safe_name}_api --validate",
        f"./atena code-build --type cli --name {safe_name}_cli --validate",
    ]
    results = []
    for command in commands:
        rc, out, err = run_safe_command(command, timeout=240, context="saas-bootstrap")
        results.append({"command": command, "returncode": rc, "ok": rc == 0, "stdout_tail": out[-1800:], "stderr_tail": err[-800:]})

    bundle_dir = ROOT / "atena_evolution" / "generated_apps" / f"{safe_name}_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "docker-compose.yml").write_text(
        f"""services:\n  {safe_name}_api:\n    image: python:3.10-slim\n    working_dir: /app\n    command: sh -c \"pip install fastapi uvicorn && uvicorn main:app --host 0.0.0.0 --port 8000\"\n    volumes:\n      - ../{safe_name}_api:/app\n    ports:\n      - \"8000:8000\"\n""",
        encoding="utf-8",
    )
    (bundle_dir / "ci_stub.yml").write_text(
        "name: atena-saas-ci\non: [push]\njobs:\n  smoke:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: ./atena doctor\n      - run: ./atena modules-smoke\n",
        encoding="utf-8",
    )
    (bundle_dir / ".env.example").write_text(
        "APP_ENV=production\nJWT_SECRET=change_me\nDATABASE_URL=postgresql://user:pass@localhost:5432/app\n",
        encoding="utf-8",
    )
    (bundle_dir / "migration.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (\n  id SERIAL PRIMARY KEY,\n  email TEXT UNIQUE NOT NULL,\n  password_hash TEXT NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);\n",
        encoding="utf-8",
    )
    (bundle_dir / "smoke_test.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    (bundle_dir / "auth_stub.py").write_text(
        "def issue_token(user_id: str) -> str:\n    return f'token-{user_id}'\n",
        encoding="utf-8",
    )
    (bundle_dir / "healthcheck.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\ncurl -sf http://localhost:8000/health\n",
        encoding="utf-8",
    )
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_path = bundle_dir / "bootstrap_report.json"
    report_path.write_text(json.dumps({"status": status, "project": safe_name, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "saas_bootstrap", "status": status, "project": safe_name, "report_path": str(report_path)})
    return status, str(report_path)


def telemetry_insights() -> str:
    telemetry_file = ROOT / "atena_evolution" / "telemetry_events.jsonl"
    if not telemetry_file.exists():
        return "Sem telemetria ainda. Rode missões para gerar eventos."
    total = 0
    fail = 0
    missions: dict[str, dict[str, int]] = {}
    for line in telemetry_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        mission = str(item.get("mission", "unknown"))
        status = str(item.get("status", "unknown"))
        missions.setdefault(mission, {"ok": 0, "fail": 0})
        if status == "ok":
            missions[mission]["ok"] += 1
        else:
            missions[mission]["fail"] += 1
            fail += 1
    top = sorted(missions.items(), key=lambda x: x[1]["fail"], reverse=True)[:3]
    fail_rate = (fail / total) if total else 0.0
    success_rate = 1.0 - fail_rate
    slo_ok = fail_rate <= SLO_TARGETS["max_fail_rate"] and success_rate >= SLO_TARGETS["min_success_rate"]
    lines = [
        f"Eventos totais: {total}",
        f"Falhas totais: {fail}",
        f"Fail rate: {fail_rate:.2%}",
        f"Success rate: {success_rate:.2%}",
        f"SLO status: {'OK' if slo_ok else 'ALERTA'}",
        "Top missões por falha:",
    ]
    lines.extend([f"- {name}: fail={stats['fail']} ok={stats['ok']}" for name, stats in top])
    lines.append("SLO por missão:")
    for name, stats in sorted(missions.items()):
        count = stats["ok"] + stats["fail"]
        mission_fail_rate = (stats["fail"] / count) if count else 0.0
        mission_status = "ALERTA" if mission_fail_rate > SLO_TARGETS["max_fail_rate"] else "OK"
        lines.append(f"- {name}: fail_rate={mission_fail_rate:.2%} status={mission_status}")
    append_learning_memory({"event": "telemetry_insights", "status": "ok" if slo_ok else "alert", "fail_rate": fail_rate, "success_rate": success_rate})
    return "\n".join(lines)


def run_release_governor() -> tuple[str, str]:
    sequence = ["security", "release", "perf"]
    details = []
    weights = {"security": 0.5, "release": 0.3, "perf": 0.2}
    score = 0.0
    for mode in sequence:
        status, report_path = run_self_test(mode=mode)
        details.append({"mode": mode, "status": status, "report_path": report_path})
        score += weights.get(mode, 0.0) * (1.0 if status == "ok" else 0.0)
    final_status = "go" if score >= 0.8 else "no-go"
    remediation = "Executar ./atena fix e repetir /self-test security" if final_status == "no-go" else "Sistema aprovado para evolução."
    governor_dir = ROOT / "atena_evolution" / "release_governor"
    governor_dir.mkdir(parents=True, exist_ok=True)
    out_path = governor_dir / f"release_governor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps({"status": final_status, "score": round(score, 3), "checks": details, "remediation": remediation, "generated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    append_learning_memory({"event": "release_governor", "status": final_status, "report_path": str(out_path)})
    return final_status, str(out_path)


def suggest_from_memory(objective: str) -> str:
    memory_path = ROOT / "atena_evolution" / "assistant_learning_memory.jsonl"
    if not memory_path.exists():
        return "Sem memória histórica ainda."
    query_tokens = set(re.findall(r"\w+", objective.lower()))
    scored: list[tuple[int, dict[str, object]]] = []
    for line in memory_path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = json.dumps(item, ensure_ascii=False).lower()
        score = sum(1 for token in query_tokens if token in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = [entry for _, entry in scored[:3]]
    if not best:
        return "Nenhum caso similar encontrado."
    lines = ["Top casos similares:"]
    for item in best:
        lines.append(f"- event={item.get('event')} status={item.get('status')} report={item.get('report_path', '-')}")
    return "\n".join(lines)


def run_multi_agent_orchestrator(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    roles = ["planner", "builder", "reviewer", "security", "release"]
    outputs = {}
    for role in roles:
        prompt = f"Você é o agente {role}. Objetivo: {objective}. Entregue resumo objetivo e próximo passo."
        outputs[role] = router.generate(prompt, context=f"multi-agent:{role}")
    orchestration_dir = ROOT / "atena_evolution" / "multi_agent_runs"
    orchestration_dir.mkdir(parents=True, exist_ok=True)
    out_path = orchestration_dir / f"orchestrate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps({"objective": objective, "outputs": outputs}, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "orchestrate", "status": "ok", "objective": objective, "report_path": str(out_path)})
    return "ok", str(out_path)


def run_benchmark_suite() -> tuple[str, str]:
    suites = ["quick", "security", "perf"]
    points = {"quick": 20, "security": 40, "perf": 40}
    total = 0
    details = []
    for suite in suites:
        status, report_path = run_self_test(mode=suite)
        earned = points[suite] if status == "ok" else 0
        total += earned
        details.append({"suite": suite, "status": status, "points": earned, "report_path": report_path})
    leaderboard_dir = ROOT / "atena_evolution" / "benchmarks"
    leaderboard_dir.mkdir(parents=True, exist_ok=True)
    out_path = leaderboard_dir / "leaderboard.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "score": total, "details": details}
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    append_learning_memory({"event": "benchmark", "status": "ok", "score": total, "report_path": str(out_path)})
    return ("ok" if total >= 80 else "alert"), str(out_path)


def run_device_control(request: str, confirmed: bool) -> tuple[str, str]:
    report_dir = ROOT / "atena_evolution" / "device_control"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"device_control_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"

    if not confirmed:
        payload = {
            "status": "blocked",
            "reason": "confirmation_required",
            "request": request,
            "allowed_actions": [
                "abrir URL (http/https)",
                "diagnóstico rápido do sistema",
                "status básico do sistema",
            ],
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return "blocked", str(report_path)

    req = request.strip().lower()
    action = "unknown"
    result: dict[str, object] = {"request": request}

    url_match = re.search(r"(https?://[^\s]+)", request, flags=re.IGNORECASE)
    if any(token in req for token in ("abrir", "abra", "open")) and url_match:
        action = "open_url"
        url = url_match.group(1)
        ok = webbrowser.open(url)
        result.update({"action": action, "url": url, "ok": bool(ok)})
    elif "diagnost" in req or "teste" in req:
        action = "self_test_quick"
        status, path = run_self_test(mode="quick")
        result.update({"action": action, "status": status, "report": path})
    elif "status" in req or "sistema" in req:
        action = "system_status"
        rc, out, err = run_safe_command("uname -a", context="device-control", tier="tier0")
        result.update({"action": action, "returncode": rc, "stdout": out[-800:], "stderr": err[-400:]})
    else:
        result.update({"action": action, "status": "unsupported_request"})

    final_status = "ok" if result.get("action") != "unknown" and result.get("status") != "unsupported_request" else "failed"
    payload = {"status": final_status, **result}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "device_control", "status": final_status, "action": action, "report_path": str(report_path)})
    return final_status, str(report_path)


def run_security_scan(scope: str = "repo") -> tuple[str, str]:
    """
    Executa uma varredura de segurança (read-only) e salva artefatos em analysis_reports/.
    scope=repo evita scans agressivos no host inteiro; scope=system inclui SUID em /.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    reports_dir = ROOT / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    commands: list[tuple[str, str]] = [
        (f"SCAN_SECURITY_SYSTEM_{timestamp}.txt", "uname -a && cat /etc/os-release && python3 --version"),
        (f"SCAN_SECURITY_ATENA_DOCTOR_{timestamp}.txt", "./atena doctor"),
        (f"SCAN_SECURITY_SECRET_SCAN_{timestamp}.txt", "./atena secret-scan"),
        (
            f"SCAN_SECURITY_CODE_MARKERS_{timestamp}.txt",
            "rg -n \"TODO|FIXME|HACK|XXX|password|secret|token|eval\\(|exec\\(|subprocess\\.Popen\\(|os\\.system\\(\" core modules protocols",
        ),
        (f"SCAN_SECURITY_WORLD_WRITABLE_{timestamp}.txt", "find . -xdev -type f -perm -0002"),
    ]
    if scope == "system":
        commands.append((f"SCAN_SECURITY_SUID_TOP200_{timestamp}.txt", "find / -xdev -type f -perm -4000 2>/dev/null | head -n 200"))
    else:
        commands.append((f"SCAN_SECURITY_SUID_REPO_{timestamp}.txt", "find . -xdev -type f -perm -4000"))

    results: list[dict[str, object]] = []
    artifact_map: dict[str, Path] = {}
    for filename, command in commands:
        rc, out, err = run_safe_command(command, timeout=240, context="security-scan", tier="tier0")
        out_path = reports_dir / filename
        out_path.write_text((out or "").rstrip() + ("\n" if out else ""), encoding="utf-8")
        artifact_map[filename] = out_path
        results.append(
            {
                "artifact": str(out_path),
                "command": command,
                "returncode": rc,
                "ok": rc == 0,
                "stderr_tail": (err or "")[-500:],
            }
        )

    findings: list[dict[str, object]] = []
    summary = {
        "secret_scan": "unknown",
        "world_writable_count": 0,
        "suid_count": 0,
        "code_marker_count": 0,
        "high_risk_marker_count": 0,
    }

    secret_file = artifact_map.get(f"SCAN_SECURITY_SECRET_SCAN_{timestamp}.txt")
    if secret_file and secret_file.exists():
        secret_txt = secret_file.read_text(encoding="utf-8").lower()
        if "nenhum vazamento detectado" in secret_txt:
            summary["secret_scan"] = "clean"
        else:
            summary["secret_scan"] = "possible_leak"
            findings.append(
                {
                    "severity": "high",
                    "category": "secrets",
                    "message": "Secret scan retornou possível vazamento; revisar imediatamente.",
                    "artifact": str(secret_file),
                }
            )

    world_file = artifact_map.get(f"SCAN_SECURITY_WORLD_WRITABLE_{timestamp}.txt")
    if world_file and world_file.exists():
        ww_lines = [ln for ln in world_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        summary["world_writable_count"] = len(ww_lines)
        if ww_lines:
            findings.append(
                {
                    "severity": "high",
                    "category": "filesystem",
                    "message": f"Foram encontrados {len(ww_lines)} arquivos world-writable.",
                    "artifact": str(world_file),
                    "sample": ww_lines[:10],
                }
            )

    suid_name = f"SCAN_SECURITY_SUID_TOP200_{timestamp}.txt" if scope == "system" else f"SCAN_SECURITY_SUID_REPO_{timestamp}.txt"
    suid_file = artifact_map.get(suid_name)
    if suid_file and suid_file.exists():
        suid_lines = [ln for ln in suid_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        summary["suid_count"] = len(suid_lines)
        if len(suid_lines) > 20:
            findings.append(
                {
                    "severity": "medium",
                    "category": "privilege_surface",
                    "message": f"Superfície SUID elevada: {len(suid_lines)} binários encontrados.",
                    "artifact": str(suid_file),
                    "sample": suid_lines[:10],
                }
            )

    markers_file = artifact_map.get(f"SCAN_SECURITY_CODE_MARKERS_{timestamp}.txt")
    if markers_file and markers_file.exists():
        marker_lines = [ln for ln in markers_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        summary["code_marker_count"] = len(marker_lines)
        high_risk = [
            ln for ln in marker_lines
            if any(token in ln for token in ("eval(", "exec(", "os.system(", "subprocess.Popen("))
        ]
        summary["high_risk_marker_count"] = len(high_risk)
        if high_risk:
            findings.append(
                {
                    "severity": "medium",
                    "category": "code_pattern",
                    "message": f"Foram encontrados {len(high_risk)} marcadores de alto risco (eval/exec/os.system/subprocess).",
                    "artifact": str(markers_file),
                    "sample": high_risk[:10],
                }
            )

    base_ok = all(item["ok"] for item in results)
    if not base_ok:
        status = "failed"
    elif any(item["severity"] == "high" for item in findings):
        status = "fail"
    elif findings:
        status = "warn"
    else:
        status = "ok"

    summary_path = reports_dir / f"EXECUCAO_SECURITY_SCAN_{timestamp}.json"
    payload = {
        "status": status,
        "scope": scope,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "summary": summary,
        "findings": findings,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "security_scan", "status": status, "scope": scope, "report_path": str(summary_path)})
    return status, str(summary_path)


def _mask_secret(value: str) -> dict[str, str]:
    token = (value or "").strip()
    if len(token) <= 8:
        masked = "*" * len(token)
    else:
        masked = f"{token[:4]}...{token[-4:]}"
    fp = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else ""
    return {"masked": masked, "fingerprint_sha256_16": fp}


def run_secret_audit() -> tuple[str, str]:
    """
    Auditoria segura de possíveis segredos no repositório.
    Nunca salva segredo bruto: apenas valor mascarado + fingerprint.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    reports_dir = ROOT / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"EXECUCAO_SECRET_AUDIT_{timestamp}.json"

    patterns = [
        ("github_token", re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
        ("api_key", re.compile(r"\b(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\\-_]{20,})\b")),
        (
            "env_secret_value",
            re.compile(
                r"(?i)\b(?:token|secret|api[_-]?key|github[_-]?token)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\\-]{16,})[\"']?"
            ),
        ),
    ]

    findings: list[dict[str, object]] = []
    scanned_files = 0
    max_file_bytes = 1_000_000
    skip_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        "atena_evolution",
        "analysis_reports",
    }

    for file_path in ROOT.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(ROOT)
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            if file_path.stat().st_size > max_file_bytes:
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned_files += 1
        for line_no, line in enumerate(content.splitlines(), start=1):
            for kind, rgx in patterns:
                for match in rgx.finditer(line):
                    raw = match.group(1)
                    if kind == "env_secret_value" and not re.search(r"\d", raw):
                        continue
                    masked = _mask_secret(raw)
                    findings.append(
                        {
                            "file": str(rel),
                            "line": line_no,
                            "kind": kind,
                            "masked": masked["masked"],
                            "fingerprint_sha256_16": masked["fingerprint_sha256_16"],
                            "context_redacted": line.replace(raw, masked["masked"])[:260],
                        }
                    )
    status = "warn" if findings else "ok"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scanned_files": scanned_files,
        "findings_count": len(findings),
        "note": "Segredos brutos NÃO são armazenados. Apenas versões mascaradas e fingerprint.",
        "findings": findings[:5000],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "secret_audit", "status": status, "report_path": str(report_path), "findings_count": len(findings)})
    return status, str(report_path)

@contextmanager
def atena_thinking(message: str = "Pensando..."):
    use_live_spinner = HAS_RICH and os.getenv("ATENA_USE_LIVE_SPINNER", "0") == "1"
    if use_live_spinner:
        with Live(Spinner("dots", text=Text(message, style="cyan"), style="magenta"), refresh_per_second=10, transient=True):
            yield
    else:
        print(f"◐ {message}")
        yield
        print("✔ concluído")

def main():
    render_banner()
    router = AtenaLLMRouter()
    if os.getenv("ATENA_PRELOAD_ALL_MODULES", "1") == "1":
        preload_result = preload_all_modules(ROOT / "modules")
        loaded_count = int(preload_result.get("loaded_count", 0))
        total = int(preload_result.get("total", 0))
        failed_count = int(preload_result.get("failed_count", 0))
        console_print(
            f"[ATENA preload] módulos carregados: {loaded_count}/{total} (falhas: {failed_count})"
        )
    if router.auto_prepare_result is not None:
        ok_auto, msg_auto = router.auto_prepare_result
        if ok_auto:
            console_print(f"[ATENA model] {msg_auto}")
        else:
            console_print(f"[ATENA model] aviso: {msg_auto}")
    evolution_state = EvolutionState()
    bg_thread = start_background_evolution(evolution_state)
    if bg_thread is not None:
        console_print("[ATENA evolution] background internet-learning e auto-modificação ativos.")
    
    # Silenciar logs barulhentos
    for logger_name in ["AtenaUltraBrain", "httpx", "huggingface_hub", "transformers"]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    while True:
        try:
            prompt = get_prompt_label(router.current())
            if HAS_RICH:
                CONSOLE.print(prompt, end="")
                user_input = input().strip()
            else:
                user_input = input(prompt).strip()

            if user_input.startswith(".task "):
                user_input = "/task " + user_input[len(".task "):]
            elif user_input.startswith(".internet "):
                user_input = "/internet " + user_input[len(".internet "):]
            
            if not user_input:
                continue
            
            if user_input in ["/exit", "exit", "quit", "/quit", "/q", ":q", "/sair", "sair"]:
                console_print("[bold red]Encerrando ATENA... Até logo![/bold red]" if HAS_RICH else "Encerrando ATENA... Até logo!")
                evolution_state.running = False
                evolution_state.wake_event.set()
                break
            
            if user_input == "/help":
                print_help()
                continue
            
            if user_input == "/clear":
                os.system("clear")
                continue

            if user_input == "/model":
                options = "\n".join(f"- {item}" for item in router.list_options())
                message = (
                    f"Atual: {router.current()}\n\n"
                    "Uso:\n"
                    "- /model list\n"
                    "- /model set <provider:modelo>\n"
                    "- /model set custom:<modelo>@<base_url>\n"
                    "- /model prepare-local\n"
                    "- /model auto\n\n"
                    f"Opções disponíveis:\n{options}"
                )
                if HAS_RICH:
                    CONSOLE.print(Panel(message, title="[bold cyan]Model Router[/bold cyan]", border_style="cyan"))
                else:
                    print(message)
                continue

            if user_input == "/model list":
                options = "\n".join(f"- {item}" for item in router.list_options())
                console_print(f"Modelos/provedores:\n{options}")
                continue

            if user_input.startswith("/model set "):
                spec = user_input[len("/model set "):].strip()
                ok, msg = router.set_backend(spec)
                color = "green" if ok else "red"
                console_print(
                    f"[bold {color}]{msg}[/bold {color}]"
                    if HAS_RICH
                    else msg
                )
                continue

            if user_input == "/model prepare-local":
                ok, msg = router.prepare_free_local_model()
                color = "green" if ok else "yellow"
                console_print(
                    f"[bold {color}]{msg}[/bold {color}]"
                    if HAS_RICH
                    else msg
                )
                continue

            if user_input == "/model auto":
                ok, msg = router.auto_orchestrate_llm()
                color = "green" if ok else "yellow"
                console_print(
                    f"[bold {color}]{msg}[/bold {color}]"
                    if HAS_RICH
                    else msg
                )
                continue
            
            if user_input == "/context":
                if HAS_RICH:
                    CONSOLE.print(Panel(
                        f"CWD: [cyan]{ROOT}[/cyan]\nBranch: [magenta]{git_branch()}[/magenta]\nModelo: [green]{router.current()}[/green]",
                        title="Contexto Atual", border_style="blue"
                    ))
                continue

            if user_input == "/evolution-status":
                status = get_evolution_status(evolution_state)
                if HAS_RICH:
                    CONSOLE.print(Panel(status, title="[bold cyan]Evolution Status[/bold cyan]", border_style="cyan"))
                else:
                    print(status)
                continue

            if user_input.startswith("/self-test"):
                parts = user_input.split(maxsplit=1)
                mode = parts[1].strip().lower() if len(parts) > 1 else "full"
                with atena_thinking("Executando auto-validação da ATENA..."):
                    status, report_path = run_self_test(mode=mode)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Self-test: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/release-governor":
                with atena_thinking("Executando Release Governor..."):
                    status, report_path = run_release_governor()
                color = "green" if status == "go" else "red"
                CONSOLE.print(f"[bold {color}]Release Governor: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/policy":
                CONSOLE.print("[bold cyan]Policy Engine[/bold cyan]")
                CONSOLE.print(f"Allowlist: {', '.join(ALLOWED_PREFIXES)}")
                CONSOLE.print(f"Bloqueios: {', '.join(DENY_PATTERNS)}")
                CONSOLE.print("Tiers: " + ", ".join(f"{name}={cfg['desc']}" for name, cfg in APPROVAL_TIERS.items()))
                continue

            if user_input.startswith("/orchestrate "):
                objective = user_input[len("/orchestrate "):].strip()
                with atena_thinking("Executando orquestração multiagente..."):
                    status, report_path = run_multi_agent_orchestrator(router, objective)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Orchestrate: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input.startswith("/memory-suggest "):
                objective = user_input[len("/memory-suggest "):].strip()
                CONSOLE.print(Panel(suggest_from_memory(objective), title="[bold cyan]Memory Suggest[/bold cyan]", border_style="cyan"))
                continue

            if user_input == "/benchmark":
                with atena_thinking("Executando benchmark contínuo..."):
                    status, report_path = run_benchmark_suite()
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Benchmark: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Leaderboard: {report_path}[/dim]")
                continue

            if user_input.startswith("/device-control "):
                raw = user_input[len("/device-control "):].strip()
                confirmed = raw.endswith("--confirm")
                request = raw[:-9].strip() if confirmed else raw
                with atena_thinking("Executando device control..."):
                    status, report_path = run_device_control(request=request, confirmed=confirmed)
                color = "green" if status == "ok" else ("yellow" if status == "blocked" else "red")
                CONSOLE.print(f"[bold {color}]Device control: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                if status == "blocked":
                    CONSOLE.print("[yellow]Use --confirm para executar ações de controle de dispositivo.[/yellow]")
                continue

            if user_input.startswith("/security-scan"):
                raw = user_input[len("/security-scan"):].strip().lower()
                scope = "system" if raw == "system" else "repo"
                with atena_thinking(f"Executando scanner de segurança ({scope})..."):
                    status, report_path = run_security_scan(scope=scope)
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Security scan: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/secret-audit":
                with atena_thinking("Executando auditoria segura de segredos (mascarada)..."):
                    status, report_path = run_secret_audit()
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Secret audit: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                if status != "ok":
                    CONSOLE.print("[yellow]Possíveis segredos detectados. Somente versão mascarada foi salva.[/yellow]")
                continue

            if user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                CONSOLE.print(f"[dim]Executando: {cmd}[/dim]")
                rc, out, err = run_safe_command(cmd, context="run", tier="tier0")
                if out:
                    CONSOLE.print(out.rstrip())
                if err:
                    CONSOLE.print(f"[yellow]{err.rstrip()}[/yellow]")
                CONSOLE.print(f"[dim]returncode={rc}[/dim]")
                continue

            if user_input.startswith("/task-exec "):
                objective = user_input[len("/task-exec "):].strip()
                with atena_thinking("Planejando e executando tarefa..."):
                    status, report_path = run_task_exec(router, objective)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Task exec: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                summary = summarize_task_exec_report(report_path)
                if summary:
                    CONSOLE.print(summary)
                continue

            if user_input.startswith("/internet "):
                with atena_thinking("Pesquisando na internet..."):
                    answer = run_user_internet_research(user_input)
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA:\n{answer}\n")
                continue

            if user_input.startswith("/saas-bootstrap "):
                project_name = user_input[len("/saas-bootstrap "):].strip()
                with atena_thinking("Gerando stack SaaS completa..."):
                    status, report_path = run_saas_bootstrap(project_name)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]SaaS bootstrap: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/telemetry-insights":
                CONSOLE.print(Panel(telemetry_insights(), title="[bold cyan]Telemetry Insights[/bold cyan]", border_style="cyan"))
                continue

            # Processamento de Tarefas (Task)
            if user_input.startswith("/task "):
                task_msg = user_input[6:].strip()
                if _is_internet_request(task_msg) or _is_web_fact_question(task_msg):
                    with atena_thinking("Pesquisando na internet..."):
                        answer = run_user_internet_research(task_msg)
                    if HAS_RICH:
                        CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                    else:
                        print(f"\nATENA:\n{answer}\n")
                    continue
                structured_five = _wants_five_topics(task_msg)
                effective_prompt = _build_five_topics_prompt(task_msg) if structured_five else task_msg
                with atena_thinking("Processando tarefa..."):
                    try:
                        answer = router_generate_with_timeout(
                            router=router,
                            prompt=effective_prompt,
                            context="Claude Code Style Assistant",
                            timeout_seconds=ROUTER_TIMEOUT_SECONDS,
                        )
                        if structured_five:
                            answer = _format_five_topics_response(answer, task_msg)
                    except Exception as exc:
                        answer = f"Timeout/erro ao gerar resposta ({type(exc).__name__}). Tente novamente com /task-exec."
                
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA:\n{answer}\n")
                continue

            # Comando padrão (se não começar com / assume-se /task)
            if not user_input.startswith("/"):
                if _is_internet_request(user_input) or _is_web_fact_question(user_input):
                    with atena_thinking("Pesquisando na internet..."):
                        answer = run_user_internet_research(user_input)
                    if HAS_RICH:
                        CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                    else:
                        print(f"\nATENA:\n{answer}\n")
                    continue
                structured_five = _wants_five_topics(user_input)
                effective_prompt = _build_five_topics_prompt(user_input) if structured_five else user_input
                with atena_thinking("Analisando..."):
                    try:
                        answer = router_generate_with_timeout(
                            router=router,
                            prompt=effective_prompt,
                            context="Claude Code Style Assistant",
                            timeout_seconds=ROUTER_TIMEOUT_SECONDS,
                        )
                        if structured_five:
                            answer = _format_five_topics_response(answer, user_input)
                    except Exception as exc:
                        answer = f"Timeout/erro ao gerar resposta ({type(exc).__name__}). Use /task-exec para fluxo estruturado."
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA:\n{answer}\n")
                continue

            console_print(
                f"[yellow]Comando desconhecido: {user_input}. Digite /help para ajuda.[/yellow]"
                if HAS_RICH
                else f"Comando desconhecido: {user_input}. Digite /help para ajuda."
            )

        except EOFError:
            evolution_state.running = False
            evolution_state.wake_event.set()
            if HAS_RICH:
                CONSOLE.print("\n[yellow]Entrada finalizada (EOF). Encerrando assistente.[/yellow]")
            else:
                print("\nEntrada finalizada (EOF). Encerrando assistente.")
            break
        except KeyboardInterrupt:
            console_print(
                "\n[yellow]Interrompido pelo usuário. Digite /exit para sair.[/yellow]"
                if HAS_RICH
                else "\nInterrompido pelo usuário. Digite /exit para sair."
            )
        except Exception as e:
            console_print(f"[bold red]Erro:[/bold red] {str(e)}" if HAS_RICH else f"Erro: {str(e)}")

if __name__ == "__main__":
    sys.exit(main())
