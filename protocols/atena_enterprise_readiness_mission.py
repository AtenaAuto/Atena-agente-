#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão integrada de prontidão empresarial da ATENA.

Executa fluxo completo para empresas:
1) doctor
2) production-ready
3) professional-launch
4) code-build (api)
5) validação estrutural do artefato gerado

Gera relatório Markdown + JSON com score, status por etapa e recomendações.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EVOLUTION = ROOT / "atena_evolution"
DEFAULT_SECRET_ALLOWLIST = [
    r"^tests/unit/test_atena_secret_scan\.py:\d+$",
]


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    duration_s: float
    stdout: str
    stderr: str
    timed_out: bool = False


def _date_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run_step(name: str, command: list[str], timeout_s: int) -> StepResult:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        return StepResult(
            name=name,
            command=command,
            returncode=124,
            duration_s=duration,
            stdout=(exc.stdout or "").strip(),
            stderr=f"Timeout após {timeout_s}s",
            timed_out=True,
        )
    duration = time.perf_counter() - start
    return StepResult(
        name=name,
        command=command,
        returncode=proc.returncode,
        duration_s=duration,
        stdout=(proc.stdout or "").strip(),
        stderr=(proc.stderr or "").strip(),
    )


def _clip(text: str, limit: int = 800) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def _evaluate_generated_api(project_name: str, required_endpoints: list[str]) -> dict[str, object]:
    main_py = ROOT / "atena_evolution" / "generated_apps" / project_name / "main.py"
    if not main_py.exists():
        return {
            "ok": False,
            "reason": f"Arquivo não encontrado: {main_py}",
            "checked_file": str(main_py),
            "found_endpoints": [],
            "missing_endpoints": required_endpoints,
        }

    content = main_py.read_text(encoding="utf-8")
    missing = [endpoint for endpoint in required_endpoints if endpoint not in content]
    found = [endpoint for endpoint in required_endpoints if endpoint in content]
    return {
        "ok": not missing,
        "reason": "ok" if not missing else "Endpoints obrigatórios ausentes",
        "checked_file": str(main_py),
        "found_endpoints": found,
        "missing_endpoints": missing,
    }


def _compute_score(results: list[StepResult], structure_check_ok: bool) -> tuple[int, dict[str, int]]:
    weights = {
        "Doctor": 20,
        "Production Gate": 35,
        "Professional Launch": 20,
        "Code Build API": 25,
    }
    score = 0
    for item in results:
        if item.returncode == 0:
            score += weights.get(item.name, 0)
    if not structure_check_ok:
        score = max(score - 10, 0)
    return score, weights


def _check_repo_clean() -> dict[str, object]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    dirty_entries = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    return {
        "ok": proc.returncode == 0 and len(dirty_entries) == 0,
        "returncode": proc.returncode,
        "dirty_entries": dirty_entries[:50],
    }


def _scan_for_secrets(max_findings: int = 20) -> dict[str, object]:
    secret_patterns = [
        re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
    ]
    skip_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}
    findings: list[dict[str, object]] = []
    scanned_files = 0

    for path in ROOT.rglob("*"):
        if len(findings) >= max_findings:
            break
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            content = path.read_text(encoding="utf-8")
            scanned_files += 1
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            for pattern in secret_patterns:
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "line": line_no,
                            "pattern": pattern.pattern,
                        }
                    )
                    break
            if len(findings) >= max_findings:
                break

    return {
        "ok": len(findings) == 0,
        "findings": findings,
        "scanned_files": scanned_files,
    }


def _load_secret_allowlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _apply_allowlist(secret_scan: dict[str, object], allowlist_patterns: list[str]) -> dict[str, object]:
    if not allowlist_patterns:
        return secret_scan

    compiled = [re.compile(pattern) for pattern in allowlist_patterns]
    filtered: list[dict[str, object]] = []
    for finding in secret_scan.get("findings", []):
        location = f"{finding.get('file')}:{finding.get('line')}"
        if any(pattern.search(location) for pattern in compiled):
            continue
        filtered.append(finding)

    updated = dict(secret_scan)
    updated["findings"] = filtered
    updated["ok"] = len(filtered) == 0
    updated["allowlist_patterns"] = allowlist_patterns
    return updated


def _merge_allowlists(file_patterns: list[str]) -> list[str]:
    merged: list[str] = []
    for pattern in [*DEFAULT_SECRET_ALLOWLIST, *file_patterns]:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def _classify_release_risk(
    score: int,
    threshold: int,
    critical_fail: bool,
    structure_ok: bool,
    repo_clean_ok: bool,
    secret_ok: bool,
) -> str:
    if critical_fail or not secret_ok:
        return "critical"
    if score < threshold or not structure_ok:
        return "high"
    if not repo_clean_ok:
        return "medium"
    return "low"


