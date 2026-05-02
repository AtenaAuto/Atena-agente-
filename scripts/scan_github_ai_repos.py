#!/usr/bin/env python3
"""Escaneia GitHub por repositórios de IA com muitas estrelas e gera snapshot local."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

API_URL = "https://api.github.com/search/repositories"
DEFAULT_QUERIES = [
    "topic:artificial-intelligence stars:>5000 archived:false",
    "topic:machine-learning stars:>5000 archived:false",
    '"llm" stars:>3000 archived:false',
]


@dataclass
class RepoSnapshot:
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    language: str | None
    updated_at: str


def _github_request(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "atena-ai-repo-scanner",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_repos(query: str, per_page: int = 20) -> List[RepoSnapshot]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": str(per_page),
            "page": "1",
        }
    )
    payload = _github_request(f"{API_URL}?{params}")
    items = payload.get("items", [])
    return [
        RepoSnapshot(
            full_name=item.get("full_name", ""),
            html_url=item.get("html_url", ""),
            description=(item.get("description") or "").strip(),
            stargazers_count=int(item.get("stargazers_count", 0)),
            language=item.get("language"),
            updated_at=item.get("updated_at", ""),
        )
        for item in items
    ]


def dedupe_rank(repos: List[RepoSnapshot], top_n: int = 50) -> List[RepoSnapshot]:
    by_name: dict[str, RepoSnapshot] = {}
    for repo in repos:
        prev = by_name.get(repo.full_name)
        if not prev or repo.stargazers_count > prev.stargazers_count:
            by_name[repo.full_name] = repo
    return sorted(by_name.values(), key=lambda r: r.stargazers_count, reverse=True)[:top_n]


def main() -> int:
    collected: List[RepoSnapshot] = []
    for q in DEFAULT_QUERIES:
        try:
            collected.extend(search_repos(q))
            time.sleep(0.4)
        except Exception as exc:
            print(f"[WARN] Falha na query '{q}': {exc}")

    if not collected:
        print("[ERROR] Nenhum repositório coletado do GitHub.")
        return 1

    top = dedupe_rank(collected, top_n=50)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "GitHub Search API",
        "queries": DEFAULT_QUERIES,
        "count": len(top),
        "repos": [asdict(repo) for repo in top],
    }

    out_path = Path("docs/ai_repo_watchlist.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Watchlist gerada em: {out_path} ({len(top)} repositórios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
