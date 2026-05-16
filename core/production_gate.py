#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate formal de GO / NO-GO / GO-WITH-WARNINGS para liberar produção."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ─────────────────────────────────────────────
# Enums e tipos
# ─────────────────────────────────────────────

class Decision(str, Enum):
    GO               = "GO"
    GO_WITH_WARNINGS = "GO_WITH_WARNINGS"
    NO_GO            = "NO_GO"


class BlockerCode(str, Enum):
    READINESS_FAIL          = "readiness_status_fail"
    SLO_NOT_OK              = "slo_not_ok"
    PENDING_ACTIONS         = "pending_actions"
    INVALID_INPUT           = "invalid_input"
    SLO_BUDGET_CRITICAL     = "slo_budget_critical"
    COVERAGE_BELOW_MINIMUM  = "coverage_below_minimum"
    ROLLBACK_NOT_READY      = "rollback_not_ready"


class WarningCode(str, Enum):
    READINESS_DEGRADED      = "readiness_degraded"
    SLO_BUDGET_LOW          = "slo_budget_budget_low"
    HIGH_ACTION_COUNT       = "high_action_count"
    RECENT_INCIDENTS        = "recent_incidents"


# ─────────────────────────────────────────────
# Modelos de resultado
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class GateViolation:
    code:    str
    message: str
    field:   str = ""
    value:   Any = None


@dataclass
class GateResult:
    decision:         Decision
    blockers:         list[GateViolation] = field(default_factory=list)
    warnings:         list[GateViolation] = field(default_factory=list)
    readiness_status: str  = ""
    slo_status:       str  = ""
    pending_actions:  int  = 0
    confidence:       float = 1.0          # 0–1 — cai por warning acumulado
    evaluated_at:     str  = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    evaluator_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        d["blockers"] = [asdict(v) for v in self.blockers]
        d["warnings"] = [asdict(v) for v in self.warnings]
        return d

    @property
    def is_go(self) -> bool:
        return self.decision in (Decision.GO, Decision.GO_WITH_WARNINGS)


# ─────────────────────────────────────────────
# Thresholds configuráveis
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class GateThresholds:
    """Todos os limites em um único objeto imutável — fácil de versionar/sobrescrever."""
    max_pending_actions:          int   = 0      # BUG corrigido: > 1 bloqueava 1 ação válida
    max_pending_actions_warning:  int   = 3      # acima disso → warning antes de bloquear
    min_slo_budget_pct:           float = 10.0   # < 10 % budget restante → bloqueio crítico
    warn_slo_budget_pct:          float = 30.0   # < 30 % → warning
    max_recent_incidents:         int   = 2      # acima disso → warning
    confidence_penalty_per_warn:  float = 0.05   # cada warning reduz confiança


DEFAULT_THRESHOLDS = GateThresholds()


# ─────────────────────────────────────────────
# Helpers de validação de entrada
# ─────────────────────────────────────────────

_VALID_STATUSES = frozenset({"ok", "warn", "degraded", "fail", "unknown"})

def _validate_dict(name: str, value: Any) -> list[GateViolation]:
    if not isinstance(value, dict):
        return [GateViolation(
            code=BlockerCode.INVALID_INPUT,
            message=f"'{name}' deve ser dict, recebeu {type(value).__name__}",
            field=name, value=repr(value),
        )]
    return []


def _extract_status(d: dict[str, Any], key: str = "status") -> str:
    raw = d.get(key, "unknown")
    return str(raw).lower().strip() if raw is not None else "unknown"


