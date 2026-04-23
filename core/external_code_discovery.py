#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def search_repositories(query: str, max_repos: int) -> list[dict[str, object]]:
    q = f"{query} language:python"
    params = urllib.parse.urlencode(
        {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": max(1, min(max_repos, 25)),
        }
    )
    url = f"https://api.github.com/search/repositories?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ATENA-external-code-discovery",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    items = payload.get("items", [])
    repos: list[dict[str, object]] = []
    for item in items:
        repos.append(
            {
                "name": item.get("full_name"),
                "url": item.get("html_url"),
                "description": item.get("description") or "",
                "stars": item.get("stargazers_count", 0),
                "updated_at": item.get("updated_at"),
                "clone_url": item.get("clone_url"),
                "language": item.get("language"),
            }
        )
    return repos


def write_reports(query: str, repos: list[dict[str, object]]) -> tuple[Path, Path]:
    reports_dir = ROOT / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    json_path = reports_dir / f"EXTERNAL_CODE_DISCOVERY_{ts}.json"
    md_path = reports_dir / f"EXTERNAL_CODE_DISCOVERY_{ts}.md"

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": query,
        "count": len(repos),
        "repos": repos,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# External Code Discovery",
        "",
        f"- Query: `{query}`",
        f"- Count: `{len(repos)}`",
        "",
        "## Top repositories",
    ]
    for idx, repo in enumerate(repos, start=1):
        lines.append(
            f"{idx}. **{repo.get('name')}** — ⭐ {repo.get('stars')}  \n"
            f"   URL: {repo.get('url')}  \n"
            f"   Language: {repo.get('language')}  \n"
            f"   Updated: {repo.get('updated_at')}  \n"
            f"   Desc: {repo.get('description')}"
        )
    lines.append("")
    lines.append(f"JSON artifact: `{json_path.relative_to(ROOT)}`")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca repositórios externos no GitHub para inspiração de código.")
    parser.add_argument("--query", default="autonomous ai agents", help="Tema de busca")
    parser.add_argument("--max-repos", type=int, default=8, help="Quantidade máxima de repositórios")
    args = parser.parse_args()

    repos = search_repositories(args.query, args.max_repos)
    json_path, md_path = write_reports(args.query, repos)
    print(f"External code discovery OK | repos={len(repos)}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
