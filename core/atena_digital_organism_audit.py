#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria inteligente e reprodutível de maturidade de organismo digital da ATENA."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AuditCheck:
    id: str
    pillar: str
    command: list[str]
    weight: float
    description: str


@dataclass
class CheckEvidence:
    external_score_0_100: float | None = None
    parsed_json_path: str | None = None
    parsed_markdown_path: str | None = None


def default_checks() -> list[AuditCheck]:
    return [
        AuditCheck(
            id="doctor",
            pillar="safety-runtime",
            command=["./atena", "doctor"],
            weight=1.5,
            description="Sanidade de runtime, bootstrap e checagens básicas",
        ),
        AuditCheck(
            id="guardian",
            pillar="safety-gate",
            command=["./atena", "guardian"],
            weight=2.0,
            description="Gate de segurança e robustez operacional",
        ),
        AuditCheck(
            id="production-ready",
            pillar="operations",
            command=["./atena", "production-ready"],
            weight=2.0,
            description="Prontidão para produção",
        ),
        AuditCheck(
            id="agi-uplift",
            pillar="cognition-memory",
            command=["./atena", "agi-uplift"],
            weight=2.0,
            description="Memória, continuidade decisória e uplift cognitivo",
        ),
        AuditCheck(
            id="agi-external-validation",
            pillar="external-validation",
            command=["./atena", "agi-external-validation"],
            weight=2.5,
            description="Validação externa independente",
        ),
    ]


def _extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1))


def _extract_path(pattern: str, text: str) -> Path | None:
    match = re.search(pattern, text)
    if not match:
        return None
    candidate = match.group(1).strip()
    if not candidate:
        return None
    return Path(candidate)


def _parse_external_evidence(stdout: str, root: Path) -> CheckEvidence:
    evidence = CheckEvidence()
    evidence.external_score_0_100 = _extract_float(r"score_0_100=([0-9]+(?:\.[0-9]+)?)", stdout)

    json_path = _extract_path(r"json=([^\n]+)", stdout)
    md_path = _extract_path(r"markdown=([^\n]+)", stdout)

    if json_path:
        resolved = json_path if json_path.is_absolute() else root / json_path
        if resolved.exists():
            evidence.parsed_json_path = str(resolved)
            try:
                payload = json.loads(resolved.read_text(encoding="utf-8"))
                scored = payload.get("score_0_100")
                if isinstance(scored, (int, float)):
                    evidence.external_score_0_100 = float(scored)
            except Exception:
                pass

    if md_path:
        resolved_md = md_path if md_path.is_absolute() else root / md_path
        if resolved_md.exists():
            evidence.parsed_markdown_path = str(resolved_md)

    return evidence


def classify_stage(score_0_100: float) -> str:
    if score_0_100 >= 92:
        return "organismo_digital_v1_operacional"
    if score_0_100 >= 82:
        return "organismo_digital_emergente"
    if score_0_100 >= 65:
        return "agente_autonomo_em_transicao"
    return "sistema_automatizado_nao_organico"


def _build_recommendations(results: list[dict[str, Any]], stage: str) -> list[str]:
    by_id = {item["id"]: item for item in results}
    recommendations: list[str] = []

    if not by_id.get("doctor", {}).get("ok", False):
        recommendations.append("Corrigir falhas de bootstrap/runtime antes de qualquer evolução adicional.")
    if not by_id.get("guardian", {}).get("ok", False):
        recommendations.append("Bloquear promoção de versão enquanto Guardian não estiver estável.")
    if not by_id.get("production-ready", {}).get("ok", False):
        recommendations.append("Executar plano de hardening operacional para recuperar produção.")

    ext = by_id.get("agi-external-validation", {})
    ext_score = ext.get("evidence", {}).get("external_score_0_100")
    if isinstance(ext_score, (int, float)) and ext_score < 85:
        recommendations.append("Aumentar robustez externa com bateria adversarial e benchmarks independentes.")

    if stage == "organismo_digital_v1_operacional":
        recommendations.extend(
            [
                "Introduzir score de estabilidade longitudinal (7/30/90 dias).",
                "Adicionar governança de identidade/self com invariantes auditáveis.",
                "Implementar red-team contínuo para validação externa recorrente.",
            ]
        )

    if not recommendations:
        recommendations.append("Manter rotina de auditoria periódica e acompanhar tendência histórica de score.")

    return recommendations


def _calc_confidence(results: list[dict[str, Any]]) -> float:
    # Confiança cresce com checks bem-sucedidos + presença de evidência parseada.
    if not results:
        return 0.0
    ok_ratio = sum(1 for x in results if x.get("ok")) / len(results)
    evidence_ratio = sum(1 for x in results if x.get("evidence", {}).get("parsed_json_path")) / len(results)
    return round(min(1.0, 0.75 * ok_ratio + 0.25 * evidence_ratio), 3)


