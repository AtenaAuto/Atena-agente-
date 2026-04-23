#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera relatório consolidado de telemetria das missões da ATENA."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_telemetry_hub import AtenaTelemetryHub


def main() -> int:
    hub = AtenaTelemetryHub(ROOT)
    summary = hub.build_summary(limit=500)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")
    docs_dir = ROOT / "docs"
    evo_dir = ROOT / "atena_evolution"
    docs_dir.mkdir(parents=True, exist_ok=True)
    evo_dir.mkdir(parents=True, exist_ok=True)

    md_path = docs_dir / f"TELEMETRY_REPORT_{stamp}.md"
    json_path = evo_dir / f"telemetry_report_{now.strftime('%Y%m%d_%H%M%S')}.json"

    lines = [
        f"# Telemetry Report — {stamp}",
        "",
        f"- Total events: **{summary['total_events']}**",
        "",
        "## Missões",
    ]
    missions = summary.get("missions", {})
    if not missions:
        lines.append("- Sem eventos registrados ainda")
    else:
        for name, stats in sorted(missions.items()):
            lines.append(
                f"- **{name}**: ok={stats['ok']} fail={stats['fail']} avg_latency_ms={stats['avg_latency_ms']} count={stats['count']}"
            )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("📊 ATENA Telemetry Report")
    print(f"Eventos: {summary['total_events']}")
    print(f"Relatório: {md_path.relative_to(ROOT)}")
    print(f"Artefato: {json_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
