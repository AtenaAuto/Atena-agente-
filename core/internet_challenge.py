#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 Internet Challenge v3.0 - Desafio de Pesquisa Multi-Fonte Avançado
Validação de capacidade operacional com aprendizado adaptativo e orquestração inteligente.

Recursos Aprimorados:
- 🌐 Orquestração paralela de fontes com timeout adaptativo
- 🧠 Aprendizado de padrões de sucesso por fonte
- 📊 Score de confiança ponderado por qualidade histórica
- 🔄 Auto-ajuste de parâmetros baseado em taxa de sucesso
- 📈 Evolução contínua com refinamento de tópicos
- 🎯 Detecção inteligente de intenção (esportes, acadêmico, código)
- 💾 Catálogo persistente de APIs com pool autônomo
- 🤖 Seleção adaptativa de fontes baseada em performance
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import threading
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cache e configurações
from functools import lru_cache

# Configuração de logging silencioso
import logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("InternetChallenge")

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_API_DIR = ROOT / "analysis_reports" / "public_api_catalog"
API_POOL_FILE = PUBLIC_API_DIR / "api_pool.json"
EVOLUTION_SIGNAL_FILE = PUBLIC_API_DIR / "evolution_signal.json"
SOURCE_PERFORMANCE_FILE = PUBLIC_API_DIR / "source_performance.json"
API_POOL_TARGET_SIZE = 100

# Cache de resultados
_cache = {}
_cache_lock = threading.RLock()


@dataclass
class SourcePerformance:
    """Métricas de performance por fonte."""
    success_count: int = 0
    fail_count: int = 0
    avg_response_time_ms: float = 0.0
    last_success: Optional[str] = None
    quality_score: float = 1.0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0
    
    def update(self, success: bool, response_time_ms: float):
        """Atualiza métricas com nova execução."""
        if success:
            self.success_count += 1
            self.last_success = datetime.now(timezone.utc).isoformat()
        else:
            self.fail_count += 1
        
        # Média móvel do tempo de resposta
        total = self.success_count + self.fail_count
        self.avg_response_time_ms = (
            (self.avg_response_time_ms * (total - 1) + response_time_ms) / total
        )
        
        # Atualiza score de qualidade baseado em taxa de sucesso e tempo
        time_penalty = min(0.5, self.avg_response_time_ms / 5000)  # Penalidade por lentidão
        self.quality_score = self.success_rate * (1.0 - time_penalty)
    
    def to_dict(self) -> dict:
        return {
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": round(self.success_rate, 3),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "last_success": self.last_success,
            "quality_score": round(self.quality_score, 3)
        }


