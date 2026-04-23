#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validação leve de contratos JSON dos comandos de produção."""

from __future__ import annotations

from typing import Any


REQUIRED_FIELDS: dict[str, set[str]] = {
    "policy-check": {"allowed", "requires_approval", "reason"},
    "telemetry-summary": {"total", "success_rate", "avg_latency_ms", "cost_units"},
    "tenant-report": {"tenant_id", "total", "success_rate", "avg_latency_ms", "cost_units", "month"},
    "slo-check": {"window_days", "thresholds", "summary", "checks", "status"},
    "slo-alert": {"status", "alert", "sent", "delivery"},
    "quality-score": {"total", "passed", "score", "results", "baseline"},
    "skill-list": set(),
    "incident-drill": {"scenario", "primary_provider", "fallback_provider", "recovered", "timestamp"},
    "quota-check": {"quota", "usage", "checks", "status"},
    "production-ready": {"status", "checks", "summary"},
    "remediation-plan": {"status", "actions", "total_actions"},
    "perfection-plan": {"generated_at", "status", "tracks", "success_criteria"},
    "internet-challenge": {"topic", "status", "confidence", "sources", "recommendation"},
    "go-live-gate": {"decision", "blockers", "readiness_status", "slo_status", "pending_actions"},
    "self-audit": {"status", "score", "passed", "total", "checks", "recommendations"},
    "programming-probe": {"status", "score", "passed", "total", "checks", "generated_projects", "recommendation"},
    "eval-run": {"status", "passed", "total", "checks", "generated_at", "summary"},
    "issue-to-pr-plan": {"status", "issue", "repository", "steps", "next_action"},
    "rag-governance-check": {"status", "role", "data_classification", "checks", "recommendation"},
    "security-check": {"status", "risk_score", "blocked", "reasons", "recommended_action"},
    "finops-route": {"status", "mode", "reason", "estimated_cost_units", "budget_ok"},
    "incident-commander": {"status", "scenario", "severity", "actions", "summary"},
    "subagent-solve": {
        "status",
        "subagent",
        "problem",
        "plan",
        "integration",
        "result",
        "recommendations",
        "learning",
        "inferred_language",
        "diagnosis",
        "bug_found",
        "confidence",
        "fix_suggestion",
        "generated_at",
    },
}


def validate_contract(command: str, payload: Any) -> list[str]:
    required = REQUIRED_FIELDS.get(command)
    if required is None:
        return []
    if not isinstance(payload, dict) and command != "skill-list":
        return ["payload must be an object"]
    if command == "skill-list" and not isinstance(payload, list):
        return ["payload must be an array"]
    if isinstance(payload, dict):
        missing = [k for k in required if k not in payload]
        return [f"missing field: {k}" for k in missing]
    return []
