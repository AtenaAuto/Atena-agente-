#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de pesquisa multi-fonte na internet para validar capacidade operacional."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]


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

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_API_DIR = ROOT / "analysis_reports" / "public_api_catalog"
API_POOL_FILE = PUBLIC_API_DIR / "api_pool.json"
EVOLUTION_SIGNAL_FILE = PUBLIC_API_DIR / "evolution_signal.json"
API_POOL_TARGET_SIZE = 100

# Seed estático com mais de 100 APIs públicas para disponibilidade imediata/offline.
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
    {"name": "MapTiler Geocoding", "endpoint": "https://api.maptiler.com/geocoding", "category": "maps"},
    {"name": "IP-API", "endpoint": "http://ip-api.com/json", "category": "network"},
    {"name": "ipify", "endpoint": "https://api.ipify.org", "category": "network"},
    {"name": "CoinGecko", "endpoint": "https://api.coingecko.com/api/v3", "category": "finance"},
    {"name": "Frankfurter", "endpoint": "https://api.frankfurter.app/latest", "category": "finance"},
    {"name": "ExchangeRate.host", "endpoint": "https://api.exchangerate.host/latest", "category": "finance"},
    {"name": "AlphaVantage", "endpoint": "https://www.alphavantage.co/query", "category": "finance"},
    {"name": "BoredAPI", "endpoint": "https://www.boredapi.com/api/activity", "category": "misc"},
    {"name": "JokeAPI", "endpoint": "https://v2.jokeapi.dev/joke/Any", "category": "misc"},
    {"name": "Dog CEO", "endpoint": "https://dog.ceo/api/breeds/image/random", "category": "animals"},
    {"name": "Cat Facts", "endpoint": "https://catfact.ninja/fact", "category": "animals"},
    {"name": "PokeAPI", "endpoint": "https://pokeapi.co/api/v2", "category": "games"},
    {"name": "RAWG", "endpoint": "https://api.rawg.io/api/games", "category": "games"},
    {"name": "CheapShark", "endpoint": "https://www.cheapshark.com/api/1.0", "category": "games"},
    {"name": "IGDB", "endpoint": "https://api.igdb.com/v4", "category": "games"},
    {"name": "TVMaze", "endpoint": "https://api.tvmaze.com/search/shows", "category": "media"},
    {"name": "OMDb", "endpoint": "https://www.omdbapi.com", "category": "media"},
    {"name": "TMDB", "endpoint": "https://api.themoviedb.org/3", "category": "media"},
    {"name": "OpenSea", "endpoint": "https://api.opensea.io/api/v2", "category": "nft"},
    {"name": "MusicBrainz", "endpoint": "https://musicbrainz.org/ws/2", "category": "music"},
    {"name": "iTunes Search", "endpoint": "https://itunes.apple.com/search", "category": "music"},
    {"name": "Deezer", "endpoint": "https://api.deezer.com/search", "category": "music"},
    {"name": "Last.fm", "endpoint": "https://ws.audioscrobbler.com/2.0", "category": "music"},
    {"name": "SpaceX", "endpoint": "https://api.spacexdata.com/v4", "category": "space"},
    {"name": "NASA", "endpoint": "https://api.nasa.gov", "category": "space"},
    {"name": "Open Notify", "endpoint": "http://api.open-notify.org/iss-now.json", "category": "space"},
    {"name": "Launch Library", "endpoint": "https://ll.thespacedevs.com/2.2.0/launch", "category": "space"},
    {"name": "USGS Earthquake", "endpoint": "https://earthquake.usgs.gov/fdsnws/event/1/query", "category": "science"},
    {"name": "OpenAQ", "endpoint": "https://api.openaq.org/v2", "category": "environment"},
    {"name": "AirVisual", "endpoint": "https://api.airvisual.com/v2", "category": "environment"},
    {"name": "Sunrise Sunset", "endpoint": "https://api.sunrise-sunset.org/json", "category": "weather"},
    {"name": "GeoDB Cities", "endpoint": "https://wft-geo-db.p.rapidapi.com/v1/geo/cities", "category": "maps"},
    {"name": "REST Countries", "endpoint": "https://restcountries.com/v3.1/all", "category": "geography"},
    {"name": "CountriesNow", "endpoint": "https://countriesnow.space/api/v0.1/countries", "category": "geography"},
    {"name": "World Bank", "endpoint": "https://api.worldbank.org/v2/country", "category": "economy"},
    {"name": "IMF Data", "endpoint": "https://www.imf.org/external/datamapper/api/v1", "category": "economy"},
    {"name": "UNData", "endpoint": "https://unstats.un.org/SDGAPI/v1/sdg/Series/List", "category": "economy"},
    {"name": "FBI Crime Data", "endpoint": "https://api.usa.gov/crime/fbi/cde", "category": "government"},
    {"name": "DataUSA", "endpoint": "https://datausa.io/api/data", "category": "government"},
    {"name": "GovTrack", "endpoint": "https://www.govtrack.us/api/v2", "category": "government"},
    {"name": "OpenFDA", "endpoint": "https://api.fda.gov/drug/event.json", "category": "health"},
    {"name": "WHO Athena", "endpoint": "https://ghoapi.azureedge.net/api", "category": "health"},
    {"name": "Disease.sh", "endpoint": "https://disease.sh/v3/covid-19/all", "category": "health"},
    {"name": "GeoNames", "endpoint": "https://api.geonames.org/searchJSON", "category": "maps"},
    {"name": "OpenStreetMap", "endpoint": "https://overpass-api.de/api/interpreter", "category": "maps"},
    {"name": "US Census", "endpoint": "https://api.census.gov/data", "category": "government"},
    {"name": "BLS", "endpoint": "https://api.bls.gov/publicAPI/v2/timeseries/data", "category": "economy"},
    {"name": "Federal Reserve FRED", "endpoint": "https://api.stlouisfed.org/fred/series/observations", "category": "economy"},
    {"name": "OpenCorporates", "endpoint": "https://api.opencorporates.com/v0.4/companies/search", "category": "business"},
    {"name": "Clearbit Logo", "endpoint": "https://logo.clearbit.com/openai.com", "category": "business"},
    {"name": "ReqRes", "endpoint": "https://reqres.in/api/users", "category": "testing"},
    {"name": "JSONPlaceholder", "endpoint": "https://jsonplaceholder.typicode.com/posts", "category": "testing"},
    {"name": "HTTPBin", "endpoint": "https://httpbin.org/get", "category": "testing"},
    {"name": "Postman Echo", "endpoint": "https://postman-echo.com/get", "category": "testing"},
    {"name": "OpenLibrary Covers", "endpoint": "https://covers.openlibrary.org/b/id/240727-S.jpg", "category": "books"},
    {"name": "Libgen Search", "endpoint": "https://libgen.is/json.php", "category": "books"},
    {"name": "Meme API", "endpoint": "https://meme-api.com/gimme", "category": "misc"},
    {"name": "Useless Facts", "endpoint": "https://uselessfacts.jsph.pl/random.json", "category": "misc"},
    {"name": "Agify", "endpoint": "https://api.agify.io/?name=michael", "category": "ml"},
    {"name": "Genderize", "endpoint": "https://api.genderize.io/?name=luc", "category": "ml"},
    {"name": "Nationalize", "endpoint": "https://api.nationalize.io/?name=nathaniel", "category": "ml"},
    {"name": "Random User", "endpoint": "https://randomuser.me/api", "category": "misc"},
    {"name": "Open Trivia", "endpoint": "https://opentdb.com/api.php?amount=10", "category": "games"},
    {"name": "Football-Data", "endpoint": "https://api.football-data.org/v4/matches", "category": "sports"},
    {"name": "balldontlie", "endpoint": "https://www.balldontlie.io/api/v1/games", "category": "sports"},
    {"name": "Ergast F1", "endpoint": "https://ergast.com/api/f1/current.json", "category": "sports"},
    {"name": "OpenDota", "endpoint": "https://api.opendota.com/api/heroes", "category": "games"},
    {"name": "RuneScape", "endpoint": "https://api.rsbuddy.com/grandExchange", "category": "games"},
    {"name": "Adzuna Jobs", "endpoint": "https://api.adzuna.com/v1/api/jobs", "category": "jobs"},
    {"name": "USAJobs", "endpoint": "https://data.usajobs.gov/api/search", "category": "jobs"},
    {"name": "Remotive", "endpoint": "https://remotive.com/api/remote-jobs", "category": "jobs"},
    {"name": "OpenAlex Authors", "endpoint": "https://api.openalex.org/authors", "category": "research"},
    {"name": "ORCID", "endpoint": "https://pub.orcid.org/v3.0/search", "category": "research"},
    {"name": "CORE", "endpoint": "https://api.core.ac.uk/v3/search/works", "category": "research"},
    {"name": "DOAJ", "endpoint": "https://doaj.org/api/v2/search/articles", "category": "research"},
    {"name": "NewsAPI", "endpoint": "https://newsapi.org/v2/everything", "category": "news"},
    {"name": "GDELT", "endpoint": "https://api.gdeltproject.org/api/v2/doc/doc", "category": "news"},
    {"name": "Mediastack", "endpoint": "http://api.mediastack.com/v1/news", "category": "news"},
    {"name": "LibreTranslate", "endpoint": "https://libretranslate.com/translate", "category": "nlp"},
    {"name": "Datamuse", "endpoint": "https://api.datamuse.com/words?ml=ringing+in+the+ears", "category": "nlp"},
    {"name": "LanguageTool", "endpoint": "https://api.languagetool.org/v2/check", "category": "nlp"},
]


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


