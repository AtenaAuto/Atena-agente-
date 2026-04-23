#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate formal de GO/NO-GO para liberar produção."""

from __future__ import annotations


def evaluate_go_live(
    *,
    readiness: dict[str, object],
    remediation: dict[str, object],
    slo_alert: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []

    if readiness.get("status") == "fail":
        blockers.append("readiness_status_fail")

    if float(slo_alert.get("status") == "ok") != 1.0:
        blockers.append("slo_not_ok")

    if int(remediation.get("total_actions", 0)) > 1:
        blockers.append("pending_actions")

    decision = "GO" if not blockers else "NO_GO"
    return {
        "decision": decision,
        "blockers": blockers,
        "readiness_status": readiness.get("status"),
        "slo_status": slo_alert.get("status"),
        "pending_actions": remediation.get("total_actions", 0),
    }
