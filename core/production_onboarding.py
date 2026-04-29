#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Onboarding profissional 1-clique: doctor -> guardian -> production-ready -> professional-launch."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class StepResult:
    step: str
    command: str
    returncode: int
    ok: bool


ONBOARDING_STEPS: list[tuple[str, str]] = [
    ("doctor", "./atena doctor"),
    ("guardian", "./atena guardian"),
    ("production-ready", "./atena production-ready"),
    ("professional-launch", "./atena professional-launch"),
]


def run_onboarding(timeout: int = 180) -> dict[str, object]:
    results: list[StepResult] = []
    for step, cmd in ONBOARDING_STEPS:
        proc = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        item = StepResult(step=step, command=cmd, returncode=proc.returncode, ok=proc.returncode == 0)
        results.append(item)
        if not item.ok:
            break

    ok = all(r.ok for r in results) and len(results) == len(ONBOARDING_STEPS)
    return {
        "status": "ok" if ok else "partial",
        "completed_steps": len(results),
        "total_steps": len(ONBOARDING_STEPS),
        "results": [r.__dict__ for r in results],
    }
