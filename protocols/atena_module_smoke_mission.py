#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executa smoke suite de módulos ATENA (um por um)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_codex import AtenaCodex


def main() -> int:
    codex = AtenaCodex(root_path=str(ROOT))
    report = codex.run_module_smoke_suite(timeout_seconds=25)

    print("🧪 ATENA — Module Smoke Suite")
    print(f"Status: {report['status']}")
    print(f"Total checks: {report['total_checks']}")
    print(f"Passed: {report['passed']}")
    print(f"Failed: {report['failed']}")

    failed_items = [r for r in report["results"] if not r["ok"]]
    if failed_items:
        print("\nFalhas detectadas (top 10):")
        for item in failed_items[:10]:
            err = item.get("stderr", "")
            err_short = err.splitlines()[-1] if err else "sem stderr"
            print(f"- {item['target']} (rc={item['returncode']}): {err_short}")

    print(f"\nRelatório completo: {report['report_path']}")
    print("\nResumo JSON:")
    print(json.dumps({
        "status": report["status"],
        "passed": report["passed"],
        "failed": report["failed"],
        "report_path": report["report_path"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
