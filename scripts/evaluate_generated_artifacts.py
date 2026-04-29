#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avalia valor prático dos artefatos gerados pela ATENA."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ArtifactScore:
    path: str
    actionability: int
    novelty: int
    evidence: int
    risk: int
    overall: float
    notes: str


def _score_markdown(text: str, path: str) -> ArtifactScore:
    lower = text.lower()
    actionability = 2
    novelty = 2
    evidence = 1
    risk = 2
    notes = []

    if "mvp" in lower or "próxima ação" in lower or "backlog" in lower:
        actionability += 2
        notes.append("contém plano de execução")
    if "métricas" in lower or "score" in lower:
        actionability += 1
        evidence += 1
        notes.append("define métrica/score")
    if "arquitetura" in lower or "multiagente" in lower or "neuro-simbólico" in lower:
        novelty += 2
        notes.append("propõe arquitetura avançada")
    if "runbook" in lower or "citations" in lower or "fonte" in lower:
        evidence += 1
        notes.append("possui referência operacional")
    if "rollback" in lower or "risk" in lower or "risco" in lower:
        risk += 2
        notes.append("considera mitigação de risco")

    actionability = min(actionability, 5)
    novelty = min(novelty, 5)
    evidence = min(evidence, 5)
    risk = min(risk, 5)
    overall = round((actionability + novelty + evidence + risk) / 4, 2)
    return ArtifactScore(path, actionability, novelty, evidence, risk, overall, "; ".join(notes))


def _score_enterprise_report(payload: dict[str, object], path: str) -> ArtifactScore:
    actionability = 3
    novelty = 3
    evidence = 2
    risk = 2
    notes = []

    research = payload.get("internet_research_engine", {})
    sre = payload.get("sre_auto_hardening", {})
    redaction = payload.get("security_redaction", {})

    weighted_conf = float(research.get("weighted_confidence", 0.0) or 0.0)
    if weighted_conf >= 0.8:
        novelty += 1
        evidence += 1
        notes.append(f"weighted_confidence forte ({weighted_conf})")

    risk_level = str(sre.get("regression", {}).get("risk", "")).lower()
    if risk_level in {"high", "critical"}:
        risk += 2
        notes.append(f"risco SRE detectado: {risk_level}")

    if redaction.get("status") == "ok":
        risk += 1
        notes.append("relatório com trilha de redaction")

    actionability = min(actionability, 5)
    novelty = min(novelty, 5)
    evidence = min(evidence, 5)
    risk = min(risk, 5)
    overall = round((actionability + novelty + evidence + risk) / 4, 2)
    return ArtifactScore(path, actionability, novelty, evidence, risk, overall, "; ".join(notes))


def evaluate_artifact(path: Path) -> ArtifactScore:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _score_enterprise_report(payload, str(path))
    text = path.read_text(encoding="utf-8")
    return _score_markdown(text, str(path))


def build_markdown(scores: list[ArtifactScore]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Análise de Valor dos Artefatos ATENA ({ts})",
        "",
        "| Artefato | Actionability | Novelty | Evidence | Risk/Governance | Overall |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in scores:
        lines.append(
            f"| `{s.path}` | {s.actionability} | {s.novelty} | {s.evidence} | {s.risk} | **{s.overall}** |"
        )
    lines += ["", "## Notas", ""]
    for s in scores:
        lines.append(f"- `{s.path}`: {s.notes or 'sem observações'}")
    avg = round(sum(s.overall for s in scores) / max(1, len(scores)), 2)
    lines += ["", f"## Veredito", f"- Valor médio dos artefatos: **{avg}/5**."]
    return "\n".join(lines) + "\n"


def main() -> int:
    targets = [
        Path("docs/MISSAO_GENIAL_ATENA_2026-04-18.md"),
        Path("docs/PLANO_AVANCADO_ATENA_2026-04-18.md"),
        Path("docs/PROPOSTA_LAB_PESQUISA_AUTONOMA_2026-04-18.md"),
        Path("analysis_reports/ATENA_Organismo_Digital_Live_Cycle_2026-04-18.md"),
        Path("atena_evolution/enterprise_advanced/enterprise_advanced_report.json"),
    ]
    existing = [p for p in targets if p.exists()]
    if not existing:
        print("Nenhum artefato encontrado para avaliar.")
        return 1

    scores = [evaluate_artifact(p) for p in existing]
    report = build_markdown(scores)
    out = Path("docs/ANALISE_VALOR_ARTEFATOS_ATENA_2026-04-18.md")
    out.write_text(report, encoding="utf-8")
    print(f"Relatório gerado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