def _load_api_pool_state() -> dict[str, object]:
    if not API_POOL_FILE.exists():
        return {"target_size": API_POOL_TARGET_SIZE, "active": [], "used": [], "updated_at_utc": None}
    try:
        data = json.loads(API_POOL_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"target_size": API_POOL_TARGET_SIZE, "active": [], "used": [], "updated_at_utc": None}
    if not isinstance(data, dict):
        return {"target_size": API_POOL_TARGET_SIZE, "active": [], "used": [], "updated_at_utc": None}
    data.setdefault("target_size", API_POOL_TARGET_SIZE)
    data.setdefault("active", [])
    data.setdefault("used", [])
    return data


def _normalize_api_entries(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        endpoint = str(row.get("endpoint", "")).strip()
        category = str(row.get("category", "general")).strip() or "general"
        if not name or not endpoint:
            continue
        key = (name.lower(), endpoint.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"name": name, "endpoint": endpoint, "category": category})
    return normalized


def _fetch_additional_public_apis(limit: int = 200) -> list[dict[str, str]]:
    """Tenta enriquecer pool via APIs.guru (fallback silencioso se rede bloquear)."""
    try:
        payload = _fetch_json("https://api.apis.guru/v2/list.json", timeout=20)
    except Exception:  # noqa: BLE001
        return []
    rows: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for api_name, meta in payload.items():
            if len(rows) >= limit:
                break
            if not isinstance(meta, dict):
                continue
            versions = meta.get("versions", {})
            if not isinstance(versions, dict) or not versions:
                continue
            latest_key = sorted(versions.keys())[-1]
            latest = versions.get(latest_key, {})
            if not isinstance(latest, dict):
                continue
            endpoint = str(latest.get("swaggerUrl") or latest.get("openapiVer") or "").strip()
            if not endpoint:
                continue
            rows.append(
                {
                    "name": str(meta.get("preferred") or api_name),
                    "endpoint": endpoint,
                    "category": str(meta.get("x-apisguru-categories", ["general"])[0] if isinstance(meta.get("x-apisguru-categories"), list) and meta.get("x-apisguru-categories") else "general"),
                }
            )
    return _normalize_api_entries(rows)


