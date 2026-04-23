#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de validação externa AGI-like."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_agi_external_validation import run_external_validation, save_external_validation


def main() -> int:
    payload = run_external_validation(ROOT)
    js, md = save_external_validation(ROOT, payload)
    print("🧪 ATENA External AGI Validation")
    print(f"score_0_100={payload['score_0_100']}")
    print(f"score_1_10={payload['score_1_10']}")
    print(f"json={js}")
    print(f"markdown={md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
