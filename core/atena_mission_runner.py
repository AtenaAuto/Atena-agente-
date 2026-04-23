#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runner padronizado para missões com contratos + telemetria."""

from __future__ import annotations

import inspect
from time import perf_counter
from typing import Awaitable
from typing import Callable

from core.atena_runtime_contracts import MissionOutcome
from core.atena_telemetry import emit_event


def run_mission(mission_id: str, runner: Callable[[], MissionOutcome]) -> MissionOutcome:
    emit_event("mission_start", mission_id, "started")
    t0 = perf_counter()
    outcome = runner()
    duration_ms = int((perf_counter() - t0) * 1000)
    emit_event(
        "mission_finish",
        mission_id,
        outcome.status,
        score=outcome.score,
        duration_ms=duration_ms,
        details=outcome.details,
    )
    return outcome


async def run_async_mission(
    mission_id: str,
    runner: Callable[[], MissionOutcome | Awaitable[MissionOutcome]],
) -> MissionOutcome:
    emit_event("mission_start", mission_id, "started")
    t0 = perf_counter()
    outcome_or_awaitable = runner()
    if inspect.isawaitable(outcome_or_awaitable):
        outcome = await outcome_or_awaitable
    else:
        outcome = outcome_or_awaitable
    duration_ms = int((perf_counter() - t0) * 1000)
    emit_event(
        "mission_finish",
        mission_id,
        outcome.status,
        score=outcome.score,
        duration_ms=duration_ms,
        details=outcome.details,
    )
    return outcome
