#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telemetria estruturada simples para eventos de missão da ATENA."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "atena_evolution" / "logs" / "events.jsonl"


def emit_event(event_name: str, mission_id: str, status: str, **extra: Any) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_name": event_name,
        "mission_id": mission_id,
        "status": status,
        **extra,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
