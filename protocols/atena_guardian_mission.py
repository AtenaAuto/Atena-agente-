#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Ω Guardian Mission: gate essencial de prontidão operacional."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_codex import AtenaCodex
from modules.atena_telemetry_hub import AtenaTelemetryHub, TelemetryEvent


def is_autopilot_acceptable(autopilot: dict[str, object]) -> bool:
    status = str(autopilot.get("status", "")).lower()
    if status == "ok":
        return True
    if status != "partial":
        return False
    risk = float(autopilot.get("risk_score", 1.0) or 1.0)
    confidence = float(autopilot.get("confidence", 0.0) or 0.0)
    return risk <= 0.50 and confidence >= 0.50


def main() -> int:
    t0 = time.perf_counter()
    codex = AtenaCodex(root_path=str(ROOT))
    telemetry = AtenaTelemetryHub(ROOT)

    autopilot = codex.run_advanced_autopilot(
        objective="Gate essencial de estabilidade e segurança antes de evolução contínua",
        include_commands=False,
        timeout_seconds=60,
    )
    smoke = codex.run_module_smoke_suite(timeout_seconds=20)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")

    autopilot_acceptable = is_autopilot_acceptable(autopilot)
    guardian_ok = autopilot_acceptable and smoke.get("status") == "ok"

    failed_smoke = [r for r in smoke.get("results", []) if not r.get("ok", False)]
    blockers = []
    if not autopilot_acceptable:
        blockers.append("Autopilot fora da faixa aceitável (ok ou partial com risco/confiança mínimos)")
    if failed_smoke:
        blockers.append(f"Smoke suite com {len(failed_smoke)} falhas")

    docs_dir = ROOT / "docs"
    evo_dir = ROOT / "atena_evolution"
    docs_dir.mkdir(parents=True, exist_ok=True)
    evo_dir.mkdir(parents=True, exist_ok=True)

    md_path = docs_dir / f"GUARDIAN_REPORT_{stamp}.md"
    json_path = evo_dir / f"guardian_report_{now.strftime('%Y%m%d_%H%M%S')}.json"

    md_lines = [
        f"# Guardian Report — {stamp}",
        "",
        "## Status geral",
        f"- Guardian OK: **{guardian_ok}**",
        f"- Autopilot status: **{autopilot.get('status')}**",
        f"- Smoke status: **{smoke.get('status')}**",
        f"- Smoke passed: **{smoke.get('passed')} / {smoke.get('total_checks')}**",
        "",
        "## Blockers",
    ]
    if blockers:
        md_lines.extend([f"- {b}" for b in blockers])
    else:
        md_lines.append("- Nenhum blocker detectado")

    md_lines.extend([
        "",
        "## Recomendação essencial",
        "Executar evolução contínua apenas quando `Guardian OK=True`; caso contrário, bloquear promoções e corrigir blockers.",
    ])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    payload = {
        "generated_at": now.isoformat(),
        "guardian_ok": guardian_ok,
        "autopilot": {
            "status": autopilot.get("status"),
            "risk_score": autopilot.get("risk_score"),
            "confidence": autopilot.get("confidence"),
        },
        "smoke": {
            "status": smoke.get("status"),
            "passed": smoke.get("passed"),
            "failed": smoke.get("failed"),
            "total_checks": smoke.get("total_checks"),
        },
        "blockers": blockers,
        "report_markdown": str(md_path.relative_to(ROOT)),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🛡️ ATENA Guardian executado")
    print(f"Guardian OK: {guardian_ok}")
    print(f"Autopilot: {autopilot.get('status')} | Smoke: {smoke.get('status')} ({smoke.get('passed')}/{smoke.get('total_checks')})")
    print(f"Relatório: {md_path.relative_to(ROOT)}")
    print(f"Artefato: {json_path.relative_to(ROOT)}")
    telemetry.log_event(
        TelemetryEvent(
            mission="guardian",
            status="ok" if guardian_ok else "fail",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            metadata={
                "autopilot_status": autopilot.get("status"),
                "smoke_status": smoke.get("status"),
                "smoke_passed": smoke.get("passed"),
                "smoke_total": smoke.get("total_checks"),
            },
        )
    )
    return 0 if guardian_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
