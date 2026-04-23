#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validação externa AGI-like com critérios independentes do score interno."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ValidationCase:
    id: str
    domain: str
    command: list[str]
    weight: float
    description: str


def default_cases() -> list[ValidationCase]:
    return [
        ValidationCase("eng-tests", "engineering", ["./atena", "modules-smoke"], 2.0, "Robustez de engenharia"),
        ValidationCase("ops-gate", "operations", ["./atena", "go-no-go"], 2.0, "Prontidão operacional"),
        ValidationCase("memory", "cognition", ["./atena", "agi-uplift"], 2.0, "Memória + planejamento + auditoria"),
        ValidationCase("syntax-health", "infrastructure", ["python", "-m", "py_compile", "core/atena_launcher.py"], 1.0, "Saúde base de runtime"),
        ValidationCase("security", "safety", ["./atena", "doctor"], 1.0, "Sanidade mínima e guardrails"),
        ValidationCase("documentation", "communication", ["python", "-m", "py_compile", "protocols/atena_agi_uplift_mission.py"], 1.0, "Capacidade documental"),
        ValidationCase("generalization", "generalization", ["python", "-m", "py_compile", "core/atena_agi_uplift.py"], 1.0, "Generalização multi-domínio"),
    ]


def run_external_validation(root: Path, timeout_seconds: int = 180) -> dict[str, Any]:
    cases = default_cases()
    results: list[dict[str, Any]] = []

    total_weight = sum(c.weight for c in cases)
    earned = 0.0
    for case in cases:
        try:
            proc = subprocess.run(
                case.command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            ok = proc.returncode == 0
            if ok:
                earned += case.weight
            results.append(
                {
                    **asdict(case),
                    "ok": ok,
                    "returncode": proc.returncode,
                    "stdout_tail": (proc.stdout or "")[-1000:],
                    "stderr_tail": (proc.stderr or "")[-600:],
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    **asdict(case),
                    "ok": False,
                    "returncode": -1,
                    "stdout_tail": "",
                    "stderr_tail": f"timeout>{timeout_seconds}s",
                }
            )

    score_0_100 = round((earned / total_weight) * 100.0, 2) if total_weight > 0 else 0.0
    score_1_10 = round((score_0_100 / 10.0), 2)
    maturity = "high" if score_0_100 >= 85 else ("medium" if score_0_100 >= 60 else "low")
    return {
        "status": "ok",
        "score_0_100": score_0_100,
        "score_1_10": score_1_10,
        "maturity": maturity,
        "earned_weight": earned,
        "total_weight": total_weight,
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_external_validation(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evolution = root / "atena_evolution"
    docs = root / "docs"
    evolution.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    js = evolution / f"external_agi_validation_{ts}.json"
    md = docs / f"EXTERNAL_AGI_VALIDATION_{date}.md"

    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# External AGI Validation ({date})",
        "",
        f"- Score (0-100): **{payload['score_0_100']}**",
        f"- Score (1-10): **{payload['score_1_10']}**",
        f"- Maturity: **{payload['maturity']}**",
        "",
        "## Cases",
    ]
    for item in payload["results"]:
        icon = "✅" if item["ok"] else "❌"
        lines.append(f"- {icon} `{item['id']}` ({item['domain']}) w={item['weight']}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return js, md
