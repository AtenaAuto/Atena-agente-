#!/usr/bin/env python3
"""Varredura GitHub para alimentar a evolução da ATENA.

O objetivo é permitir que um operador diga "vasculhe o GitHub em busca de
informações para sua evolução" e receba um artefato local com repositórios,
padrões técnicos e próximas ações sugeridas.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "atena_evolution" / "github_evolution_scans"
ABSORPTION_DOC = ROOT / "docs" / "ATENA_GITHUB_EVOLUTION_ABSORBED.md"
CLONE_DIR = ROOT / "atena_evolution" / "github_evolution_clones"
INCORPORATED_CORE_DIR = ROOT / "core" / "atena_incorporated_github"
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
DEFAULT_QUERIES = [
    "autonomous ai agent framework stars:>500 archived:false",
    "llm agent orchestration stars:>500 archived:false",
    "self improving ai agents stars:>100 archived:false",
    "ai coding agent benchmark stars:>100 archived:false",
]


THEME_KEYWORDS = {
    "orquestração de agentes": ("agent", "orchestration", "workflow", "multi-agent", "crew"),
    "memória/RAG": ("rag", "memory", "retrieval", "stateful"),
    "benchmarks/evals": ("benchmark", "eval", "evaluation", "leaderboard"),
    "automação/coding agents": ("coding", "code", "developer", "automation"),
    "segurança/guardrails": ("security", "sandbox", "guardrail", "policy"),
}


@dataclass(frozen=True)
class GitHubRepoInsight:
    """Resumo de um repositório encontrado no GitHub."""

    full_name: str
    html_url: str
    description: str
    stars: int
    forks: int
    language: str | None
    topics: list[str]
    license_spdx: str | None
    updated_at: str
    score: float


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ATENA-github-evolution-scan",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_github_headers())
    try:
        ctx = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - GitHub API URL controlada
    except TypeError:
        # Compatibilidade com mocks de testes que esperam string.
        ctx = urllib.request.urlopen(url, timeout=timeout)  # noqa: S310
    with ctx as response:
        return json.loads(response.read().decode("utf-8"))


def search_github_repositories(query: str, *, limit: int = 10, timeout: int = 30) -> list[GitHubRepoInsight]:
    """Busca repositórios no GitHub e retorna insights rankeáveis."""
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": str(max(1, min(limit, 30))),
            "page": "1",
        }
    )
    payload = _fetch_json(f"{GITHUB_SEARCH_URL}?{params}", timeout=timeout)
    repos: list[GitHubRepoInsight] = []
    for item in payload.get("items", []):
        stars = int(item.get("stargazers_count") or 0)
        forks = int(item.get("forks_count") or 0)
        topics = [str(t) for t in item.get("topics", []) if t]
        license_info = item.get("license") if isinstance(item.get("license"), dict) else {}
        recency_bonus = 1.0 if str(item.get("updated_at", ""))[:4] >= "2025" else 0.0
        topic_bonus = min(len(topics), 8) * 0.15
        score = round(stars * 0.001 + forks * 0.0005 + topic_bonus + recency_bonus, 4)
        repos.append(
            GitHubRepoInsight(
                full_name=str(item.get("full_name") or ""),
                html_url=str(item.get("html_url") or ""),
                description=str(item.get("description") or "").strip(),
                stars=stars,
                forks=forks,
                language=item.get("language"),
                topics=topics,
                license_spdx=str(license_info.get("spdx_id") or "") or None,
                updated_at=str(item.get("updated_at") or ""),
                score=score,
            )
        )
    return repos


def dedupe_rank_repositories(repos: Sequence[GitHubRepoInsight], *, top_n: int = 25) -> list[GitHubRepoInsight]:
    """Remove duplicatas e ordena por score/estrelas."""
    by_name: dict[str, GitHubRepoInsight] = {}
    for repo in repos:
        if not repo.full_name:
            continue
        previous = by_name.get(repo.full_name)
        if previous is None or repo.score > previous.score:
            by_name[repo.full_name] = repo
    return sorted(by_name.values(), key=lambda r: (r.score, r.stars), reverse=True)[:top_n]


def classify_interesting_themes(repo: GitHubRepoInsight) -> list[str]:
    """Classifica por que um repositório é interessante para a evolução."""
    text = " ".join([repo.full_name, repo.description, " ".join(repo.topics)]).lower()
    themes = [label for label, tokens in THEME_KEYWORDS.items() if any(token in text for token in tokens)]
    if repo.stars >= 10_000:
        themes.append("alta adoção")
    if str(repo.updated_at)[:4] >= "2025":
        themes.append("ativo/recente")
    return themes or ["referência técnica"]


def build_findings_summary(repos: Sequence[GitHubRepoInsight]) -> dict[str, Any]:
    """Resume o que foi encontrado e se os achados parecem interessantes."""
    language_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}
    interesting_findings: list[dict[str, Any]] = []

    for repo in repos[:10]:
        language = repo.language or "unknown"
        language_counts[language] = language_counts.get(language, 0) + 1
        themes = classify_interesting_themes(repo)
        for theme in themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
        interesting_findings.append(
            {
                "repo": repo.full_name,
                "why_interesting": themes[:4],
                "stars": repo.stars,
                "url": repo.html_url,
            }
        )

    top_score = repos[0].score if repos else 0.0
    interesting_score = round(min(100.0, top_score), 2)
    if not repos:
        verdict = "Não encontrou achados suficientes nesta execução."
    elif interesting_score >= 20 or len(repos) >= 3:
        verdict = "Sim, encontrou sinais interessantes para investigar; ainda precisam de validação antes de virar evolução."
    else:
        verdict = "Encontrou poucos sinais; pode ser necessário refinar a busca."

    return {
        "answer_what_she_found": [item["repo"] for item in interesting_findings[:5]],
        "interesting_findings": interesting_findings,
        "theme_counts": dict(sorted(theme_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "language_counts": dict(sorted(language_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "interesting_score": interesting_score,
        "verdict": verdict,
        "does_she_always_find_interesting_things": False,
        "caveat": "Não sempre: a qualidade depende dos termos de busca, rate limit/API do GitHub, recência dos projetos e validação local com testes.",
    }


def summarize_evolution_actions(repos: Sequence[GitHubRepoInsight], objective: str) -> list[str]:
    """Gera ações práticas para evolução da ATENA a partir dos repositórios."""
    text = " ".join(
        [objective]
        + [repo.description for repo in repos]
        + [" ".join(repo.topics) for repo in repos]
    ).lower()
    actions = [
        "Comparar arquitetura dos top repositórios com módulos internos da ATENA antes de copiar qualquer padrão.",
        "Registrar hipóteses de evolução em atena_evolution e validar cada uma com self-test rápido.",
    ]
    if any(token in text for token in ("benchmark", "eval", "evaluation")):
        actions.append("Criar benchmark local para medir melhoria antes/depois da evolução inspirada no GitHub.")
    if any(token in text for token in ("rag", "memory", "retrieval")):
        actions.append("Avaliar padrões de memória/RAG encontrados e mapear impacto em enterprise_memory_rag.")
    if any(token in text for token in ("agent", "orchestration", "multi-agent", "workflow")):
        actions.append("Extrair padrões de orquestração multiagente e testar com uma missão pequena no terminal.")
    if any(token in text for token in ("security", "sandbox", "guardrail")):
        actions.append("Revisar guardrails/sandbox antes de habilitar qualquer automação inspirada nos achados.")
    return actions


def write_github_evolution_reports(payload: dict[str, Any], *, output_dir: Path | str = REPORT_DIR) -> tuple[Path, Path]:
    """Salva relatório JSON e Markdown da varredura GitHub."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"github_evolution_scan_{ts}.json"
    md_path = out_dir / f"github_evolution_scan_{ts}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# ATENA GitHub Evolution Scan",
        "",
        f"- Objetivo: `{payload.get('objective')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Repositórios: `{payload.get('repo_count')}`",
        "",
        "## O que a ATENA achou?",
        f"- Veredito: {payload.get('findings_summary', {}).get('verdict', 'n/a')}",
        f"- Score de interesse: `{payload.get('findings_summary', {}).get('interesting_score', 0)}`",
        f"- Ela sempre acha coisas interessantes? `{payload.get('findings_summary', {}).get('does_she_always_find_interesting_things', False)}`",
        f"- Observação: {payload.get('findings_summary', {}).get('caveat', '')}",
        "",
        "### Achados interessantes",
    ]
    for finding in payload.get('findings_summary', {}).get('interesting_findings', [])[:8]:
        lines.append(
            f"- **{finding.get('repo')}** — {', '.join(finding.get('why_interesting', []))} — ⭐ {finding.get('stars')}"
        )
    lines.extend([
        "",
        "## Próximas ações",
    ])
    for action in payload.get("evolution_actions", []):
        lines.append(f"- {action}")
    if payload.get("incorporated"):
        incorporation = payload.get("incorporation_result", {})
        lines.extend(
            [
                "",
                "## Incorporação automática no core",
                f"- Diretório: `{incorporation.get('core_dir')}`",
                f"- Repositórios incorporados: `{incorporation.get('ok', 0)}/{incorporation.get('requested', 0)}`",
                f"- Manifesto: `{incorporation.get('manifest_path', '')}`",
            ]
        )
    lines.extend(["", "## Top repositórios"])
    for idx, repo in enumerate(payload.get("repositories", [])[:15], start=1):
        lines.append(
            f"{idx}. **{repo.get('full_name')}** — ⭐ {repo.get('stars')} — score={repo.get('score')}  \n"
            f"   {repo.get('html_url')}  \n"
            f"   {repo.get('description')}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _safe_repo_dir_name(full_name: str) -> str:
    """Converte owner/repo em nome seguro para diretório local."""
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "__" for ch in full_name).strip("_") or "repo"