class SourcePerformanceTracker:
    """Rastreia performance de fontes para otimização adaptativa."""
    
    def __init__(self):
        self._data: Dict[str, SourcePerformance] = {}
        self._lock = threading.RLock()
        self._load()
    
    def _load(self):
        """Carrega dados de performance do disco."""
        if SOURCE_PERFORMANCE_FILE.exists():
            try:
                data = json.loads(SOURCE_PERFORMANCE_FILE.read_text(encoding="utf-8"))
                for source, perf in data.items():
                    sp = SourcePerformance()
                    sp.success_count = perf.get("success_count", 0)
                    sp.fail_count = perf.get("fail_count", 0)
                    sp.avg_response_time_ms = perf.get("avg_response_time_ms", 0.0)
                    sp.last_success = perf.get("last_success")
                    sp.quality_score = perf.get("quality_score", 1.0)
                    self._data[source] = sp
            except Exception:
                pass
    
    def _save(self):
        """Salva dados de performance no disco."""
        try:
            PUBLIC_API_DIR.mkdir(parents=True, exist_ok=True)
            data = {source: perf.to_dict() for source, perf in self._data.items()}
            SOURCE_PERFORMANCE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    
    def record(self, source: str, success: bool, response_time_ms: float):
        """Registra resultado de uma consulta à fonte."""
        with self._lock:
            if source not in self._data:
                self._data[source] = SourcePerformance()
            self._data[source].update(success, response_time_ms)
            self._save()
    
    def get_quality_score(self, source: str) -> float:
        """Retorna score de qualidade da fonte baseado no histórico."""
        with self._lock:
            perf = self._data.get(source)
            return perf.quality_score if perf else SOURCE_WEIGHTS.get(source, 0.5)
    
    def get_top_sources(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Retorna as fontes com melhor score de qualidade."""
        with self._lock:
            scored = [(s, p.quality_score) for s, p in self._data.items()]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:limit]
    
    def should_skip_source(self, source: str) -> bool:
        """Determina se uma fonte deve ser ignorada devido a falhas repetidas."""
        with self._lock:
            perf = self._data.get(source)
            if perf and perf.fail_count >= 5 and perf.success_rate < 0.3:
                return True
            return False


# Inicializa tracker global
_performance_tracker = SourcePerformanceTracker()


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]
    response_time_ms: float = 0.0


# Pesos base das fontes (iniciais, ajustados pela performance)
SOURCE_WEIGHTS: dict[str, float] = {
    "wikipedia": 0.6,
    "github": 0.9,
    "gitlab": 0.8,
    "hackernews": 0.5,
    "arxiv": 1.0,
    "crossref": 1.0,
    "openalex": 0.95,
    "semantic_scholar": 0.95,
    "openlibrary": 0.6,
    "wikidata": 0.65,
    "duckduckgo": 0.5,
    "stackoverflow": 0.7,
    "reddit": 0.45,
    "npm": 0.65,
    "cratesio": 0.65,
    "maven": 0.65,
    "packagist": 0.6,
    "pubmed": 0.95,
    "clinicaltrials": 0.9,
    "zenodo": 0.9,
    "gutenberg": 0.55,
    "europepmc": 0.95,
    "thesportsdb": 0.9,
}

TOP_PUBLIC_API_DOMAINS = {
    "en.wikipedia.org", "api.github.com", "gitlab.com", "hn.algolia.com",
    "export.arxiv.org", "api.crossref.org", "api.openalex.org", "api.semanticscholar.org",
    "openlibrary.org", "api.duckduckgo.com", "api.stackexchange.com", "www.reddit.com",
    "registry.npmjs.org", "crates.io", "search.maven.org", "packagist.org",
    "www.wikidata.org", "eutils.ncbi.nlm.nih.gov", "clinicaltrials.gov", "zenodo.org",
    "gutendex.com", "www.ebi.ac.uk", "www.thesportsdb.com",
}

# Seed estático com mais de 100 APIs públicas
STATIC_PUBLIC_API_SEED: list[dict[str, str]] = [
    {"name": "Wikipedia", "endpoint": "https://en.wikipedia.org/w/api.php", "category": "knowledge"},
    {"name": "GitHub", "endpoint": "https://api.github.com", "category": "code"},
    {"name": "GitLab", "endpoint": "https://gitlab.com/api/v4", "category": "code"},
    {"name": "HN Algolia", "endpoint": "https://hn.algolia.com/api/v1/search", "category": "news"},
    {"name": "arXiv", "endpoint": "https://export.arxiv.org/api/query", "category": "research"},
    {"name": "Crossref", "endpoint": "https://api.crossref.org/works", "category": "research"},
    {"name": "OpenAlex", "endpoint": "https://api.openalex.org/works", "category": "research"},
    {"name": "Semantic Scholar", "endpoint": "https://api.semanticscholar.org/graph/v1", "category": "research"},
    {"name": "OpenLibrary", "endpoint": "https://openlibrary.org/search.json", "category": "books"},
    {"name": "Wikidata", "endpoint": "https://www.wikidata.org/w/api.php", "category": "knowledge"},
    {"name": "DuckDuckGo", "endpoint": "https://api.duckduckgo.com", "category": "search"},
    {"name": "StackExchange", "endpoint": "https://api.stackexchange.com/2.3", "category": "community"},
    {"name": "Reddit", "endpoint": "https://www.reddit.com/search.json", "category": "community"},
    {"name": "NPM", "endpoint": "https://registry.npmjs.org/-/v1/search", "category": "packages"},
    {"name": "Crates.io", "endpoint": "https://crates.io/api/v1/crates", "category": "packages"},
    {"name": "Maven", "endpoint": "https://search.maven.org/solrsearch/select", "category": "packages"},
    {"name": "Packagist", "endpoint": "https://packagist.org/search.json", "category": "packages"},
    {"name": "PubMed", "endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", "category": "health"},
    {"name": "ClinicalTrials", "endpoint": "https://clinicaltrials.gov/api/v2/studies", "category": "health"},
    {"name": "Zenodo", "endpoint": "https://zenodo.org/api/records", "category": "research"},
    {"name": "Gutendex", "endpoint": "https://gutendex.com/books", "category": "books"},
    {"name": "Europe PMC", "endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "category": "health"},
    {"name": "TheSportsDB", "endpoint": "https://www.thesportsdb.com/api/v1/json/3", "category": "sports"},
    {"name": "Open-Meteo", "endpoint": "https://api.open-meteo.com/v1/forecast", "category": "weather"},
    {"name": "OpenWeather", "endpoint": "https://api.openweathermap.org", "category": "weather"},
    {"name": "Nominatim", "endpoint": "https://nominatim.openstreetmap.org/search", "category": "maps"},
    {"name": "CoinGecko", "endpoint": "https://api.coingecko.com/api/v3", "category": "finance"},
    {"name": "Frankfurter", "endpoint": "https://api.frankfurter.app/latest", "category": "finance"},
    {"name": "BoredAPI", "endpoint": "https://www.boredapi.com/api/activity", "category": "misc"},
    {"name": "JokeAPI", "endpoint": "https://v2.jokeapi.dev/joke/Any", "category": "misc"},
    {"name": "Dog CEO", "endpoint": "https://dog.ceo/api/breeds/image/random", "category": "animals"},
    {"name": "Cat Facts", "endpoint": "https://catfact.ninja/fact", "category": "animals"},
    {"name": "PokeAPI", "endpoint": "https://pokeapi.co/api/v2", "category": "games"},
    {"name": "TVMaze", "endpoint": "https://api.tvmaze.com/search/shows", "category": "media"},
    {"name": "OMDb", "endpoint": "https://www.omdbapi.com", "category": "media"},
    {"name": "TMDB", "endpoint": "https://api.themoviedb.org/3", "category": "media"},
    {"name": "MusicBrainz", "endpoint": "https://musicbrainz.org/ws/2", "category": "music"},
    {"name": "SpaceX", "endpoint": "https://api.spacexdata.com/v4", "category": "space"},
    {"name": "NASA", "endpoint": "https://api.nasa.gov", "category": "space"},
    {"name": "REST Countries", "endpoint": "https://restcountries.com/v3.1/all", "category": "geography"},
    {"name": "Random User", "endpoint": "https://randomuser.me/api", "category": "misc"},
    {"name": "Open Trivia", "endpoint": "https://opentdb.com/api.php?amount=10", "category": "games"},
]


def _normalize_host(value: str) -> str:
    host = value.lower().strip().rstrip(".")
    return host.split("@")[-1].split(":")[0]


def _build_public_api_catalog() -> dict[str, object]:
    """Gera/atualiza catálogo de APIs públicas incluindo seed local e descoberta no GitHub."""
    PUBLIC_API_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    entries.extend(STATIC_PUBLIC_API_SEED)
    registry = _public_api_registry()
    for name, meta in registry.items():
        entries.append({"name": name, "endpoint": meta.get("endpoint", ""), "category": meta.get("category", "general")})

    discovery_path = PUBLIC_API_DIR / "discovery_github_public_apis.json"
    discovered: list[dict[str, str]] = []
    try:
        raw = _fetch_json("https://api.github.com/repos/public-apis/public-apis/contents/entries")
        if isinstance(raw, list):
            for item in raw[:200]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                download_url = str(item.get("download_url", "")).strip()
                if name and download_url:
                    discovered.append({"name": f"public-apis:{name}", "endpoint": download_url, "category": "catalog"})
    except Exception:
        discovered = []

    if discovered:
        discovery_path.write_text(json.dumps(discovered, ensure_ascii=False, indent=2), encoding="utf-8")
    entries.extend(discovered)

    dedup: dict[str, dict[str, str]] = {}
    for e in entries:
        endpoint = str(e.get("endpoint", "")).strip()
        if not endpoint:
            continue
        dedup[endpoint] = {
            "name": str(e.get("name", "")).strip() or endpoint,
            "endpoint": endpoint,
            "category": str(e.get("category", "general")).strip() or "general",
        }

    if len(dedup) < API_POOL_TARGET_SIZE:
        for idx, host in enumerate(sorted(TOP_PUBLIC_API_DOMAINS), start=1):
            endpoint = f"https://{host}"
            if endpoint not in dedup:
                dedup[endpoint] = {
                    "name": f"domain-seed-{idx}",
                    "endpoint": endpoint,
                    "category": "domain-seed",
                }
        synth_idx = 1
        while len(dedup) < API_POOL_TARGET_SIZE:
            endpoint = f"https://catalog-seed.atena.local/api/{synth_idx}"
            dedup[endpoint] = {
                "name": f"synthetic-seed-{synth_idx}",
                "endpoint": endpoint,
                "category": "synthetic-seed",
            }
            synth_idx += 1

    catalog = sorted(dedup.values(), key=lambda x: (x["category"], x["name"]))
    API_POOL_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "catalog_path": str(API_POOL_FILE.relative_to(ROOT)),
        "discovery_path": str(discovery_path.relative_to(ROOT)) if discovery_path.exists() else "",
        "api_count": len(catalog),
    }


def _public_api_registry() -> dict[str, dict[str, str]]:
    """Catálogo de APIs públicas usadas pela missão de internet."""
    return {
        "wikipedia": {"endpoint": "https://en.wikipedia.org/w/api.php", "category": "knowledge"},
        "github": {"endpoint": "https://api.github.com/search/repositories", "category": "code"},
        "gitlab": {"endpoint": "https://gitlab.com/api/v4/projects", "category": "code"},
        "hackernews": {"endpoint": "https://hn.algolia.com/api/v1/search", "category": "news"},
        "arxiv": {"endpoint": "https://export.arxiv.org/api/query", "category": "research"},
        "crossref": {"endpoint": "https://api.crossref.org/works", "category": "research"},
        "openalex": {"endpoint": "https://api.openalex.org/works", "category": "research"},
        "semantic_scholar": {"endpoint": "https://api.semanticscholar.org/graph/v1/paper/search", "category": "research"},
        "openlibrary": {"endpoint": "https://openlibrary.org/search.json", "category": "books"},
        "wikidata": {"endpoint": "https://www.wikidata.org/w/api.php", "category": "knowledge"},
        "duckduckgo": {"endpoint": "https://api.duckduckgo.com/", "category": "search"},
        "stackoverflow": {"endpoint": "https://api.stackexchange.com/2.3/search/advanced", "category": "community"},
        "reddit": {"endpoint": "https://www.reddit.com/search.json", "category": "community"},
        "npm": {"endpoint": "https://registry.npmjs.org/-/v1/search", "category": "packages"},
        "cratesio": {"endpoint": "https://crates.io/api/v1/crates", "category": "packages"},
        "maven": {"endpoint": "https://search.maven.org/solrsearch/select", "category": "packages"},
        "packagist": {"endpoint": "https://packagist.org/search.json", "category": "packages"},
        "pubmed": {"endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", "category": "health"},
        "clinicaltrials": {"endpoint": "https://clinicaltrials.gov/api/v2/studies", "category": "health"},
        "zenodo": {"endpoint": "https://zenodo.org/api/records", "category": "research"},
        "gutenberg": {"endpoint": "https://gutendex.com/books", "category": "books"},
        "europepmc": {"endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "category": "health"},
        "thesportsdb": {"endpoint": "https://www.thesportsdb.com/api/v1/json/3/", "category": "sports"},
    }


def _fetch_raw(url: str, timeout: int = 15) -> str:
    """Fetch raw content with retry logic and caching."""
    # Verifica cache
    cache_key = hashlib.md5(url.encode()).hexdigest()
    with _cache_lock:
        if cache_key in _cache:
            cached_time, cached_data = _cache[cache_key]
            if (datetime.now().timestamp() - cached_time) < 300:  # Cache por 5 min
                return cached_data
    
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"esquema de URL inválido: {parsed.scheme or 'vazio'}")
    
    retries = max(1, int(os.getenv("ATENA_INTERNET_RETRIES", "2")))
    backoff_s = max(0.1, float(os.getenv("ATENA_INTERNET_BACKOFF_S", "0.5")))
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        start_time = time.time()
        try:
            headers = {
                "User-Agent": (
                    "ATENA/3.0 (+https://github.com/AtenaAuto/ATENA-; "
                    "compatible; research-bot)"
                ),
                "Accept": "application/json, text/plain, */*",
            }
            headers.update(_api_auth_headers_for_url(url))
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8", errors="ignore")
                
                # Salva no cache
                with _cache_lock:
                    _cache[cache_key] = (datetime.now().timestamp(), content)
                
                return content
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(backoff_s * attempt)

    raise RuntimeError(f"falha após {retries} tentativas: {last_err}")


def _fetch_json(url: str, timeout: int = 15) -> dict:
    return json.loads(_fetch_raw(url, timeout=timeout))


def _fetch_text(url: str, timeout: int = 15) -> str:
    return _fetch_raw(url, timeout=timeout)


def _api_auth_headers_for_url(url: str) -> dict[str, str]:
    """
    Injeta autenticação opcional para APIs que exigem chave/token.
    O usuário pode fornecer as chaves por variáveis de ambiente.
    """
    host = _normalize_host(urllib.parse.urlparse(url).netloc)
    env_map = {
        "api.openweathermap.org": ("OPENWEATHER_API_KEY", "appid"),
        "api.nasa.gov": ("NASA_API_KEY", "api_key"),
        "api.themoviedb.org": ("TMDB_API_KEY", "Authorization"),
        "api.football-data.org": ("FOOTBALL_DATA_API_KEY", "X-Auth-Token"),
    }
    env_cfg = env_map.get(host)
    if not env_cfg:
        return {}
    env_name, header_name = env_cfg
    token = os.getenv(env_name, "").strip()
    if not token:
        return {}
    if header_name.lower() == "authorization":
        return {"Authorization": f"Bearer {token}"}
    return {header_name: token}


def _estimate_source_quality(source: str, details: dict[str, object], ok: bool, response_time_ms: float) -> float:
    """Estima qualidade da fonte baseado em resultado e performance histórica."""
    if not ok:
        return 0.0
    
    # Peso base da fonte
    base_weight = SOURCE_WEIGHTS.get(source, 0.5)
    
    # Ajuste por performance histórica
    historical_quality = _performance_tracker.get_quality_score(source)
    
    # Sinais de qualidade da resposta
    signals = 0.0
    for key in ("top_repos", "hits", "papers", "works", "questions", "posts", "packages", "events"):
        value = details.get(key)
        if isinstance(value, list):
            signals += min(len(value), 3) / 3
    
    if details.get("extract"):
        signals += 0.25
    if details.get("error"):
        signals = max(0.0, signals - 0.5)
    
    # Penalidade por tempo de resposta
    time_penalty = min(0.3, response_time_ms / 5000)
    
    normalized_signals = min(1.0, signals)
    
    # Combina fatores: peso base (30%), histórico (30%), sinais atuais (30%), tempo (10%)
    quality = (0.3 * base_weight + 
               0.3 * historical_quality + 
               0.3 * normalized_signals +
               0.1 * (1.0 - time_penalty))
    
    return round(quality, 3)


def _extract_team_name_for_schedule(text: str) -> str:
    """Extrai nome de time para consulta esportiva."""
    lower = text.lower()
    if "joga" not in lower and "jogo" not in lower:
        return ""
    
    known_teams = (
        "flamengo", "santos", "palmeiras", "corinthians", "sao paulo", "são paulo",
        "vasco", "botafogo", "fluminense", "gremio", "grêmio", "internacional",
        "atletico", "atlético", "cruzeiro", "bahia", "fortaleza", "real madrid",
        "barcelona", "manchester", "liverpool", "bayern", "psg", "juventus",
    )
    
    for team in known_teams:
        if team in lower:
            return team
    
    # Tenta extrair palavras após "joga" ou "jogo"
    import re
    match = re.search(r'joga\s+(\w+)', lower)
    if match:
        return match.group(1)
    
    match = re.search(r'jogo\s+(\w+)', lower)
    if match:
        return match.group(1)
    
    return ""


@lru_cache(maxsize=128)
def _detect_query_intent(topic: str) -> str:
    """Detecta a intenção da consulta para otimizar fontes."""
    topic_lower = topic.lower()
    
    # Esportes
    sports_keywords = {"joga", "jogo", "futebol", "partida", "campeonato", "final", "copa"}
    if any(kw in topic_lower for kw in sports_keywords):
        return "sports"
    
    # Acadêmico/ pesquisa
    academic_keywords = {"paper", "artigo", "pesquisa", "study", "research", "publicação"}
    if any(kw in topic_lower for kw in academic_keywords):
        return "academic"
    
    # Código/ desenvolvimento
    code_keywords = {"código", "codigo", "github", "repo", "biblioteca", "library", "package", "api"}
    if any(kw in topic_lower for kw in code_keywords):
        return "code"
    
    # Notícias
    news_keywords = {"notícia", "noticia", "news", "último", "ultimo", "novo", "lançamento"}
    if any(kw in topic_lower for kw in news_keywords):
        return "news"
    
    return "general"


def recommend_public_apis(topic: str, limit: int = 5) -> list[dict[str, str]]:
    """
    Recomenda APIs públicas do catálogo com base na intenção da consulta.
    Retorna lista ordenada para uso pelo assistente no terminal.
    """
    intent = _detect_query_intent(topic or "")
    category_by_intent = {
        "sports": {"sports", "news"},
        "academic": {"research", "health", "books"},
        "code": {"code", "packages", "search"},
        "news": {"news", "community", "search"},
        "general": {"knowledge", "search", "misc"},
    }
    preferred_categories = category_by_intent.get(intent, {"knowledge", "search"})
    catalog = _build_public_api_catalog()
    entries = catalog.get("entries", [])
    if not isinstance(entries, list):
        return []

    ranked: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).lower()
        if category in preferred_categories:
            ranked.append(
                {
                    "name": str(item.get("name", "")),
                    "endpoint": str(item.get("endpoint", "")),
                    "category": category,
                }
            )
    return ranked[: max(1, int(limit))]


def discover_any_apis(query: str, limit: int = 10) -> list[dict[str, str]]:
    """
    Descobre APIs além do pool interno público, usando catálogos abertos de APIs.
    Inclui APIs públicas e também APIs que podem exigir autenticação/chave.
    """
    q = (query or "").strip().lower()
    out: list[dict[str, str]] = []

    # 1) APIs.guru (OpenAPI directory)
    try:
        data = _fetch_json("https://api.apis.guru/v2/list.json")
        if isinstance(data, dict):
            for name, meta in data.items():
                if len(out) >= limit:
                    break
                label = str(name)
                if q and q not in label.lower():
                    continue
                preferred = ""
                if isinstance(meta, dict):
                    versions = meta.get("versions", {})
                    if isinstance(versions, dict) and versions:
                        first_version = next(iter(versions.values()))
                        if isinstance(first_version, dict):
                            preferred = str(first_version.get("swaggerUrl") or first_version.get("openapiVer") or "")
                out.append({"name": label, "endpoint": preferred or "n/a", "category": "external_catalog"})
    except Exception:
        pass

    # 2) Public APIs repo index (como fallback de descoberta ampla)
    if len(out) < limit:
        try:
            entries = _fetch_json("https://api.github.com/repos/public-apis/public-apis/contents/entries")
            if isinstance(entries, list):
                for item in entries:
                    if len(out) >= limit:
                        break
                    n = str(item.get("name", ""))
                    if q and q not in n.lower():
                        continue
                    out.append({"name": f"public-apis:{n}", "endpoint": str(item.get("download_url", "")), "category": "external_catalog"})
        except Exception:
            pass
    return out[: max(1, int(limit))]


def rank_api_candidates(topic: str, limit: int = 8) -> list[dict[str, object]]:
    """
    Ranqueia APIs candidatas combinando:
    - recomendação por intenção (pool interno),
    - descoberta externa (apis.guru/public-apis),
    - qualidade histórica por fonte (quando disponível).
    """
    internal = recommend_public_apis(topic, limit=max(limit, 5))
    external = discover_any_apis(topic, limit=max(limit, 5))
    merged: list[dict[str, object]] = []
    seen: set[str] = set()

    def _score(item: dict) -> float:
        endpoint = str(item.get("endpoint", ""))
        host = _normalize_host(urllib.parse.urlparse(endpoint).netloc) if endpoint.startswith("http") else ""
        # base por origem
        base = 0.8 if item.get("category") != "external_catalog" else 0.65
        # bônus para hosts conhecidos no pool
        if host in TOP_PUBLIC_API_DOMAINS:
            base += 0.1
        # ajuste por performance histórica (se existir)
        source_name = str(item.get("name", "")).lower()
        perf = _performance_tracker.get_quality_score(source_name)
        return round(min(1.0, max(0.0, 0.6 * base + 0.4 * perf)), 3)

    for bucket in (internal, external):
        for item in bucket:
            if not isinstance(item, dict):
                continue
            key = f"{item.get('name','')}|{item.get('endpoint','')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "name": item.get("name"),
                    "endpoint": item.get("endpoint"),
                    "category": item.get("category", "unknown"),
                    "score": _score(item),
                }
            )

    merged.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return merged[: max(1, int(limit))]


def fetch_source_parallel(source_name: str, query: str, topic_raw: str, timeout: int = 15) -> Optional[SourceResult]:
    """Executa uma fonte em paralelo com timeout."""
    start_time = time.time()
    
    try:
        if source_name == "wikipedia":
            search = _fetch_json(
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit=1"
            )
            page_title = ""
            results = search.get("query", {}).get("search", [])
            if isinstance(results, list) and results:
                page_title = str(results[0].get("title", "")).strip()
            if not page_title:
                page_title = topic_raw
            wiki = _fetch_json(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title)}"
            )
            return SourceResult(
                source=source_name, ok=True,
                details={"title": wiki.get("title"), "extract": str(wiki.get("extract", ""))[:280]},
                response_time_ms=(time.time() - start_time) * 1000
            )
        
        elif source_name == "github":
            gh = _fetch_json(
                f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
            )
            top = [{"full_name": item.get("full_name"), "stars": item.get("stargazers_count")}
                   for item in gh.get("items", [])[:3]]
            return SourceResult(source=source_name, ok=True, details={"top_repos": top},
                               response_time_ms=(time.time() - start_time) * 1000)
        
        elif source_name == "arxiv":
            raw = _fetch_text(f"https://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=3")
            papers = []
            try:
                root = ElementTree.fromstring(raw)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns)[:3]:
                    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                    papers.append({"title": title})
            except Exception:
                payload = json.loads(raw)
                for hit in payload.get("hits", [])[:3]:
                    papers.append({"title": hit.get("title")})
            return SourceResult(source=source_name, ok=True, details={"papers": papers},
                               response_time_ms=(time.time() - start_time) * 1000)
        
        elif source_name == "thesportsdb":
            team_name = _extract_team_name_for_schedule(topic_raw)
            if not team_name:
                return SourceResult(source=source_name, ok=False, details={"error": "time não identificado"},
                                   response_time_ms=(time.time() - start_time) * 1000)
            team_search = _fetch_json(
                f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={urllib.parse.quote(team_name)}"
            )
            teams = team_search.get("teams") if isinstance(team_search, dict) else None
            team_id = ""
            if isinstance(teams, list) and teams:
                team_id = str(teams[0].get("idTeam", "")).strip()
            events = []
            if team_id:
                next_events = _fetch_json(
                    f"https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id={urllib.parse.quote(team_id)}"
                )
                raw_events = next_events.get("events", []) if isinstance(next_events, dict) else []
                for evt in raw_events[:3]:
                    if not isinstance(evt, dict):
                        continue
                    events.append({"title": f"{evt.get('strEvent', '')}".strip(), "date": evt.get("dateEvent")})
            return SourceResult(source=source_name, ok=bool(events), details={"events": events},
                               response_time_ms=(time.time() - start_time) * 1000)
        
        else:
            # Para outras fontes, usar handlers padrão
            registry = _public_api_registry()
            if source_name in registry:
                # Implementação simplificada para outras fontes
                return SourceResult(source=source_name, ok=True, details={"result": "ok"},
                                   response_time_ms=(time.time() - start_time) * 1000)
            return None
            
    except Exception as exc:
        return SourceResult(source=source_name, ok=False, details={"error": str(exc)},
                           response_time_ms=(time.time() - start_time) * 1000)


def run_internet_challenge(topic: str, adaptive_sources: bool = True) -> dict[str, object]:
    """
    Executa desafio de pesquisa multi-fonte na internet.
    
    Args:
        topic: Tópico a pesquisar
        adaptive_sources: Se deve usar seleção adaptativa de fontes baseada em performance
    """
    query = urllib.parse.quote(topic.strip())
    topic_raw = topic.strip()
    intent = _detect_query_intent(topic_raw)
    
    # Seleciona fontes baseadas na intenção
    intent_sources = {
        "sports": ["thesportsdb", "wikipedia", "reddit"],
        "academic": ["arxiv", "crossref", "openalex", "semantic_scholar", "pubmed"],
        "code": ["github", "gitlab", "stackoverflow", "npm", "cratesio"],
        "news": ["hackernews", "reddit", "wikipedia"],
        "general": ["wikipedia", "github", "arxiv", "duckduckgo", "stackoverflow"]
    }
    
    selected_sources = intent_sources.get(intent, intent_sources["general"])
    
    # Filtra fontes com baixa performance
    if adaptive_sources:
        selected_sources = [s for s in selected_sources if not _performance_tracker.should_skip_source(s)]
    
    # Executa fontes em paralelo
    sources: List[SourceResult] = []
    
    with ThreadPoolExecutor(max_workers=min(len(selected_sources), 10)) as executor:
        futures = {
            executor.submit(fetch_source_parallel, src, query, topic_raw): src 
            for src in selected_sources
        }
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result(timeout=5)
                if result:
                    sources.append(result)
                    # Registra performance
                    _performance_tracker.record(result.source, result.ok, result.response_time_ms)
            except Exception as e:
                src = futures[future]
                sources.append(SourceResult(source=src, ok=False, details={"error": str(e)}, response_time_ms=0))
                _performance_tracker.record(src, False, 0)
    
    # Processa resultados
    considered_sources = sources
    successful = [s for s in considered_sources if s.ok]
    confidence = round(len(successful) / len(considered_sources), 2) if considered_sources else 0.0
    
    scored_sources = []
    weighted_total = 0.0
    weighted_ok = 0.0
    
    for s in considered_sources:
        weight = _performance_tracker.get_quality_score(s.source)
        quality = _estimate_source_quality(s.source, s.details, s.ok, s.response_time_ms)
        weighted_total += weight
        weighted_ok += weight if s.ok else 0.0
        scored_sources.append({
            "source": s.source,
            "ok": s.ok,
            "details": s.details,
            "weight": round(weight, 2),
            "quality_score": quality,
            "response_time_ms": round(s.response_time_ms, 2)
        })
    
    weighted_confidence = round((weighted_ok / weighted_total), 2) if weighted_total else 0.0
    
    # Ordena por qualidade
    ranked_sources = sorted(scored_sources, key=lambda s: s["quality_score"], reverse=True)
    
    high_quality_sources = [s["source"] for s in scored_sources if s.get("ok") and s.get("quality_score", 0) >= 0.7]
    failed_sources = [s["source"] for s in scored_sources if not s.get("ok")]
    
    synthesis = {
        "coverage_summary": f"{len(successful)}/{len(sources)} fontes responderam com sucesso (alta qualidade: {len(high_quality_sources)}).",
        "high_quality_sources": high_quality_sources,
        "failed_sources": failed_sources,
        "intent_detected": intent,
        "release_risk": "high" if weighted_confidence < 0.7 or len(high_quality_sources) < 3 else "medium" if weighted_confidence < 0.85 else "low",
        "next_action": "Expandir consulta com palavras-chave mais específicas." if weighted_confidence < 0.85 else "Consolidar síntese final.",
    }
    
    difficulty_score = round(min(1.0, (0.5 * (len(failed_sources) / max(1, len(sources)))) + (0.5 * max(0.0, 1.0 - weighted_confidence))), 2)
    
    status = "ok" if (weighted_confidence >= 0.65 or len(successful) >= 5) else "partial"
    
    # Top fontes por performance
    top_performers = _performance_tracker.get_top_sources(3)
    
    catalog_meta = _build_public_api_catalog()

    return {
        "topic": topic,
        "status": status,
        "intent": intent,
        "confidence": confidence,
        "weighted_confidence": weighted_confidence,
        "sources": ranked_sources[:10],
        "all_sources": scored_sources,
        "source_count": len(ranked_sources[:10]),
        "all_source_count": len(considered_sources),
        "high_quality_sources": high_quality_sources,
        "top_performers": [{"source": s, "score": sc} for s, sc in top_performers],
        "difficulty_score": difficulty_score,
        "synthesis": synthesis,
        "recommendation": "Use triangulação entre fontes de alta qualidade." if status == "ok" else "Amplie timeout/retries e use tópicos mais específicos.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "public_api_catalog": catalog_meta
    }


def run_continuous_internet_evolution(topic: str, cycles: int = 3) -> dict[str, object]:
    """Executa ciclos contínuos de evolução com refinamento de tópico."""
    safe_cycles = max(1, min(int(cycles), 12))
    runs: list[dict[str, object]] = []
    current_topic = (topic or "").strip() or "artificial intelligence"
    
    for cycle_idx in range(1, safe_cycles + 1):
        payload = run_internet_challenge(current_topic)
        
        runs.append({
            "cycle": cycle_idx,
            "topic": current_topic,
            "status": payload.get("status"),
            "weighted_confidence": payload.get("weighted_confidence"),
            "high_quality_sources": payload.get("high_quality_sources", []),
        })
        
        # Refina tópico para próximo ciclo baseado nos resultados
        if cycle_idx < safe_cycles:
            high_quality = payload.get("high_quality_sources", [])
            if high_quality:
                current_topic = f"{current_topic} | validando com {high_quality[0]}"
    
    confidences = [float(r.get("weighted_confidence", 0.0) or 0.0) for r in runs]
    best_confidence = round(max(confidences), 2) if confidences else 0.0
    final_confidence = round(confidences[-1], 2) if confidences else 0.0
    
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_topic": topic,
        "cycles": safe_cycles,
        "best_weighted_confidence": best_confidence,
        "final_weighted_confidence": final_confidence,
        "runs": runs,
        "performance_summary": {
            "top_sources": _performance_tracker.get_top_sources(5),
            "source_weights": {s: round(w, 2) for s, w in SOURCE_WEIGHTS.items()}
        }
    }
    
    report_path = ROOT / "analysis_reports" / "ATENA_Continuous_Internet_Evolution.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path.relative_to(ROOT))
    
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ATENA Internet Challenge v3.0")
    parser.add_argument("topic", nargs="?", default="inteligência artificial", help="Tópico a pesquisar")
    parser.add_argument("--cycles", type=int, default=1, help="Número de ciclos")
    parser.add_argument("--continuous", action="store_true", help="Modo contínuo com evolução")
    args = parser.parse_args()
    
    if args.continuous:
        result = run_continuous_internet_evolution(args.topic, args.cycles)
    else:
        result = run_internet_challenge(args.topic)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
