#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Telemetry Hub: coleta e sumariza eventos de missão."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TelemetryEvent:
    mission: str
    status: str
    latency_ms: float
    metadata: dict[str, Any]


class AtenaTelemetryHub:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.telemetry_dir = self.root / "atena_evolution" / "telemetry"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.telemetry_dir / "events.jsonl"

    def log_event(self, event: TelemetryEvent) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mission": event.mission,
            "status": event.status,
            "latency_ms": round(float(event.latency_ms), 3),
            "metadata": event.metadata,
        }
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_events(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        lines = self.events_file.read_text(encoding="utf-8").splitlines()
        tail = lines[-limit:]
        out: list[dict[str, Any]] = []
        for line in tail:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def build_summary(self, limit: int = 200) -> dict[str, Any]:
        events = self.read_events(limit=limit)
        grouped = defaultdict(lambda: {"ok": 0, "fail": 0, "avg_latency_ms": 0.0, "count": 0})

        for e in events:
            mission = e.get("mission", "unknown")
            status = e.get("status", "unknown")
            latency = float(e.get("latency_ms", 0.0))
            grouped[mission]["count"] += 1
            grouped[mission]["avg_latency_ms"] += latency
            if status in ("ok", "approved", "success"):
                grouped[mission]["ok"] += 1
            else:
                grouped[mission]["fail"] += 1

        for mission, stats in grouped.items():
            if stats["count"] > 0:
                stats["avg_latency_ms"] = round(stats["avg_latency_ms"] / stats["count"], 3)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(events),
            "missions": dict(grouped),
        }