def clone_best_repositories(
    repositories: Sequence[dict[str, Any]],
    *,
    clone_dir: Path | str = CLONE_DIR,
    limit: int | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Clona de forma rasa os melhores repositórios públicos encontrados.

    Os clones ficam em atena_evolution (runtime/cache). Use --incorporate
    quando quiser copiar snapshots filtrados para dentro de core/.
    """
    out_dir = Path(clone_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = list(repositories[: limit or len(repositories)])
    results: list[dict[str, Any]] = []

    for repo in selected:
        full_name = str(repo.get("full_name") or "").strip()
        html_url = str(repo.get("html_url") or "").strip()
        if not full_name or not html_url.startswith("https://github.com/"):
            results.append({"repo": full_name or html_url, "status": "skipped", "reason": "not_public_github_url"})
            continue

        target = out_dir / _safe_repo_dir_name(full_name)
        clone_url = f"{html_url}.git"
        if (target / ".git").exists():
            results.append({"repo": full_name, "status": "exists", "path": str(target), "url": html_url})
            continue

        command = ["git", "clone", "--depth", "1", "--filter=blob:none", clone_url, str(target)]
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
            results.append(
                {
                    "repo": full_name,
                    "status": "ok" if completed.returncode == 0 else "failed",
                    "path": str(target),
                    "url": html_url,
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": (completed.stdout or "")[-2000:],
                    "stderr_tail": (completed.stderr or "")[-2000:],
                }
            )
        except Exception as exc:  # pragma: no cover - ambiente git/rede pode falhar
            results.append({"repo": full_name, "status": "failed", "path": str(target), "url": html_url, "error": str(exc)})

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "clone_dir": str(out_dir),
        "requested": len(selected),
        "ok": sum(1 for item in results if item.get("status") in {"ok", "exists"}),
        "results": results,
        "note": "Clones rasos para inspeção local; use incorporate para copiar snapshots filtrados para core/.",
    }
    manifest_path = out_dir / "latest_clone_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


_ALLOWED_CORE_EXTENSIONS = {
    ".py", ".pyi", ".md", ".rst", ".txt", ".toml", ".yaml", ".yml", ".json",
    ".ini", ".cfg", ".sh", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
}
_ALWAYS_KEEP_NAMES = {"license", "license.md", "license.txt", "copying", "notice", "readme.md", "readme"}
_SKIP_DIRS = {
    ".git", ".github", "node_modules", "dist", "build", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next", "target", "vendor",
}


def _is_incorporable_file(path: Path, *, max_file_bytes: int) -> bool:
    """Decide se um arquivo clonado pode virar snapshot versionável no core."""
    if path.is_symlink() or not path.is_file():
        return False
    name = path.name.lower()
    if name in _ALWAYS_KEEP_NAMES:
        return True
    if path.suffix.lower() not in _ALLOWED_CORE_EXTENSIONS:
        return False
    try:
        return path.stat().st_size <= max_file_bytes
    except OSError:
        return False


def incorporate_cloned_repositories_into_core(
    clone_manifest: dict[str, Any],
    repositories: Sequence[dict[str, Any]],
    *,
    core_dir: Path | str = INCORPORATED_CORE_DIR,
    limit: int | None = 3,
    max_files_per_repo: int = 80,
    max_file_bytes: int = 256_000,
) -> dict[str, Any]:
    """Copia snapshots filtrados dos clones para dentro de ``core/``.

    Esta é a opção explícita de incorporação automática pedida pelo operador:
    os melhores repositórios já clonados viram código-fonte versionável em
    ``core/atena_incorporated_github``. A cópia é intencionalmente filtrada para
    evitar diretórios de build, dependências vendorizadas, binários e arquivos
    grandes. O manifesto preserva origem, licença informada pelo GitHub e limites
    aplicados para auditoria posterior.
    """
    out_dir = Path(core_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").write_text(
        '"""Snapshots de repositórios GitHub incorporados automaticamente pela ATENA."""\n',
        encoding="utf-8",
    )

    repo_by_name = {str(repo.get("full_name") or ""): repo for repo in repositories}
    clone_results = clone_manifest.get("results", []) if isinstance(clone_manifest.get("results"), list) else []
    eligible = [item for item in clone_results if item.get("status") in {"ok", "exists"} and item.get("path")]
    selected = eligible[: limit or len(eligible)]
    incorporated: list[dict[str, Any]] = []

    for item in selected:
        full_name = str(item.get("repo") or "").strip()
        source_path = Path(str(item.get("path") or ""))
        repo_meta = repo_by_name.get(full_name, {})
        target = out_dir / _safe_repo_dir_name(full_name)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

        copied_files: list[str] = []
        skipped_files = 0
        if source_path.exists():
            for path in source_path.rglob("*"):
                if len(copied_files) >= max_files_per_repo:
                    skipped_files += 1
                    continue
                rel = path.relative_to(source_path)
                if any(part in _SKIP_DIRS for part in rel.parts):
                    continue
                if path.is_dir():
                    continue
                if not _is_incorporable_file(path, max_file_bytes=max_file_bytes):
                    skipped_files += 1
                    continue
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                copied_files.append(str(rel))
        else:
            skipped_files += 1

        repo_manifest = {
            "repo": full_name,
            "source_url": item.get("url") or repo_meta.get("html_url"),
            "source_clone_path": str(source_path),
            "core_path": str(target),
            "license_spdx": repo_meta.get("license_spdx"),
            "stars": repo_meta.get("stars"),
            "score": repo_meta.get("score"),
            "copied_files": copied_files,
            "copied_file_count": len(copied_files),
            "skipped_file_count": skipped_files,
        }
        (target / "ATENA_INCORPORATION.json").write_text(
            json.dumps(repo_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        incorporated.append(repo_manifest)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "core_dir": str(out_dir),
        "requested": len(selected),
        "ok": sum(1 for repo in incorporated if repo.get("copied_file_count", 0) > 0),
        "repositories": incorporated,
        "policy": {
            "mode": "automatic_core_snapshot",
            "max_files_per_repo": max_files_per_repo,
            "max_file_bytes": max_file_bytes,
            "excluded_dirs": sorted(_SKIP_DIRS),
            "allowed_extensions": sorted(_ALLOWED_CORE_EXTENSIONS),
        },
        "note": "Código incorporado automaticamente como snapshot filtrado em core/ para uso/auditoria da ATENA.",
    }
    manifest_path = out_dir / "latest_incorporation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest

def absorb_scan_findings_into_repo(
    payload: dict[str, Any],
    *,
    output_path: Path | str = ABSORPTION_DOC,
) -> Path:
    """Absorve achados do GitHub como backlog rastreável no repositório.

    Esta etapa registra referências e hipóteses. A cópia automática de código
    para core/ é feita pela opção explícita --incorporate, com manifesto.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload.get("findings_summary", {}) if isinstance(payload.get("findings_summary"), dict) else {}
    repositories = payload.get("repositories", []) if isinstance(payload.get("repositories"), list) else []
    actions = payload.get("evolution_actions", []) if isinstance(payload.get("evolution_actions"), list) else []

    lines = [
        "# ATENA — GitHub Evolution Absorption",
        "",
        "Este arquivo é a absorção **segura e rastreável** dos achados do GitHub.",
        "Por padrão, registra referências, padrões e hipóteses; com `--incorporate`, a ATENA copia snapshots filtrados para `core/atena_incorporated_github/`.",
        "",
        f"- Gerado em: `{payload.get('generated_at_utc', '')}`",
        f"- Objetivo: `{payload.get('objective', '')}`",
        f"- Fonte: `{payload.get('source', 'GitHub Search API')}`",
        f"- Repositórios absorvidos como referência: `{len(repositories)}`",
        f"- Veredito: {summary.get('verdict', 'n/a')}",
        f"- Ela sempre acha coisas interessantes? `{summary.get('does_she_always_find_interesting_things', False)}`",
        "",
        "## Regras de absorção",
        "- Copiar código externo somente via `--incorporate`, com manifesto e origem preservada.",
        "- Verificar licença antes de executar/adaptar qualquer snapshot incorporado.",
        "- Transformar achados em hipóteses pequenas e testáveis.",
        "- Rodar self-test/benchmark antes de qualquer mudança em runtime.",
        "",
        "## Referências absorvidas",
    ]
    for idx, repo in enumerate(repositories[:20], start=1):
        topics = ", ".join(repo.get("topics", [])[:8]) if isinstance(repo.get("topics"), list) else ""
        lines.extend(
            [
                f"### {idx}. {repo.get('full_name', 'repo desconhecido')}",
                f"- URL: {repo.get('html_url', '')}",
                f"- Linguagem: `{repo.get('language', 'unknown')}`",
                f"- Estrelas: `{repo.get('stars', 0)}`",
                f"- Score ATENA: `{repo.get('score', 0)}`",
                f"- Tópicos: {topics or 'n/a'}",
                f"- Por que observar: {repo.get('description', '')}",
                "- Hipótese ATENA: comparar o padrão com módulos internos e criar teste pequeno antes de implementar.",
                "",
            ]
        )

    lines.extend(["## Ações de evolução derivadas"])
    for action in actions:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Checklist antes de virar código",
            "- [ ] Confirmar licença e compatibilidade.",
            "- [ ] Escrever teste que prove o ganho esperado.",
            "- [ ] Se usar `--incorporate`, revisar `ATENA_INCORPORATION.json` e limitar a adaptação ao necessário.",
            "- [ ] Rodar `pytest -q` no escopo afetado.",
            "- [ ] Registrar resultado em relatório de evolução.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_github_evolution_scan(
    objective: str = "evolução de agentes autônomos",
    *,
    queries: Sequence[str] | None = None,
    limit_per_query: int = 8,
    top_n: int = 20,
    output_dir: Path | str = REPORT_DIR,
    timeout: int = 30,
    absorb: bool = False,
    absorption_path: Path | str = ABSORPTION_DOC,
    clone: bool = False,
    clone_dir: Path | str = CLONE_DIR,
    clone_limit: int | None = None,
    incorporate: bool = False,
    incorporate_dir: Path | str = INCORPORATED_CORE_DIR,
    incorporate_limit: int | None = 3,
) -> dict[str, Any]:
    """Vasculha o GitHub e produz um relatório para evolução da ATENA."""
    scan_queries = list(queries or DEFAULT_QUERIES)
    if objective:
        scan_queries.insert(0, f"{objective} stars:>50 archived:false")

    collected: list[GitHubRepoInsight] = []
    errors: list[str] = []
    for query in scan_queries:
        try:
            collected.extend(search_github_repositories(query, limit=limit_per_query, timeout=timeout))
        except Exception as exc:  # pragma: no cover - rede externa pode falhar
            errors.append(f"{query}: {exc}")

    ranked = dedupe_rank_repositories(collected, top_n=top_n)
    actions = summarize_evolution_actions(ranked, objective)
    findings_summary = build_findings_summary(ranked)
    payload: dict[str, Any] = {
        "status": "ok" if ranked else "warn",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "GitHub Search API",
        "objective": objective,
        "queries": scan_queries,
        "repo_count": len(ranked),
        "repositories": [asdict(repo) for repo in ranked],
        "findings_summary": findings_summary,
        "evolution_actions": actions,
        "errors": errors,
    }
    if clone or incorporate:
        clone_result = clone_best_repositories(payload["repositories"], clone_dir=clone_dir, limit=clone_limit)
        payload["cloned"] = True
        payload["clone_result"] = clone_result
    else:
        clone_result = {}
        payload["cloned"] = False

    if incorporate:
        incorporation_result = incorporate_cloned_repositories_into_core(
            clone_result,
            payload["repositories"],
            core_dir=incorporate_dir,
            limit=incorporate_limit,
        )
        payload["incorporated"] = True
        payload["incorporation_result"] = incorporation_result
    else:
        payload["incorporated"] = False

    if absorb:
        absorbed_path = absorb_scan_findings_into_repo(payload, output_path=absorption_path)
        payload["absorbed"] = True
        payload["absorbed_path"] = str(absorbed_path)
    else:
        payload["absorbed"] = False

    json_path, md_path = write_github_evolution_reports(payload, output_dir=output_dir)
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    latest_path = Path(output_dir) / "latest_github_evolution_scan.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["latest_path"] = str(latest_path)
    return payload


