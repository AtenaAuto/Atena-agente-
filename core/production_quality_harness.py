#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness de avaliação contínua por perfil de cliente."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class HarnessResult:
    profile: str
    command: str
    returncode: int
    ok: bool


PROFILE_COMMANDS: dict[str, str] = {
    "support": "./atena doctor",
    "dev": "./atena modules-smoke",
    "ops": "./atena go-no-go",
    "security": "./atena guardian",
}


def run_profile(profile: str, timeout: int = 180) -> HarnessResult:
    cmd = PROFILE_COMMANDS.get(profile)
    if not cmd:
        return HarnessResult(profile=profile, command="", returncode=2, ok=False)
    proc = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return HarnessResult(profile=profile, command=cmd, returncode=proc.returncode, ok=proc.returncode == 0)


def score_profiles(profiles: list[str]) -> dict[str, object]:
    results = [run_profile(p) for p in profiles]
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    return {
        "total": total,
        "passed": passed,
        "score": round((passed / total) if total else 0.0, 4),
        "results": [r.__dict__ for r in results],
    }


def score_profiles_with_baseline(profiles: list[str], baseline_path: str | Path) -> dict[str, object]:
    payload = score_profiles(profiles)
    baseline_file = Path(baseline_path)
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, object]] = []
    if baseline_file.exists():
        history = json.loads(baseline_file.read_text(encoding="utf-8"))

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": payload["score"],
        "profiles": profiles,
    }
    history.append(entry)
    baseline_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    previous_score = float(history[-2]["score"]) if len(history) > 1 else None
    trend = "stable"
    if previous_score is not None:
        if float(payload["score"]) > previous_score:
            trend = "up"
        elif float(payload["score"]) < previous_score:
            trend = "down"

    payload["baseline"] = {
        "history_points": len(history),
        "previous_score": previous_score,
        "trend": trend,
    }
    payload["history_entry"] = entry
    return payload
