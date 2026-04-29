#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera scorecard de evolução contínua da ATENA."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_secret_scan import scan_repo


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def build_scorecard(root: Path) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    findings = scan_repo(root)
    security_ok = len(findings) == 0

    enterprise_report = _read_json(root / "atena_evolution" / "enterprise_advanced" / "enterprise_advanced_report.json")
    sre_risk = (
        enterprise_report.get("sre_auto_hardening", {})
        .get("regression", {})
        .get("risk", "unknown")
    )
    weighted_confidence = (
        enterprise_report.get("internet_research_engine", {})
        .get("weighted_confidence")
    )

    artifact_report_path = root / "docs" / "ANALISE_VALOR_ARTEFATOS_ATENA_2026-04-18.md"
    artifact_avg = None
    if artifact_report_path.exists():
        for line in artifact_report_path.read_text(encoding="utf-8").splitlines():
            if "Valor médio dos artefatos" in line and "**" in line:
                try:
                    artifact_avg = float(line.split("**")[1].split("/")[0].strip())
                except Exception:  # noqa: BLE001
                    artifact_avg = None
                break

    score = 0.0
    score += 35.0 if security_ok else 10.0
    score += 30.0 if str(sre_risk).lower() in {"low", "medium"} else 12.0
    if isinstance(weighted_confidence, (int, float)):
        score += min(20.0, float(weighted_confidence) * 20.0)
    if isinstance(artifact_avg, (int, float)):
        score += min(15.0, float(artifact_avg) * 3.0)
    score = round(score, 2)

    return {
        "timestamp": now,
        "status": "ok" if score >= 70 else "warn",
        "score_0_100": score,
        "pillars": {
            "security": {"ok": security_ok, "findings": len(findings)},
            "reliability": {"sre_risk": sre_risk},
            "research": {"weighted_confidence": weighted_confidence},
            "quality": {"artifact_value_avg_0_5": artifact_avg},
        },
        "recommendations": [
            "Rodar secret-scan em cada PR",
            "Baixar risco SRE para low/medium antes de deploy",
            "Manter benchmark contínuo semanal",
            "Aumentar score de qualidade dos artefatos (>4.0/5)",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Evolution Scorecard")
    parser.add_argument("--out-dir", default=str(ROOT / "analysis_reports"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scorecard = build_scorecard(ROOT)

    out_json = out_dir / "ATENA_Evolution_Scorecard.json"
    out_md = out_dir / "ATENA_Evolution_Scorecard.md"
    out_json.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        (
            f"# ATENA Evolution Scorecard\n\n"
            f"- Timestamp: `{scorecard['timestamp']}`\n"
            f"- Status: **{scorecard['status']}**\n"
            f"- Score (0-100): **{scorecard['score_0_100']}**\n\n"
            f"## Pillars\n"
            f"- Security findings: `{scorecard['pillars']['security']['findings']}`\n"
            f"- SRE risk: `{scorecard['pillars']['reliability']['sre_risk']}`\n"
            f"- Weighted confidence: `{scorecard['pillars']['research']['weighted_confidence']}`\n"
            f"- Artifact avg (0-5): `{scorecard['pillars']['quality']['artifact_value_avg_0_5']}`\n"
        ),
        encoding="utf-8",
    )

    print("📊 ATENA Evolution Scorecard")
    print(f"Status: {scorecard['status']}")
    print(f"Score: {scorecard['score_0_100']}/100")
    print(f"JSON: {out_json}")
    print(f"MD: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