def run_scan_in_terminal(objective: str, *, limit_per_query: int = 8, top_n: int = 20) -> dict[str, Any]:
    """Executa a varredura como subprocesso, simulando uso real no terminal da ATENA."""
    command = [
        sys.executable,
        "-m",
        "scripts.github_evolution_scan",
        objective,
        "--limit-per-query",
        str(limit_per_query),
        "--top-n",
        str(top_n),
        "--json",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-12000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vasculha GitHub em busca de sinais para evolução da ATENA")
    parser.add_argument("objective", nargs="*", help="Objetivo/tema de evolução")
    parser.add_argument("--limit-per-query", type=int, default=8, help="Limite por query GitHub")
    parser.add_argument("--top-n", type=int, default=20, help="Quantidade final de repositórios")
    parser.add_argument("--json", action="store_true", help="Imprime JSON completo")
    parser.add_argument("--absorb", action="store_true", help="Absorve achados como backlog versionado em docs/")
    parser.add_argument("--clone", action="store_true", help="Clona os melhores repositórios públicos encontrados em atena_evolution/")
    parser.add_argument("--clone-limit", type=int, default=None, help="Quantidade máxima a clonar; padrão clona todos os ranqueados")
    parser.add_argument("--incorporate", action="store_true", help="Clona e incorpora snapshots filtrados dos melhores repositórios em core/")
    parser.add_argument("--incorporate-limit", type=int, default=3, help="Quantidade máxima de repositórios incorporados em core/; padrão 3")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    objective = " ".join(args.objective).strip() or "evolução de agentes autônomos"
    payload = run_github_evolution_scan(
        objective,
        limit_per_query=args.limit_per_query,
        top_n=args.top_n,
        absorb=args.absorb,
        clone=args.clone,
        clone_limit=args.clone_limit,
        incorporate=args.incorporate,
        incorporate_limit=args.incorporate_limit,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ATENA GitHub evolution scan status={payload['status']} repos={payload['repo_count']}")
        print(f"JSON: {payload['json_path']}")
        print(f"MD: {payload['markdown_path']}")
        summary = payload.get("findings_summary", {})
        print(f"O que ela achou: {', '.join(summary.get('answer_what_she_found', [])[:5]) or 'nenhum repositório relevante'}")
        print(f"Interessante? {summary.get('verdict', 'n/a')}")
        print(f"Sempre acha coisa interessante? {summary.get('does_she_always_find_interesting_things', False)}")
        if payload.get("cloned"):
            clone_result = payload.get("clone_result", {})
            print(f"Clones locais: {clone_result.get('ok', 0)}/{clone_result.get('requested', 0)} em {clone_result.get('clone_dir')}")
        if payload.get("incorporated"):
            incorporation_result = payload.get("incorporation_result", {})
            print(f"Incorporado no core: {incorporation_result.get('ok', 0)}/{incorporation_result.get('requested', 0)} em {incorporation_result.get('core_dir')}")
        if payload.get("absorbed"):
            print(f"Absorvido no repositório: {payload.get('absorbed_path')}")
        for action in payload.get("evolution_actions", []):
            print(f"- {action}")
    return 0 if payload["status"] in {"ok", "warn"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