def _build_markdown(
    results: list[StepResult],
    report_json: Path,
    project_name: str,
    overall_ok: bool,
    score: int,
    threshold: int,
    structure_check: dict[str, object],
    repo_clean: dict[str, object],
    secret_scan: dict[str, object],
    release_risk: str,
    blocking_reasons: list[str],
) -> str:
    status = "APROVADO" if overall_ok else "REPROVADO"

    lines = [
        f"# ATENA Enterprise Readiness Report ({_date_today()})",
        "",
        "## Objetivo",
        "Executar automaticamente uma trilha empresarial de pré-produção da ATENA, cobrindo gate técnico, plano de lançamento e geração de software.",
        "",
        f"## Status geral: **{status}**",
        f"- Score: **{score}/100** (threshold: {threshold})",
        "",
        "## Etapas executadas",
    ]

    for index, item in enumerate(results, start=1):
        icon = "✅" if item.returncode == 0 else "❌"
        lines.extend(
            [
                f"### {index}) {icon} {item.name}",
                "",
                "```bash",
                " ".join(item.command),
                "```",
                "",
                f"- Return code: `{item.returncode}`",
                f"- Duração: `{item.duration_s:.2f}s`",
                f"- Timeout: `{item.timed_out}`",
                "",
                "Saída (trecho):",
                "```text",
                _clip(item.stdout or "(sem stdout)"),
                "```",
            ]
        )
        if item.stderr:
            lines.extend(["", "Erro (trecho):", "```text", _clip(item.stderr), "```"])
        lines.append("")

    lines.extend(
        [
            "## Validação estrutural da API gerada",
            f"- Status: `{'ok' if structure_check.get('ok') else 'fail'}`",
            f"- Arquivo validado: `{structure_check.get('checked_file')}`",
            f"- Endpoints encontrados: `{structure_check.get('found_endpoints')}`",
            f"- Endpoints ausentes: `{structure_check.get('missing_endpoints')}`",
            "",
        ]
    )
    lines.extend(
        [
            "## Segurança e higiene de release",
            f"- Repositório limpo: `{'ok' if repo_clean.get('ok') else 'fail'}`",
            f"- Arquivos modificados detectados: `{len(repo_clean.get('dirty_entries', []))}`",
            f"- Secret scan: `{'ok' if secret_scan.get('ok') else 'fail'}`",
            f"- Arquivos escaneados: `{secret_scan.get('scanned_files')}`",
            f"- Segredos detectados: `{len(secret_scan.get('findings', []))}`",
            "",
        ]
    )
    lines.extend(
        [
            "## Classificação de risco",
            f"- Risk level: `{release_risk}`",
            f"- Blocking reasons: `{blocking_reasons}`",
            "",
        ]
    )

    recommendations: list[str] = []
    if score < threshold:
        recommendations.append("Aumentar score acima do threshold antes do go-live.")
    if structure_check.get("missing_endpoints"):
        recommendations.append("Corrigir geração da API para incluir todos endpoints obrigatórios.")
    if not repo_clean.get("ok"):
        recommendations.append("Executar release somente com working tree limpo.")
    if not secret_scan.get("ok"):
        recommendations.append("Bloquear go-live: remover/rotacionar credenciais expostas no repositório.")
    for item in results:
        if item.returncode != 0:
            recommendations.append(f"Corrigir falha na etapa '{item.name}' (rc={item.returncode}).")
    if not recommendations:
        recommendations.append("Aprovado para piloto controlado com observabilidade e rollback.")

    lines.extend(
        [
            "## Artefatos",
            f"- JSON consolidado: `{report_json}`",
            f"- Projeto API gerado: `atena_evolution/generated_apps/{project_name}`",
            "",
            "## Recomendação",
            *[f"- {item}" for item in recommendations],
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Enterprise Readiness Mission")
    parser.add_argument("--segment", default="times de engenharia de software", help="Segmento da missão comercial")
    parser.add_argument("--pilots", type=int, default=3, help="Quantidade de pilotos-alvo")
    parser.add_argument("--project-name", default="empresa_orquestracao_api", help="Nome do projeto API a gerar")
    parser.add_argument("--quality-threshold", type=int, default=85, help="Score mínimo (0-100) para aprovação")
    parser.add_argument("--step-timeout", type=int, default=240, help="Timeout por etapa, em segundos")
    parser.add_argument(
        "--required-endpoints",
        nargs="+",
        default=["/health", "/idea"],
        help="Endpoints obrigatórios esperados no main.py da API gerada",
    )
    parser.add_argument(
        "--allow-dirty-repo",
        action="store_true",
        help="Permite aprovação mesmo com alterações locais não commitadas",
    )
    parser.add_argument(
        "--allow-secrets-detected",
        action="store_true",
        help="Permite aprovação mesmo que secret scan detecte possíveis segredos",
    )
    parser.add_argument(
        "--secret-allowlist-file",
        default=".atena_secret_allowlist",
        help="Arquivo com regex por linha para ignorar findings de secret scan (formato file:line)",
    )
    args = parser.parse_args()

    DOCS.mkdir(parents=True, exist_ok=True)
    EVOLUTION.mkdir(parents=True, exist_ok=True)

    command_specs = [
        ("Doctor", [sys.executable, str(ROOT / "core" / "atena_doctor.py")]),
        ("Production Gate", [sys.executable, str(ROOT / "protocols" / "atena_production_mission.py")]),
        (
            "Professional Launch",
            [
                sys.executable,
                str(ROOT / "protocols" / "atena_professional_launch_mission.py"),
                "--segment",
                args.segment,
                "--pilots",
                str(args.pilots),
            ],
        ),
        (
            "Code Build API",
            [
                sys.executable,
                str(ROOT / "protocols" / "atena_code_build_mission.py"),
                "--type",
                "api",
                "--name",
                args.project_name,
                "--validate",
            ],
        ),
    ]

    repo_clean = _check_repo_clean()
    results = [_run_step(name, command, timeout_s=args.step_timeout) for name, command in command_specs]
    critical_fail = any(
        item.returncode != 0 and item.name in {"Doctor", "Production Gate"}
        for item in results
    )
    structure_check = _evaluate_generated_api(args.project_name, args.required_endpoints)
    secret_scan_raw = _scan_for_secrets()
    allowlist_patterns = _merge_allowlists(_load_secret_allowlist(ROOT / args.secret_allowlist_file))
    secret_scan = _apply_allowlist(secret_scan_raw, allowlist_patterns)
    score, weights = _compute_score(results, structure_check_ok=bool(structure_check.get("ok")))
    secrets_blocking = (not secret_scan.get("ok")) and (not args.allow_secrets_detected)
    dirty_blocking = (not repo_clean.get("ok")) and (not args.allow_dirty_repo)
    blocking_reasons: list[str] = []
    if critical_fail:
        blocking_reasons.append("critical_mission_step_failed")
    if not structure_check.get("ok"):
        blocking_reasons.append("structure_validation_failed")
    if score < args.quality_threshold:
        blocking_reasons.append("score_below_threshold")
    if secrets_blocking:
        blocking_reasons.append("secrets_detected")
    if dirty_blocking:
        blocking_reasons.append("dirty_repo_detected")
    overall_ok = (
        (not critical_fail)
        and bool(structure_check.get("ok"))
        and score >= args.quality_threshold
        and (not secrets_blocking)
        and (not dirty_blocking)
    )
    release_risk = _classify_release_risk(
        score=score,
        threshold=args.quality_threshold,
        critical_fail=critical_fail,
        structure_ok=bool(structure_check.get("ok")),
        repo_clean_ok=bool(repo_clean.get("ok")),
        secret_ok=bool(secret_scan.get("ok")),
    )

    ts = _timestamp()
    date_str = _date_today()
    json_path = EVOLUTION / f"enterprise_readiness_{ts}.json"
    md_path = DOCS / f"ENTERPRISE_READINESS_REPORT_{date_str}.md"

    payload = {
        "status": "ok" if overall_ok else "fail",
        "timestamp": ts,
        "segment": args.segment,
        "pilot_target": args.pilots,
        "project_name": args.project_name,
        "quality_threshold": args.quality_threshold,
        "score_0_100": score,
        "scoring_weights": weights,
        "structure_check": structure_check,
        "repo_clean_check": repo_clean,
        "secret_scan": secret_scan,
        "policy": {
            "allow_dirty_repo": args.allow_dirty_repo,
            "allow_secrets_detected": args.allow_secrets_detected,
            "secret_allowlist_file": args.secret_allowlist_file,
        },
        "release_risk": release_risk,
        "blocking_reasons": blocking_reasons,
        "steps": [
            {
                "name": item.name,
                "command": item.command,
                "returncode": item.returncode,
                "duration_s": round(item.duration_s, 3),
                "stdout": item.stdout,
                "stderr": item.stderr,
                "timed_out": item.timed_out,
            }
            for item in results
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_content = _build_markdown(
        results=results,
        report_json=json_path,
        project_name=args.project_name,
        overall_ok=overall_ok,
        score=score,
        threshold=args.quality_threshold,
        structure_check=structure_check,
        repo_clean=repo_clean,
        secret_scan=secret_scan,
        release_risk=release_risk,
        blocking_reasons=blocking_reasons,
    )
    md_path.write_text(md_content, encoding="utf-8")

    print("🏢 ATENA Enterprise Readiness Mission")
    print(f"Status: {'ok' if overall_ok else 'fail'}")
    print(f"Segmento: {args.segment}")
    print(f"Pilotos-alvo: {args.pilots}")
    print(f"Projeto API: {args.project_name}")
    print(f"Score: {score}/100 (threshold={args.quality_threshold})")
    print(f"Validação estrutural: {'ok' if structure_check.get('ok') else 'fail'}")
    print(f"Repo limpo: {'ok' if repo_clean.get('ok') else 'fail'}")
    print(f"Secret scan: {'ok' if secret_scan.get('ok') else 'fail'}")
    print(f"Risk: {release_risk}")
    print(f"Bloqueios: {blocking_reasons}")
    print(f"Relatório: {md_path}")
    print(f"Artefato: {json_path}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