def _history_trend(root: Path, current_score: float, lookback: int = 10) -> dict[str, Any]:
    evo = root / "atena_evolution"
    files = sorted(evo.glob("digital_organism_audit_*.json"))
    tail = files[-lookback:] if files else []

    scores: list[float] = []
    for path in tail:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            val = payload.get("score_0_100")
            if isinstance(val, (int, float)):
                scores.append(float(val))
        except Exception:
            continue

    if not scores:
        return {
            "samples": 0,
            "mean_score_0_100": current_score,
            "delta_vs_mean": 0.0,
            "direction": "stable",
        }

    mean_score = round(sum(scores) / len(scores), 2)
    delta = round(current_score - mean_score, 2)
    direction = "up" if delta > 0.5 else ("down" if delta < -0.5 else "stable")
    return {
        "samples": len(scores),
        "mean_score_0_100": mean_score,
        "delta_vs_mean": delta,
        "direction": direction,
    }


def run_digital_organism_audit(root: Path, timeout_seconds: int = 300) -> dict[str, Any]:
    checks = default_checks()
    total_weight = sum(check.weight for check in checks)
    earned_weight = 0.0
    results: list[dict[str, Any]] = []

    for check in checks:
        score_factor = 0.0
        evidence = CheckEvidence()
        try:
            proc = subprocess.run(
                check.command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            ok = proc.returncode == 0
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            if check.id == "agi-external-validation":
                evidence = _parse_external_evidence(stdout, root)
                ext_score = evidence.external_score_0_100
                if ok and ext_score is not None:
                    score_factor = max(0.0, min(1.0, ext_score / 100.0))
                else:
                    score_factor = 1.0 if ok else 0.0
            else:
                score_factor = 1.0 if ok else 0.0

            earned_weight += check.weight * score_factor

            results.append(
                {
                    **asdict(check),
                    "ok": ok,
                    "score_factor": round(score_factor, 4),
                    "returncode": proc.returncode,
                    "stdout_tail": stdout[-1400:],
                    "stderr_tail": stderr[-800:],
                    "evidence": asdict(evidence),
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    **asdict(check),
                    "ok": False,
                    "score_factor": 0.0,
                    "returncode": -1,
                    "stdout_tail": "",
                    "stderr_tail": f"timeout>{timeout_seconds}s",
                    "evidence": asdict(evidence),
                }
            )

    score_0_100 = round((earned_weight / total_weight) * 100.0, 2) if total_weight else 0.0
    score_1_10 = round(score_0_100 / 10.0, 2)
    stage = classify_stage(score_0_100)
    verdict = (
        "ATENA atende critérios de organismo digital operacional (v1)."
        if score_0_100 >= 92
        else "ATENA ainda não atende critérios de organismo digital operacional (v1)."
    )

    trend = _history_trend(root, score_0_100)
    confidence = _calc_confidence(results)
    recommendations = _build_recommendations(results, stage)

    missing_capabilities = [
        "Autonomia de longo horizonte com metas hierárquicas persistentes.",
        "Governança explícita de identidade/self com invariantes auditáveis.",
        "Metacognição verificável com detecção de autoengano e rollback automático.",
        "Validação externa adversarial contínua (red-team recorrente).",
        "Interoperabilidade multiagente com contratos formais e SLA.",
    ]

    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_0_100": score_0_100,
        "score_1_10": score_1_10,
        "stage": stage,
        "verdict": verdict,
        "confidence_0_1": confidence,
        "earned_weight": round(earned_weight, 4),
        "total_weight": round(total_weight, 4),
        "trend": trend,
        "checks": results,
        "recommendations": recommendations,
        "missing_capabilities": missing_capabilities,
    }


def save_digital_organism_audit(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evolution = root / "atena_evolution"
    reports = root / "analysis_reports"
    evolution.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = evolution / f"digital_organism_audit_{ts}.json"
    md_path = reports / f"ATENA_Avaliacao_Organismo_Digital_Automatica_{date}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    trend = payload.get("trend", {})
    lines = [
        f"# ATENA — Auditoria Automática de Organismo Digital ({date})",
        "",
        f"- Score (0-100): **{payload['score_0_100']}**",
        f"- Score (1-10): **{payload['score_1_10']}**",
        f"- Estágio: **{payload['stage']}**",
        f"- Veredito: **{payload['verdict']}**",
        f"- Confiança da auditoria (0-1): **{payload.get('confidence_0_1', 0.0)}**",
        f"- Tendência: **{trend.get('direction', 'stable')}** (Δ vs média={trend.get('delta_vs_mean', 0.0)}, amostras={trend.get('samples', 0)})",
        "",
        "## Checks executados",
    ]

    for item in payload["checks"]:
        icon = "✅" if item["ok"] else "❌"
        cmd = " ".join(item["command"])
        ext = item.get("evidence", {}).get("external_score_0_100")
        ext_sfx = f" | ext_score={ext}" if ext is not None else ""
        lines.append(
            f"- {icon} `{item['id']}` ({item['pillar']}) w={item['weight']} fator={item['score_factor']} :: `{cmd}`{ext_sfx}"
        )

    lines.extend(["", "## Recomendações priorizadas"])
    for rec in payload.get("recommendations", []):
        lines.append(f"- {rec}")

    lines.extend(["", "## O que falta para maior maturidade"])
    for gap in payload["missing_capabilities"]:
        lines.append(f"- {gap}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
