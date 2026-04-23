#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telemetria/observabilidade operacional para ATENA."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class TelemetryEvent:
    mission: str
    status: str
    latency_ms: int
    cost_units: float
    timestamp: str
    tenant_id: str = "default"


class TelemetryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        mission: str,
        status: str,
        latency_ms: int,
        cost_units: float,
        tenant_id: str = "default",
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            mission=mission,
            status=status,
            latency_ms=latency_ms,
            cost_units=cost_units,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def _load_events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _summarize_events(lines: list[dict]) -> dict[str, float]:
        total = len(lines)
        ok = sum(1 for l in lines if str(l.get("status", "")).lower() in {"ok", "success"})
        avg_latency = (sum(int(l.get("latency_ms", 0)) for l in lines) / total) if total else 0.0
        cost = sum(float(l.get("cost_units", 0.0)) for l in lines)
        return {
            "total": total,
            "success_rate": round((ok / total) if total else 0.0, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "cost_units": round(cost, 4),
        }

    def summarize(self) -> dict[str, float]:
        return self._summarize_events(self._load_events())

    def summarize_by_tenant(self, tenant_id: str) -> dict[str, float]:
        lines = [l for l in self._load_events() if str(l.get("tenant_id", "default")) == tenant_id]
        payload = self._summarize_events(lines)
        payload["tenant_id"] = tenant_id
        return payload

    def summarize_since_days(self, days: int) -> dict[str, float]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, days))
        lines = []
        for item in self._load_events():
            raw_ts = item.get("timestamp")
            if not raw_ts:
                continue
            try:
                ts = datetime.fromisoformat(str(raw_ts))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                lines.append(item)
        return self._summarize_events(lines)


    @staticmethod
    def alert_state(summary: dict[str, float], *, min_success_rate: float, max_avg_latency_ms: int, max_cost_units: float) -> dict[str, object]:
        violations = []
        if summary["success_rate"] < min_success_rate:
            violations.append("success_rate")
        if summary["avg_latency_ms"] > max_avg_latency_ms:
            violations.append("avg_latency_ms")
        if summary["cost_units"] > max_cost_units:
            violations.append("cost_units")
        if not violations:
            severity = "none"
        elif len(violations) == 1:
            severity = "warning"
        else:
            severity = "critical"
        return {"severity": severity, "violations": violations}

    def slo_check(self, *, min_success_rate: float, max_avg_latency_ms: int, max_cost_units: float, window_days: int) -> dict[str, object]:
        summary = self.summarize_since_days(window_days)
        checks = {
            "success_rate": summary["success_rate"] >= min_success_rate,
            "avg_latency_ms": summary["avg_latency_ms"] <= max_avg_latency_ms,
            "cost_units": summary["cost_units"] <= max_cost_units,
        }
        alert = self.alert_state(
            summary,
            min_success_rate=min_success_rate,
            max_avg_latency_ms=max_avg_latency_ms,
            max_cost_units=max_cost_units,
        )
        return {
            "window_days": window_days,
            "thresholds": {
                "min_success_rate": min_success_rate,
                "max_avg_latency_ms": max_avg_latency_ms,
                "max_cost_units": max_cost_units,
            },
            "summary": summary,
            "checks": checks,
            "alert": alert,
            "status": "ok" if all(checks.values()) else "violated",
        }


def dispatch_alert(
    webhook_url: str,
    payload: dict[str, object],
    timeout: int = 10,
    retries: int = 2,
    backoff_sec: float = 1.0,
    dedupe_window_sec: int = 300,
    state_path: str | Path | None = None,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    dedupe_key = hashlib.sha256(body).hexdigest()

    if state_path is not None:
        state_file = Path(state_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state: dict[str, float] = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                state = {}
        now = time.time()
        previous = float(state.get(dedupe_key, 0.0))
        if previous and now - previous < dedupe_window_sec:
            return {"sent": False, "deduped": True, "dedupe_key": dedupe_key}

    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec - user-controlled endpoint
                code = getattr(response, "status", 200)
            if state_path is not None:
                state = {}
                state_file = Path(state_path)
                if state_file.exists():
                    try:
                        state = json.loads(state_file.read_text(encoding="utf-8"))
                    except Exception:  # noqa: BLE001
                        state = {}
                state[dedupe_key] = time.time()
                state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"sent": True, "http_status": int(code), "attempt": attempt, "dedupe_key": dedupe_key}
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts:
                return {"sent": False, "error": str(exc), "attempt": attempt, "dedupe_key": dedupe_key}
            time.sleep(max(0.0, backoff_sec) * attempt)

    return {"sent": False, "error": "unknown", "dedupe_key": dedupe_key}
