#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guardrails de produção para ATENA (RBAC + política de ações + auditoria)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Action(str, Enum):
    READ_STATUS = "read_status"
    RUN_DIAGNOSTIC = "run_diagnostic"
    OPEN_URL = "open_url"
    RUN_MUTABLE_COMMAND = "run_mutable_command"
    KILL_PROCESS = "kill_process"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


@dataclass(frozen=True)
class AuditEvent:
    actor: str
    role: str
    action: str
    decision: str
    reason: str
    timestamp: str
    metadata: dict[str, str]


class PolicyEngine:
    """Política mínima para uso da ATENA em produção multiusuário."""

    _ALLOWLIST: dict[Role, set[Action]] = {
        Role.ADMIN: {
            Action.READ_STATUS,
            Action.RUN_DIAGNOSTIC,
            Action.OPEN_URL,
            Action.RUN_MUTABLE_COMMAND,
            Action.KILL_PROCESS,
        },
        Role.OPERATOR: {
            Action.READ_STATUS,
            Action.RUN_DIAGNOSTIC,
            Action.OPEN_URL,
        },
        Role.VIEWER: {
            Action.READ_STATUS,
        },
    }

    _APPROVAL_REQUIRED: set[Action] = {
        Action.OPEN_URL,
        Action.RUN_MUTABLE_COMMAND,
        Action.KILL_PROCESS,
    }

    def decide(self, role: Role, action: Action) -> PolicyDecision:
        return self.decide_with_context(role=role, action=action, risk_level="medium", hour_utc=12)

    def decide_with_context(self, *, role: Role, action: Action, risk_level: str, hour_utc: int) -> PolicyDecision:
        allowed = action in self._ALLOWLIST.get(role, set())
        if not allowed:
            return PolicyDecision(False, False, f"role={role.value} não pode executar {action.value}")

        normalized_risk = risk_level.strip().lower()
        if role == Role.OPERATOR and normalized_risk == "high":
            return PolicyDecision(False, True, "operator não pode executar ação de risco high")

        if action in {Action.RUN_MUTABLE_COMMAND, Action.KILL_PROCESS} and not (6 <= hour_utc <= 22):
            return PolicyDecision(False, True, "ação destrutiva fora da janela operacional UTC (06-22)")

        requires_approval = action in self._APPROVAL_REQUIRED or normalized_risk in {"high", "critical"}
        if requires_approval:
            return PolicyDecision(True, True, f"{action.value} requer aprovação explícita")
        return PolicyDecision(True, False, "permitido pela política")


class AuditLogger:
    """Logger JSONL para trilha de auditoria de decisões de política."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        actor: str,
        role: Role,
        action: Action,
        decision: PolicyDecision,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor=actor,
            role=role.value,
            action=action.value,
            decision="allowed" if decision.allowed else "denied",
            reason=decision.reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event
