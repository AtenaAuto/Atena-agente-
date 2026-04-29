#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulações operacionais de resiliência para o production-center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class IncidentDrillResult:
    scenario: str
    primary_provider: str
    fallback_provider: str
    primary_status: str
    fallback_status: str
    recovered: bool
    timestamp: str


def run_incident_drill(scenario: str, primary_provider: str = "provider-a", fallback_provider: str = "provider-b") -> IncidentDrillResult:
    scenario_key = scenario.strip().lower()
    if scenario_key in {"provider-outage", "timeout-cascade", "dependency-failure"}:
        primary_status = "failed"
        fallback_status = "ok"
        recovered = True
    else:
        primary_status = "ok"
        fallback_status = "not-needed"
        recovered = True
    return IncidentDrillResult(
        scenario=scenario,
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        primary_status=primary_status,
        fallback_status=fallback_status,
        recovered=recovered,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