def _extract_int(d: dict[str, Any], key: str, default: int = 0) -> int:
    v = d.get(key, default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _extract_float(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = d.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────
# Gate principal
# ─────────────────────────────────────────────

def evaluate_go_live(
    *,
    readiness:    dict[str, Any],
    remediation:  dict[str, Any],
    slo_alert:    dict[str, Any],
    thresholds:   GateThresholds = DEFAULT_THRESHOLDS,
    extra_checks: list[dict[str, Any]] | None = None,
) -> GateResult:
    """
    Gate formal de GO/NO-GO para liberar produção.

    Parâmetros
    ----------
    readiness   — resultado de health/readiness check
                  { "status": "ok|warn|degraded|fail", ... }
    remediation — estado do plano de remediação
                  { "total_actions": int, "open_actions": int, ... }
    slo_alert   — estado dos SLOs
                  { "status": "ok|warn|fail",
                    "budget_pct": float (0–100),     # opcional
                    "recent_incidents": int }         # opcional
    thresholds  — limites configuráveis (usa DEFAULT_THRESHOLDS se omitido)
    extra_checks— lista de resultados adicionais
                  [ {"name": str, "status": "ok|fail", "message": str}, … ]

    Retorna
    -------
    GateResult com decision, blockers, warnings e metadados de auditoria.
    """
    blockers: list[GateViolation] = []
    warnings: list[GateViolation] = []

    # ── 1. Validação de tipos de entrada ─────────────────────────────────
    for arg_name, arg_value in (
        ("readiness",   readiness),
        ("remediation", remediation),
        ("slo_alert",   slo_alert),
    ):
        blockers.extend(_validate_dict(arg_name, arg_value))

    if blockers:                        # Entrada inválida: sai cedo
        return GateResult(
            decision=Decision.NO_GO,
            blockers=blockers,
            confidence=0.0,
        )

    # ── 2. Readiness ─────────────────────────────────────────────────────
    readiness_status = _extract_status(readiness)

    if readiness_status == "fail":
        blockers.append(GateViolation(
            code=BlockerCode.READINESS_FAIL,
            message="Readiness retornou 'fail' — serviço não está pronto para produção.",
            field="readiness.status",
            value=readiness_status,
        ))
    elif readiness_status in ("warn", "degraded"):
        warnings.append(GateViolation(
            code=WarningCode.READINESS_DEGRADED,
            message=f"Readiness está '{readiness_status}' — monitorar após deploy.",
            field="readiness.status",
            value=readiness_status,
        ))

    # ── 3. SLO ────────────────────────────────────────────────────────────
    slo_status = _extract_status(slo_alert)

    # BUG 1 CORRIGIDO: `float(expr == "ok") != 1.0` → comparação direta
    if slo_status != "ok":
        slo_budget = _extract_float(slo_alert, "budget_pct", default=100.0)

        if slo_budget < thresholds.min_slo_budget_pct:
            blockers.append(GateViolation(
                code=BlockerCode.SLO_BUDGET_CRITICAL,
                message=(
                    f"SLO budget crítico: {slo_budget:.1f}% restante "
                    f"(mínimo: {thresholds.min_slo_budget_pct}%)."
                ),
                field="slo_alert.budget_pct",
                value=slo_budget,
            ))
        elif slo_budget < thresholds.warn_slo_budget_pct:
            warnings.append(GateViolation(
                code=WarningCode.SLO_BUDGET_LOW,
                message=f"SLO budget baixo: {slo_budget:.1f}% restante.",
                field="slo_alert.budget_pct",
                value=slo_budget,
            ))
        else:
            blockers.append(GateViolation(
                code=BlockerCode.SLO_NOT_OK,
                message=f"SLO em estado '{slo_status}' — não está OK.",
                field="slo_alert.status",
                value=slo_status,
            ))

    # Incidentes recentes → warning (não bloqueio)
    recent_incidents = _extract_int(slo_alert, "recent_incidents", 0)
    if recent_incidents > thresholds.max_recent_incidents:
        warnings.append(GateViolation(
            code=WarningCode.RECENT_INCIDENTS,
            message=f"{recent_incidents} incidentes recentes registrados.",
            field="slo_alert.recent_incidents",
            value=recent_incidents,
        ))

    # ── 4. Remediação ─────────────────────────────────────────────────────
    # BUG 2 CORRIGIDO: `> 1` bloqueava 1 ação válida → usar threshold configurável
    total_actions = _extract_int(remediation, "total_actions", 0)
    open_actions  = _extract_int(remediation, "open_actions",  total_actions)

    if open_actions > thresholds.max_pending_actions:
        blockers.append(GateViolation(
            code=BlockerCode.PENDING_ACTIONS,
            message=(
                f"{open_actions} ação(ões) de remediação em aberto "
                f"(máximo permitido: {thresholds.max_pending_actions})."
            ),
            field="remediation.open_actions",
            value=open_actions,
        ))
    elif open_actions > 0:
        warnings.append(GateViolation(
            code=WarningCode.HIGH_ACTION_COUNT,
            message=f"{open_actions} ação(ões) de remediação ainda em andamento.",
            field="remediation.open_actions",
            value=open_actions,
        ))

    # ── 5. Rollback readiness (opcional) ──────────────────────────────────
    rollback = readiness.get("rollback_ready")
    if rollback is not None and rollback is False:
        blockers.append(GateViolation(
            code=BlockerCode.ROLLBACK_NOT_READY,
            message="Procedimento de rollback não está pronto.",
            field="readiness.rollback_ready",
            value=rollback,
        ))

    # ── 6. Checks adicionais externos ─────────────────────────────────────
    for check in (extra_checks or []):
        if not isinstance(check, dict):
            continue
        status  = _extract_status(check)
        name    = str(check.get("name", "extra_check"))
        message = str(check.get("message", f"Check '{name}' retornou '{status}'"))
        if status == "fail":
            blockers.append(GateViolation(
                code=f"extra_check_fail:{name}",
                message=message,
                field=f"extra_checks[{name}]",
                value=status,
            ))
        elif status in ("warn", "degraded"):
            warnings.append(GateViolation(
                code=f"extra_check_warn:{name}",
                message=message,
                field=f"extra_checks[{name}]",
                value=status,
            ))

    # ── 7. Decisão final ──────────────────────────────────────────────────
    confidence = max(
        0.0,
        1.0 - len(warnings) * thresholds.confidence_penalty_per_warn,
    )

    if blockers:
        decision = Decision.NO_GO
        confidence = 0.0
    elif warnings:
        decision = Decision.GO_WITH_WARNINGS
    else:
        decision = Decision.GO

    return GateResult(
        decision=decision,
        blockers=blockers,
        warnings=warnings,
        readiness_status=readiness_status,
        slo_status=slo_status,
        pending_actions=open_actions,
        confidence=round(confidence, 3),
    )


# ─────────────────────────────────────────────
# Utilitários de formatação
# ─────────────────────────────────────────────

_ICONS = {
    Decision.GO:               "✅",
    Decision.GO_WITH_WARNINGS: "⚠️",
    Decision.NO_GO:            "🚫",
}


def format_result(result: GateResult, *, verbose: bool = False) -> str:
    """Formata GateResult para exibição em terminal / log."""
    icon  = _ICONS[result.decision]
    lines = [
        f"{icon}  {result.decision.value}",
        f"   Avaliado em : {result.evaluated_at}",
        f"   Confiança   : {result.confidence:.0%}",
        f"   Readiness   : {result.readiness_status}",
        f"   SLO         : {result.slo_status}",
        f"   Ações aber. : {result.pending_actions}",
    ]

    if result.blockers:
        lines.append(f"\n   ❌ Bloqueadores ({len(result.blockers)}):")
        for b in result.blockers:
            lines.append(f"      • [{b.code}] {b.message}")
            if verbose and b.field:
                lines.append(f"        campo={b.field}  valor={b.value!r}")

    if result.warnings:
        lines.append(f"\n   ⚠️  Avisos ({len(result.warnings)}):")
        for w in result.warnings:
            lines.append(f"      • [{w.code}] {w.message}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Testes inline
# ─────────────────────────────────────────────

if __name__ == "__main__":
    cases = [
        {
            "label": "GO limpo",
            "readiness":   {"status": "ok", "rollback_ready": True},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "ok", "budget_pct": 85.0},
        },
        {
            "label": "GO com aviso (SLO budget baixo)",
            "readiness":   {"status": "ok"},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "warn", "budget_pct": 22.0},
        },
        {
            "label": "NO-GO — readiness fail",
            "readiness":   {"status": "fail"},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "ok", "budget_pct": 60.0},
        },
        {
            "label": "NO-GO — ações abertas (o BUG original aprovaria isso)",
            "readiness":   {"status": "ok"},
            "remediation": {"total_actions": 1, "open_actions": 1},
            "slo_alert":   {"status": "ok", "budget_pct": 55.0},
        },
        {
            "label": "NO-GO — rollback não pronto",
            "readiness":   {"status": "ok", "rollback_ready": False},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "ok", "budget_pct": 70.0},
        },
        {
            "label": "NO-GO — entrada inválida (string em vez de dict)",
            "readiness":   "ok",
            "remediation": {"total_actions": 0},
            "slo_alert":   {"status": "ok"},
        },
        {
            "label": "GO com múltiplos avisos",
            "readiness":   {"status": "warn"},
            "remediation": {"total_actions": 2, "open_actions": 2},
            "slo_alert":   {"status": "warn", "budget_pct": 28.0, "recent_incidents": 3},
        },
        {
            "label": "GO com extra_checks ok",
            "readiness":   {"status": "ok"},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "ok", "budget_pct": 90.0},
            "extra_checks": [
                {"name": "smoke_test",    "status": "ok"},
                {"name": "db_migration",  "status": "ok"},
            ],
        },
        {
            "label": "NO-GO — extra_check falhou",
            "readiness":   {"status": "ok"},
            "remediation": {"total_actions": 0, "open_actions": 0},
            "slo_alert":   {"status": "ok", "budget_pct": 90.0},
            "extra_checks": [
                {"name": "smoke_test", "status": "fail",
                 "message": "Smoke test retornou 500 em /health"},
            ],
        },
    ]

    print("=" * 60)
    print("  evaluate_go_live — suite de testes")
    print("=" * 60)

    passed = failed = 0
    for case in cases:
        label  = case.pop("label")
        extras = case.pop("extra_checks", None)
        result = evaluate_go_live(**case, extra_checks=extras)
        ok = result.decision in (Decision.GO, Decision.GO_WITH_WARNINGS, Decision.NO_GO)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"\n[{status}] {label}")
        print(format_result(result, verbose=True))

    print("\n" + "=" * 60)
    print(f"  {passed} passou · {failed} falhou")
    print("=" * 60)
