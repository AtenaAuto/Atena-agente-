#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecta estagnação de mutações e sugere parâmetros de evolução."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("entries"), list):
            return [x for x in data["entries"] if isinstance(x, dict)]
        return [data]
    return []


def _score_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def analyze(entries: list[dict[str, Any]], window: int = 40) -> dict[str, Any]:
    relevant = [e for e in entries if "generation" in e and "score" in e][-window:]
    if not relevant:
        return {
            "mode": "normal",
            "reason": "insufficient_data",
            "recommended_cycles": 30,
            "recommended_extra_flags": "",
            "window_size": 0,
        }

    scores = [float(e.get("score", 0.0)) for e in relevant]
    failures = sum(1 for e in relevant if not bool(e.get("success", False)))
    failure_rate = failures / len(relevant)
    score_std = _score_std(scores)
    mutations = [str(e.get("mutation", "")) for e in relevant if e.get("mutation")]
    unique_mut_ratio = (len(set(mutations)) / len(mutations)) if mutations else 0.0

    stagnated = failure_rate >= 0.9 and score_std < 0.06 and unique_mut_ratio < 0.75
    if stagnated:
        return {
            "mode": "stagnated",
            "reason": "high_failure_low_variance",
            "failure_rate": round(failure_rate, 4),
            "score_std": round(score_std, 6),
            "unique_mutation_ratio": round(unique_mut_ratio, 4),
            "recommended_cycles": 10,
            "recommended_extra_flags": "--checker",
            "window_size": len(relevant),
        }
    return {
        "mode": "normal",
        "reason": "healthy_or_mixed",
        "failure_rate": round(failure_rate, 4),
        "score_std": round(score_std, 6),
        "unique_mutation_ratio": round(unique_mut_ratio, 4),
        "recommended_cycles": 30,
        "recommended_extra_flags": "",
        "window_size": len(relevant),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Atena evolution stagnation guard")
    parser.add_argument("--input", default="analysis_reports/mutation_history.json", help="Arquivo json/jsonl com histórico de mutações.")
    parser.add_argument("--window", type=int, default=40, help="Janela de análise.")
    parser.add_argument("--output", default="", help="Saída JSON opcional.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    entries = _load_entries(input_path)
    result = analyze(entries, window=args.window)
    result["analyzed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["input_path"] = str(input_path)

    output_path = Path(args.output) if args.output else ROOT / "analysis_reports" / "EVOLUTION_STAGNATION_GUARD.json"
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))

    github_output = os.getenv("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"mode={result['mode']}\n")
            f.write(f"recommended_cycles={result['recommended_cycles']}\n")
            f.write(f"recommended_extra_flags={result['recommended_extra_flags']}\n")
            f.write(f"guard_report={output_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
