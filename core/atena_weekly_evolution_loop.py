#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executa loop semanal de evolução contínua da ATENA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS = [
    ("secret-scan", [sys.executable, str(ROOT / "core" / "atena_secret_scan.py")]),
    ("memory-maintenance", [sys.executable, str(ROOT / "core" / "atena_memory_maintenance.py")]),
    ("memory-relevance-audit", [sys.executable, str(ROOT / "core" / "atena_memory_relevance_audit.py")]),
    ("evolution-scorecard", [sys.executable, str(ROOT / "core" / "atena_evolution_scorecard.py")]),
]


def run_loop(root: Path) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for step_name, cmd in STEPS:
        proc = subprocess.run(cmd, cwd=str(root), check=False, capture_output=True, text=True)
        results.append(
            {
                "step": step_name,
                "returncode": proc.returncode,
                "ok": proc.returncode == 0,
                "stdout": (proc.stdout or "").strip()[:1200],
                "stderr": (proc.stderr or "").strip()[:1200],
            }
        )

    all_ok = all(item["ok"] for item in results)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if all_ok else "warn",
        "steps_total": len(results),
        "steps_ok": sum(1 for item in results if item["ok"]),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Weekly Evolution Loop")
    parser.add_argument("--out-dir", default=str(ROOT / "analysis_reports"))
    args = parser.parse_args()

    payload = run_loop(ROOT)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "ATENA_Weekly_Evolution_Loop.json"
    out_md = out_dir / "ATENA_Weekly_Evolution_Loop.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        (
            "# ATENA Weekly Evolution Loop\n\n"
            f"- Status: **{payload['status']}**\n"
            f"- Steps ok: `{payload['steps_ok']}/{payload['steps_total']}`\n\n"
            "## Steps\n"
            + "\n".join(
                f"- `{item['step']}`: {'ok' if item['ok'] else 'fail'} (rc={item['returncode']})"
                for item in payload["results"]
            )
            + "\n"
        ),
        encoding="utf-8",
    )
    print("🔁 ATENA Weekly Evolution Loop")
    print(f"Status: {payload['status']}")
    print(f"JSON: {out_json}")
    print(f"MD: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
