#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de auditoria automática de organismo digital da ATENA."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_digital_organism_audit import run_digital_organism_audit, save_digital_organism_audit


def main() -> int:
    payload = run_digital_organism_audit(ROOT)
    json_path, md_path = save_digital_organism_audit(ROOT, payload)
    trend = payload.get("trend", {})
    print("🧬 ATENA Digital Organism Audit")
    print(f"score_0_100={payload['score_0_100']}")
    print(f"score_1_10={payload['score_1_10']}")
    print(f"stage={payload['stage']}")
    print(f"verdict={payload['verdict']}")
    print(f"confidence_0_1={payload.get('confidence_0_1', 0.0)}")
    print(f"trend_direction={trend.get('direction', 'stable')}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