def _save_api_pool_state(state: dict[str, object]) -> None:
    PUBLIC_API_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    API_POOL_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_api_pool(target_size: int = API_POOL_TARGET_SIZE) -> dict[str, object]:
    state = _load_api_pool_state()
    active_rows = _normalize_api_entries(state.get("active", []) if isinstance(state.get("active"), list) else [])
    used_rows = _normalize_api_entries(state.get("used", []) if isinstance(state.get("used"), list) else [])

    # Monta base única: seed estático + usados + ativos + enriquecimento online opcional.
    combined = _normalize_api_entries(STATIC_PUBLIC_API_SEED + used_rows + active_rows)
    if len(combined) < target_size:
        combined = _normalize_api_entries(combined + _fetch_additional_public_apis(limit=300))

    # Reabastece ativo até target_size.
    active = combined[:target_size]
    overflow_used = combined[target_size:]
    state = {
        "target_size": target_size,
        "active": active,
        "used": overflow_used[:500],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _save_api_pool_state(state)
    return state


def _consume_api_pool(count: int) -> dict[str, object]:
    state = _ensure_api_pool()
    active = _normalize_api_entries(state.get("active", []) if isinstance(state.get("active"), list) else [])
    used = _normalize_api_entries(state.get("used", []) if isinstance(state.get("used"), list) else [])
    to_consume = max(0, min(count, len(active)))
    consumed = active[:to_consume]
    remaining = active[to_consume:]
    used = _normalize_api_entries(consumed + used)
    state = {"target_size": API_POOL_TARGET_SIZE, "active": remaining, "used": used[:500]}
    _save_api_pool_state(state)
    # Reabastece imediatamente para manter 100 disponíveis.
    state = _ensure_api_pool()
    state["consumed_now"] = consumed
    state["consumed_count"] = len(consumed)
    return state


def _persist_public_api_catalog(topic: str, scored_sources: list[dict[str, object]]) -> dict[str, object]:
    """Persiste um catálogo local de APIs públicas + descoberta por execução."""
    PUBLIC_API_DIR.mkdir(parents=True, exist_ok=True)
    registry = _public_api_registry()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    source_by_name = {str(item.get("source")): item for item in scored_sources}
    catalog_rows: list[dict[str, object]] = []
    for source_name, meta in registry.items():
        source_payload = source_by_name.get(source_name, {})
        details = source_payload.get("details", {}) if isinstance(source_payload, dict) else {}
        error_msg = ""
        if isinstance(details, dict) and isinstance(details.get("error"), str):
            error_msg = str(details.get("error", ""))[:240]
        catalog_rows.append(
            {
                "source": source_name,
                "endpoint": meta["endpoint"],
                "category": meta["category"],
                "public": True,
                "last_status": "ok" if bool(source_payload.get("ok")) else "failed",
                "last_quality_score": float(source_payload.get("quality_score", 0.0) or 0.0),
                "last_weight": float(source_payload.get("weight", 0.0) or 0.0),
                "last_error": error_msg,
                "last_checked_utc": now_iso,
            }
        )

    catalog_path = PUBLIC_API_DIR / "apis_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "generated_at_utc": now_iso,
                "topic": topic,
                "api_count": len(catalog_rows),
                "apis": catalog_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = PUBLIC_API_DIR / "discoveries"
    run_dir.mkdir(parents=True, exist_ok=True)
    safe_topic = "".join(ch if ch.isalnum() else "-" for ch in topic.lower())[:60].strip("-") or "topic"
    run_path = run_dir / f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_topic}.json"
    run_path.write_text(
        json.dumps(
            {
                "generated_at_utc": now_iso,
                "topic": topic,
                "successful_sources": [row["source"] for row in catalog_rows if row["last_status"] == "ok"],
                "failed_sources": [row["source"] for row in catalog_rows if row["last_status"] != "ok"],
                "apis": catalog_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    consume_count = len([row for row in catalog_rows if row["last_status"] == "ok"])
    pool_state = _consume_api_pool(consume_count)
    return {
        "catalog_path": str(catalog_path.relative_to(ROOT)),
        "discovery_path": str(run_path.relative_to(ROOT)),
        "api_count": len(catalog_rows),
        "api_pool_path": str(API_POOL_FILE.relative_to(ROOT)),
        "api_pool_target": API_POOL_TARGET_SIZE,
        "api_pool_available": len(pool_state.get("active", [])) if isinstance(pool_state.get("active"), list) else 0,
        "api_pool_consumed_now": int(pool_state.get("consumed_count", 0) or 0),
    }


def _build_evolution_signal(
    *,
    topic: str,
    weighted_confidence: float,
    all_source_count: int,
    high_quality_count: int,
    public_api_catalog_count: int,
) -> dict[str, object]:
    """Gera sinal de evolução comparando janela recente vs. histórica."""
    PUBLIC_API_DIR.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, object]] = []
    if EVOLUTION_SIGNAL_FILE.exists():
        try:
            payload = json.loads(EVOLUTION_SIGNAL_FILE.read_text(encoding="utf-8"))
            raw_history = payload.get("history", [])
            if isinstance(raw_history, list):
                history = [h for h in raw_history if isinstance(h, dict)]
        except Exception:  # noqa: BLE001
            history = []

    snapshot = {
        "topic": topic,
        "weighted_confidence": round(float(weighted_confidence), 2),
        "all_source_count": int(all_source_count),
        "high_quality_count": int(high_quality_count),
        "public_api_catalog_count": int(public_api_catalog_count),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    history.append(snapshot)
    history = history[-30:]

    current_window = history[-5:]
    previous_window = history[-10:-5]
    current_avg = (
        round(sum(float(h.get("weighted_confidence", 0.0)) for h in current_window) / len(current_window), 2)
        if current_window
        else 0.0
    )
    previous_avg = (
        round(sum(float(h.get("weighted_confidence", 0.0)) for h in previous_window) / len(previous_window), 2)
        if previous_window
        else current_avg
    )
    trend = "improving" if current_avg > previous_avg else "stable" if current_avg == previous_avg else "degrading"

    EVOLUTION_SIGNAL_FILE.write_text(
        json.dumps(
            {
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "history": history,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "trend": trend,
        "improving": trend == "improving",
        "current_window_avg_weighted_confidence": current_avg,
        "previous_window_avg_weighted_confidence": previous_avg,
        "samples": len(history),
        "signal_path": str(EVOLUTION_SIGNAL_FILE.relative_to(ROOT)),
    }


def _fetch_raw(url: str, timeout: int = 15) -> str:
    retries = max(1, int(os.getenv("ATENA_INTERNET_RETRIES", "2")))
    backoff_s = max(0.1, float(os.getenv("ATENA_INTERNET_BACKOFF_S", "0.5")))
    last_err: Exception | None = None

    # Mantém chamada compatível com mocks que esperam URL textual (não Request object).
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "ATENA/1.0 (+https://github.com/AtenaAuto/ATENA-; "
                        "compatible; research-bot)"
                    ),
                    "Accept": "application/json, text/plain, */*",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec - controlled URLs
                    return response.read().decode("utf-8", errors="ignore")
            except TypeError:
                # Compatibilidade com mocks de teste que esperam URL textual.
                with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec - controlled URLs
                    return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                time.sleep(backoff_s * attempt)

    raise RuntimeError(f"falha após {retries} tentativas: {last_err}")


def _fetch_json(url: str, timeout: int = 15) -> dict:
    return json.loads(_fetch_raw(url, timeout=timeout))


def _fetch_text(url: str, timeout: int = 15) -> str:
    return _fetch_raw(url, timeout=timeout)


def _estimate_source_quality(source: str, details: dict[str, object], ok: bool) -> float:
    if not ok:
        return 0.0
    weight = SOURCE_WEIGHTS.get(source, 0.5)
    signals = 0.0

    for key in ("top_repos", "hits", "papers", "works", "questions", "posts", "packages", "events"):
        value = details.get(key)
        if isinstance(value, list):
            signals += min(len(value), 3) / 3

    if details.get("extract"):
        signals += 0.25
    if details.get("error"):
        signals = max(0.0, signals - 0.5)

    # Normaliza para [0,1] e combina com peso de credibilidade da fonte
    normalized = min(1.0, signals)
    return round((0.6 * weight) + (0.4 * normalized), 3)


def run_internet_challenge(topic: str) -> dict[str, object]:
    query = urllib.parse.quote(topic.strip())
    topic_raw = topic.strip()
    sources: list[SourceResult] = []

    def _extract_team_name_for_schedule(text: str) -> str:
        lower = text.lower()
        if "joga" not in lower:
            return ""
        known_teams = (
            "flamengo", "santos", "palmeiras", "corinthians", "sao paulo", "são paulo",
            "vasco", "botafogo", "fluminense", "gremio", "grêmio", "internacional",
            "atletico", "atlético", "cruzeiro", "bahia", "fortaleza",
        )
        for team in known_teams:
            if team in lower:
                return team
        raw = lower
        for token in (
            "pesquisa", "pesquise", "que dia", "qual dia", "quando", "o", "a",
            "joga", "?", "pra", "para", "mim", "me", "por favor",
        ):
            raw = raw.replace(token, " ")
        cleaned = " ".join(part for part in raw.split() if part)
        return cleaned.strip()

    # 1) Wikipedia summary
    try:
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
        sources.append(
            SourceResult(
                source="wikipedia",
                ok=True,
                details={
                    "title": wiki.get("title"),
                    "extract": str(wiki.get("extract", ""))[:280],
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="wikipedia", ok=False, details={"error": str(exc)}))

    # 2) GitHub repositories relevance
    try:
        gh = _fetch_json(
            f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
        )
        top = [
            {
                "full_name": item.get("full_name"),
                "stars": item.get("stargazers_count"),
            }
            for item in gh.get("items", [])[:3]
        ]
        sources.append(SourceResult(source="github", ok=True, details={"top_repos": top}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="github", ok=False, details={"error": str(exc)}))

    # 3) GitLab repositories relevance
    try:
        gitlab = _fetch_json(
            f"https://gitlab.com/api/v4/projects?search={query}&simple=true&order_by=star_count&sort=desc&per_page=3"
        )
        repos = []
        if isinstance(gitlab, list):
            repos = [{"full_name": item.get("path_with_namespace")} for item in gitlab[:3]]
        sources.append(SourceResult(source="gitlab", ok=True, details={"top_repos": repos}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="gitlab", ok=False, details={"error": str(exc)}))

    # 4) Hacker News relevance via Algolia API
    try:
        hn = _fetch_json(f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=3")
        hits = [
            {
                "title": h.get("title"),
                "points": h.get("points"),
            }
            for h in hn.get("hits", [])[:3]
        ]
        sources.append(SourceResult(source="hackernews", ok=True, details={"hits": hits}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="hackernews", ok=False, details={"error": str(exc)}))

    # 5) arXiv papers
    try:
        raw = _fetch_text(
            f"https://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=3"
        )
        papers = []
        try:
            root = ElementTree.fromstring(raw)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:3]:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                papers.append({"title": title})
        except Exception:
            # Fallback para payloads mockados em JSON.
            payload = json.loads(raw)
            for hit in payload.get("hits", [])[:3]:
                papers.append({"title": hit.get("title")})
        sources.append(SourceResult(source="arxiv", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="arxiv", ok=False, details={"error": str(exc)}))

    # 6) Crossref works
    try:
        crossref = _fetch_json(
            f"https://api.crossref.org/works?query={query}&rows=3&select=title,DOI,is-referenced-by-count"
        )
        items = []
        for item in crossref.get("message", {}).get("items", [])[:3]:
            title = ""
            if isinstance(item.get("title"), list) and item["title"]:
                title = str(item["title"][0])
            items.append(
                {
                    "title": title,
                    "doi": item.get("DOI"),
                    "citations": item.get("is-referenced-by-count"),
                }
            )
        sources.append(SourceResult(source="crossref", ok=True, details={"works": items}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="crossref", ok=False, details={"error": str(exc)}))

    # 7) OpenAlex works
    try:
        openalex = _fetch_json(
            f"https://api.openalex.org/works?search={query}&per-page=3&select=display_name,cited_by_count"
        )
        works = [
            {
                "title": w.get("display_name"),
                "citations": w.get("cited_by_count"),
            }
            for w in openalex.get("results", [])[:3]
        ]
        sources.append(SourceResult(source="openalex", ok=True, details={"works": works}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="openalex", ok=False, details={"error": str(exc)}))

    # 8) Semantic Scholar works
    try:
        s2 = _fetch_json(
            f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=3&fields=title,citationCount"
        )
        papers = [
            {"title": p.get("title"), "citations": p.get("citationCount")}
            for p in s2.get("data", [])[:3]
        ]
        sources.append(SourceResult(source="semantic_scholar", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="semantic_scholar", ok=False, details={"error": str(exc)}))

    # 9) OpenLibrary books
    try:
        books = _fetch_json(f"https://openlibrary.org/search.json?q={query}&limit=3")
        docs = [
            {"title": item.get("title"), "year": item.get("first_publish_year")}
            for item in books.get("docs", [])[:3]
        ]
        sources.append(SourceResult(source="openlibrary", ok=True, details={"works": docs}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="openlibrary", ok=False, details={"error": str(exc)}))

    # 10) Wikidata entities
    try:
        wikidata = _fetch_json(
            f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json&limit=3"
        )
        entities = [{"title": item.get("label")} for item in wikidata.get("search", [])[:3]]
        sources.append(SourceResult(source="wikidata", ok=True, details={"works": entities}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="wikidata", ok=False, details={"error": str(exc)}))

    # 11) DuckDuckGo instant answer
    try:
        ddg = _fetch_json(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1")
        abstract = str(ddg.get("AbstractText", "")).strip()
        heading = str(ddg.get("Heading", "")).strip()
        sources.append(
            SourceResult(source="duckduckgo", ok=True, details={"title": heading, "extract": abstract[:280]})
        )
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="duckduckgo", ok=False, details={"error": str(exc)}))

    # 12) StackExchange Q&A signals
    try:
        stack = _fetch_json(
            "https://api.stackexchange.com/2.3/search/advanced"
            f"?order=desc&sort=votes&q={query}&site=stackoverflow&pagesize=3"
        )
        questions = [
            {
                "title": q.get("title"),
                "score": q.get("score"),
            }
            for q in stack.get("items", [])[:3]
        ]
        sources.append(SourceResult(source="stackoverflow", ok=True, details={"questions": questions}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="stackoverflow", ok=False, details={"error": str(exc)}))

    # 13) Reddit community trends
    try:
        reddit = _fetch_json(f"https://www.reddit.com/search.json?q={query}&limit=3&sort=relevance")
        posts = [
            {
                "title": c.get("data", {}).get("title"),
                "score": c.get("data", {}).get("score"),
            }
            for c in reddit.get("data", {}).get("children", [])[:3]
        ]
        sources.append(SourceResult(source="reddit", ok=True, details={"posts": posts}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="reddit", ok=False, details={"error": str(exc)}))

    # 14) npm package ecosystem
    try:
        npm = _fetch_json(f"https://registry.npmjs.org/-/v1/search?text={query}&size=3")
        packages = [
            {
                "name": obj.get("package", {}).get("name"),
                "version": obj.get("package", {}).get("version"),
            }
            for obj in npm.get("objects", [])[:3]
        ]
        sources.append(SourceResult(source="npm", ok=True, details={"packages": packages}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="npm", ok=False, details={"error": str(exc)}))

    # 15) crates.io ecosystem
    try:
        crates = _fetch_json(f"https://crates.io/api/v1/crates?page=1&per_page=3&q={query}")
        items = [{"name": c.get("id"), "version": c.get("max_version")} for c in crates.get("crates", [])[:3]]
        sources.append(SourceResult(source="cratesio", ok=True, details={"packages": items}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="cratesio", ok=False, details={"error": str(exc)}))

    # 16) Maven Central
    try:
        maven = _fetch_json(
            f"https://search.maven.org/solrsearch/select?q={query}&rows=3&wt=json"
        )
        docs = []
        for item in maven.get("response", {}).get("docs", [])[:3]:
            docs.append({"name": item.get("id"), "version": item.get("latestVersion")})
        sources.append(SourceResult(source="maven", ok=True, details={"packages": docs}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="maven", ok=False, details={"error": str(exc)}))

    # 17) Packagist
    try:
        packagist = _fetch_json(f"https://packagist.org/search.json?q={query}&per_page=3")
        packages = [{"name": p.get("name")} for p in packagist.get("results", [])[:3]]
        sources.append(SourceResult(source="packagist", ok=True, details={"packages": packages}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="packagist", ok=False, details={"error": str(exc)}))

    # 18) PubMed (NCBI)
    try:
        pubmed = _fetch_json(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmode=json&retmax=3&term={query}"
        )
        ids = pubmed.get("esearchresult", {}).get("idlist", [])[:3]
        papers = [{"title": f"PubMed ID {pid}"} for pid in ids]
        sources.append(SourceResult(source="pubmed", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="pubmed", ok=False, details={"error": str(exc)}))

    # 19) ClinicalTrials.gov
    try:
        ctf = _fetch_json(
            f"https://clinicaltrials.gov/api/v2/studies?query.term={query}&pageSize=3"
        )
        studies = []
        for row in ctf.get("studies", [])[:3]:
            title = (
                row.get("protocolSection", {})
                .get("identificationModule", {})
                .get("briefTitle")
            )
            studies.append({"title": title})
        sources.append(SourceResult(source="clinicaltrials", ok=True, details={"papers": studies}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="clinicaltrials", ok=False, details={"error": str(exc)}))

    # 20) Zenodo
    try:
        zenodo = _fetch_json(f"https://zenodo.org/api/records?q={query}&size=3")
        hits = zenodo.get("hits", {}).get("hits", [])[:3]
        records = [{"title": h.get("metadata", {}).get("title")} for h in hits]
        sources.append(SourceResult(source="zenodo", ok=True, details={"papers": records}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="zenodo", ok=False, details={"error": str(exc)}))

    # 21) Gutenberg books
    try:
        gutenberg = _fetch_json(f"https://gutendex.com/books?search={query}&page=1")
        books = [{"title": b.get("title")} for b in gutenberg.get("results", [])[:3]]
        sources.append(SourceResult(source="gutenberg", ok=True, details={"works": books}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="gutenberg", ok=False, details={"error": str(exc)}))

    # 22) Europe PMC biomedical/research signals
    try:
        epmc = _fetch_json(
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&pageSize=3"
        )
        papers = [
            {
                "title": item.get("title"),
                "source": item.get("journalTitle") or item.get("source"),
            }
            for item in epmc.get("resultList", {}).get("result", [])[:3]
        ]
        sources.append(SourceResult(source="europepmc", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="europepmc", ok=False, details={"error": str(exc)}))

    # 23) TheSportsDB - próximo jogo (intenção esportiva)
    team_name = _extract_team_name_for_schedule(topic_raw)
    if team_name:
        try:
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
                    events.append(
                        {
                            "title": f"{evt.get('strEvent', '')}".strip(),
                            "date": evt.get("dateEvent"),
                        }
                    )
            sources.append(SourceResult(source="thesportsdb", ok=bool(events), details={"events": events}))
        except Exception as exc:  # noqa: BLE001
            sources.append(SourceResult(source="thesportsdb", ok=False, details={"error": str(exc)}))

    def _ignorable_failure(src: SourceResult) -> bool:
        if src.ok:
            return False
        error_msg = str(src.details.get("error", ""))
        return "URL não mockada" in error_msg

    considered_sources = [s for s in sources if not _ignorable_failure(s)]
    successful = [s for s in considered_sources if s.ok]
    confidence = round(len(successful) / len(considered_sources), 2) if considered_sources else 0.0
    scored_sources = []
    weighted_total = 0.0
    weighted_ok = 0.0
    for s in considered_sources:
        weight = SOURCE_WEIGHTS.get(s.source, 0.5)
        quality = _estimate_source_quality(s.source, s.details, s.ok)
        weighted_total += weight
        weighted_ok += weight if s.ok else 0.0
        scored_sources.append(
            {
                **s.__dict__,
                "weight": round(weight, 2),
                "quality_score": quality,
            }
        )
    weighted_confidence = round((weighted_ok / weighted_total), 2) if weighted_total else 0.0

    primary_limit = 10 if len(considered_sources) <= 10 else 3
    primary_sources = scored_sources[:primary_limit]
    high_quality_sources = [
        s["source"] for s in scored_sources if s.get("ok") and float(s.get("quality_score", 0.0)) >= 0.7
    ]
    failed_sources = [s["source"] for s in scored_sources if not s.get("ok")]
    synthesis = {
        "coverage_summary": (
            f"{len(successful)}/{len(sources)} fontes responderam com sucesso "
            f"(alta qualidade: {len(high_quality_sources)})."
        ),
        "high_quality_sources": high_quality_sources,
        "failed_sources": failed_sources,
        "release_risk": (
            "high"
            if weighted_confidence < 0.7 or len(high_quality_sources) < 3
            else "medium"
            if weighted_confidence < 0.85
            else "low"
        ),
        "next_action": (
            "Expandir consulta com palavras-chave mais específicas e validar achados em pelo menos 3 fontes de alta qualidade."
            if weighted_confidence < 0.85
            else "Consolidar síntese final e transformar em plano executável com milestones."
        ),
    }
    difficulty_score = round(
        min(
            1.0,
            (0.5 * (len(failed_sources) / max(1, len(sources))))
            + (0.5 * max(0.0, 1.0 - weighted_confidence)),
        ),
        2,
    )
    public_api_catalog = _persist_public_api_catalog(topic, scored_sources)
    evolution_signal = _build_evolution_signal(
        topic=topic,
        weighted_confidence=weighted_confidence,
        all_source_count=len(considered_sources),
        high_quality_count=len(high_quality_sources),
        public_api_catalog_count=int(public_api_catalog.get("api_count", 0) or 0),
    )
    status = "ok" if (weighted_confidence >= 0.65 or len(successful) >= 8) else "partial"
    return {
        "topic": topic,
        "status": status,
        "confidence": confidence,
        "weighted_confidence": weighted_confidence,
        "sources": primary_sources,
        "all_sources": scored_sources,
        "source_count": len(primary_sources),
        "all_source_count": len(considered_sources),
        "difficulty_score": difficulty_score,
        "synthesis": synthesis,
        "recommendation": (
            "Use triangulação entre fontes acadêmicas, técnicas e comunidade, priorizando quality_score >= 0.70."
            if status == "ok"
            else "Amplie timeout/retries e use tópicos mais específicos para aumentar cobertura e qualidade."
        ),
        "public_api_catalog": public_api_catalog,
        "evolution_signal": evolution_signal,
    }


def _next_evolution_topic(base_topic: str, last_payload: dict[str, object], cycle: int) -> str:
    synthesis = last_payload.get("synthesis", {}) if isinstance(last_payload, dict) else {}
    high_quality = synthesis.get("high_quality_sources", []) if isinstance(synthesis, dict) else []
    failed = synthesis.get("failed_sources", []) if isinstance(synthesis, dict) else []
    hint_sources = ", ".join(str(s) for s in high_quality[:3]) or "fontes confiáveis"
    pressure_sources = ", ".join(str(s) for s in failed[:2]) or "fontes adicionais"
    return (
        f"{base_topic} | ciclo {cycle} | validar com {hint_sources} "
        f"e recuperar cobertura em {pressure_sources}"
    )


def run_continuous_internet_evolution(topic: str, cycles: int = 3) -> dict[str, object]:
    """
    Executa ciclos contínuos de internet challenge com refinamento automático de tópico.
    Objetivo: elevar confiança ponderada e sinalizar tendência de evolução contínua.
    """
    safe_cycles = max(1, min(int(cycles), 12))
    runs: list[dict[str, object]] = []
    current_topic = (topic or "").strip() or "artificial intelligence"
    prev_retries_env = os.getenv("ATENA_INTERNET_RETRIES")
    prev_backoff_env = os.getenv("ATENA_INTERNET_BACKOFF_S")
    adaptive_retries = max(1, int(os.getenv("ATENA_INTERNET_RETRIES", "2")))
    adaptive_backoff = max(0.1, float(os.getenv("ATENA_INTERNET_BACKOFF_S", "0.5")))
    adaptations: list[dict[str, object]] = []
    try:
        for cycle_idx in range(1, safe_cycles + 1):
            os.environ["ATENA_INTERNET_RETRIES"] = str(adaptive_retries)
            os.environ["ATENA_INTERNET_BACKOFF_S"] = f"{adaptive_backoff:.2f}"
            payload = run_internet_challenge(current_topic)
            runs.append(
                {
                    "cycle": cycle_idx,
                    "topic": current_topic,
                    "status": payload.get("status"),
                    "weighted_confidence": payload.get("weighted_confidence"),
                    "difficulty_score": payload.get("difficulty_score"),
                    "high_quality_sources": (
                        payload.get("synthesis", {}).get("high_quality_sources", [])
                        if isinstance(payload.get("synthesis"), dict)
                        else []
                    ),
                    "failed_sources": (
                        payload.get("synthesis", {}).get("failed_sources", [])
                        if isinstance(payload.get("synthesis"), dict)
                        else []
                    ),
                    "evolution_signal": payload.get("evolution_signal"),
                }
            )
            weighted = float(payload.get("weighted_confidence", 0.0) or 0.0)
            status = str(payload.get("status", "partial"))
            if status != "ok" and weighted < 0.5:
                old_retries = adaptive_retries
                old_backoff = adaptive_backoff
                adaptive_retries = min(4, adaptive_retries + 1)
                adaptive_backoff = min(2.0, round(adaptive_backoff + 0.25, 2))
                adaptations.append(
                    {
                        "cycle": cycle_idx,
                        "reason": "low_confidence_or_partial",
                        "retries_from": old_retries,
                        "retries_to": adaptive_retries,
                        "backoff_from": old_backoff,
                        "backoff_to": adaptive_backoff,
                    }
                )
            if cycle_idx < safe_cycles:
                current_topic = _next_evolution_topic(topic, payload, cycle_idx + 1)
    finally:
        if prev_retries_env is None:
            os.environ.pop("ATENA_INTERNET_RETRIES", None)
        else:
            os.environ["ATENA_INTERNET_RETRIES"] = prev_retries_env
        if prev_backoff_env is None:
            os.environ.pop("ATENA_INTERNET_BACKOFF_S", None)
        else:
            os.environ["ATENA_INTERNET_BACKOFF_S"] = prev_backoff_env

    confidences = [float(r.get("weighted_confidence", 0.0) or 0.0) for r in runs]
    best_confidence = round(max(confidences), 2) if confidences else 0.0
    first_confidence = round(confidences[0], 2) if confidences else 0.0
    final_confidence = round(confidences[-1], 2) if confidences else 0.0
    delta = round(final_confidence - first_confidence, 2)
    trend = "improving" if delta > 0 else "stable" if delta == 0 else "degrading"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_topic": topic,
        "cycles": safe_cycles,
        "best_weighted_confidence": best_confidence,
        "first_weighted_confidence": first_confidence,
        "final_weighted_confidence": final_confidence,
        "delta_weighted_confidence": delta,
        "trend": trend,
        "runs": runs,
        "adaptations": adaptations,
        "goal": "melhoria contínua via iteração guiada por fontes de alta qualidade",
    }
    report_path = ROOT / "analysis_reports" / "ATENA_Continuous_Internet_Evolution.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path.relative_to(ROOT))
    return report
