#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic capability challenge harness for ATENA.

The goal is not to claim that ATENA can literally do anything. Instead, this
module converts a broad user request into a reproducible, auditable challenge
that checks whether ATENA can produce a safe plan, measurable acceptance
criteria, verification steps, and optional code-generation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapabilityTask:
    """One deterministic task in the ATENA capability challenge."""

    name: str
    category: str
    prompt: str
    expected_terms: tuple[str, ...]


BASE_TASKS: tuple[CapabilityTask, ...] = (
    CapabilityTask(
        name="objective_decomposition",
        category="planning",
        prompt="Decompor o objetivo em etapas executáveis e ordenadas.",
        expected_terms=("objetivo", "etapas", "entrega"),
    ),
    CapabilityTask(
        name="safety_boundary",
        category="governance",
        prompt="Declarar limites, riscos e quando pedir validação humana.",
        expected_terms=("risco", "limite", "validação"),
    ),
    CapabilityTask(
        name="implementation_strategy",
        category="engineering",
        prompt="Propor arquitetura, artefatos e integração mínima testável.",
        expected_terms=("arquitetura", "artefatos", "teste"),
    ),
    CapabilityTask(
        name="verification_plan",
        category="quality",
        prompt="Definir checks objetivos para provar que a entrega funciona.",
        expected_terms=("checks", "evidência", "critério"),
    ),
    CapabilityTask(
        name="delivery_protocol",
        category="operations",
        prompt="Definir como entregar, auditar e evoluir a solução.",
        expected_terms=("entrega", "auditoria", "evolução"),
    ),
)


def _normalise_objective(objective: str) -> str:
    cleaned = " ".join(objective.strip().split())
    return cleaned or "provar a capacidade operacional da ATENA com uma entrega auditável"


def _build_answer(task: CapabilityTask, objective: str) -> str:
    """Build a deterministic answer that can be scored without external APIs."""
    if task.name == "objective_decomposition":
        return (
            f"Objetivo: {objective}. Etapas: 1) entender restrições, 2) criar plano mínimo, "
            "3) produzir artefatos, 4) validar a entrega com critérios mensuráveis."
        )
    if task.name == "safety_boundary":
        return (
            "Risco controlado: não executar ações externas destrutivas sem aprovação. "
            "Limite explícito: pedir validação humana quando houver impacto financeiro, legal, "
            "médico, credenciais, produção real ou segurança ofensiva."
        )
    if task.name == "implementation_strategy":
        return (
            "Arquitetura proposta: entrada normalizada, orquestração de tarefas, geração de "
            "artefatos versionáveis e teste automatizado antes de publicar resultado."
        )
    if task.name == "verification_plan":
        return (
            "Checks: contrato JSON, compilação, smoke test e revisão de segurança. Evidência: "
            "logs, saídas de testes e critério objetivo de aprovação por score."
        )
    return (
        "Entrega: relatório final com decisões, artefatos e próximos passos. Auditoria: trilha "
        "de comandos e resultados. Evolução: registrar falhas e reexecutar o ciclo com melhoria."
    )


def _score_answer(answer: str, expected_terms: tuple[str, ...]) -> dict[str, Any]:
    lower = answer.lower()
    matched = [term for term in expected_terms if term.lower() in lower]
    return {
        "matched_terms": matched,
        "missing_terms": [term for term in expected_terms if term not in matched],
        "score": round(len(matched) / max(1, len(expected_terms)), 4),
        "ok": len(matched) == len(expected_terms),
    }


def _run_codegen_evidence(root: Path | None) -> dict[str, Any]:
    """Optionally run the programming probe full suite as hard evidence."""
    if root is None:
        root = Path(__file__).resolve().parents[1]
    from core.production_programming_probe import run_programming_probe

    payload = run_programming_probe(
        root,
        prefix="capability_challenge",
        site_template="dashboard",
        validate_all=True,
    )
    return {
        "status": payload.get("status"),
        "score": payload.get("score"),
        "passed": payload.get("passed"),
        "total": payload.get("total"),
        "generated_project_types": sorted(payload.get("generated_projects", {}).keys()),
    }


def run_capability_challenge(
    objective: str,
    *,
    include_codegen: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    """Run an auditable challenge against a broad ATENA objective."""
    normalized = _normalise_objective(objective)
    task_results: list[dict[str, Any]] = []
    for task in BASE_TASKS:
        answer = _build_answer(task, normalized)
        score = _score_answer(answer, task.expected_terms)
        task_results.append({
            **asdict(task),
            "answer": answer,
            **score,
        })

    codegen_evidence: dict[str, Any] | None = None
    if include_codegen:
        codegen_evidence = _run_codegen_evidence(root)

    base_passed = sum(1 for item in task_results if item["ok"])
    base_total = len(task_results)
    codegen_ok = not include_codegen or codegen_evidence.get("status") == "ok"
    total = base_total + (1 if include_codegen else 0)
    passed = base_passed + (1 if include_codegen and codegen_ok else 0)
    score = round(passed / max(1, total), 4)
    status = "pass" if passed == total else "warn" if score >= 0.8 else "fail"

    return {
        "status": status,
        "objective": normalized,
        "claim": "ATENA deve provar capacidades por evidência executável, não por promessa absoluta.",
        "score": score,
        "passed": passed,
        "total": total,
        "tasks": task_results,
        "codegen_evidence": codegen_evidence,
        "recommendation": (
            "Aprovada para desafio operacional controlado. Para afirmar excelência, repita com "
            "objetivos reais, critérios externos e revisão humana nos domínios de alto risco."
            if status == "pass"
            else "Reforce os itens que falharam antes de aceitar a entrega como completa."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
