#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPORTS = ROOT / "atena_evolution" / "codex_reports"


def latest_file(pattern: str) -> Path | None:
    files = sorted(DOCS.glob(pattern))
    return files[-1] if files else None


def latest_smoke() -> Path | None:
    files = sorted(REPORTS.glob("module_smoke_suite_*.json"))
    return files[-1] if files else None


def main() -> int:
    go_file = latest_file("ATENA_GO_NO_GO_DAILY_*.md")
    ent_file = ROOT / "docs" / "RELATORIO_EMPRESARIAL_ATENA_INTERNET_2026-05-04.md"
    ia_file = ROOT / "docs" / "IA_TRENDS_2026_REPORT.md"
    smoke_file = latest_smoke()

    score = 0.0
    details: list[str] = []

    # 4 pts: GO/NO-GO
    if go_file and "Status final: **GO**" in go_file.read_text(encoding="utf-8"):
        score += 4.0
        details.append("GO/NO-GO diário: GO (+4.0)")
    else:
        details.append("GO/NO-GO diário: ausente ou NO-GO (+0.0)")

    # 3 pts: smoke suite
    if smoke_file:
        data = json.loads(smoke_file.read_text(encoding="utf-8"))
        total = int(data.get("total_checks", 0))
        passed = int(data.get("passed", 0))
        if total > 0 and passed == total:
            score += 3.0
            details.append(f"Smoke suite: {passed}/{total} (+3.0)")
        elif total > 0:
            score += 3.0 * (passed / total)
            details.append(f"Smoke suite: {passed}/{total} (+{3.0 * (passed / total):.2f})")
    else:
        details.append("Smoke suite: sem relatório (+0.0)")

    # 1.5 pts: enterprise report
    if ent_file.exists() and "## Síntese Executiva" in ent_file.read_text(encoding="utf-8"):
        score += 1.5
        details.append("Relatório empresarial com síntese (+1.5)")
    else:
        details.append("Relatório empresarial incompleto (+0.0)")

    # 1.5 pts: internet trends evidence
    if ia_file.exists() and "## 6. Evidências da pesquisa" in ia_file.read_text(encoding="utf-8"):
        score += 1.5
        details.append("Relatório de tendências com evidências (+1.5)")
    else:
        details.append("Relatório de tendências sem evidências (+0.0)")

    score = round(min(score, 10.0), 2)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = DOCS / f"ATENA_SCORECARD_{ts}.md"

    lines = [
        "# ATENA Scorecard",
        "",
        f"- Timestamp UTC: {ts}",
        f"- Nota final: **{score}/10**",
        "",
        "## Breakdown",
    ] + [f"- {d}" for d in details]

    if score >= 9.5:
        lines += ["", "## Veredito", "ATENA está em nível **excelente (nota 10 operacional)** para execução assistida."]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Score ATENA: {score}/10")
    print(f"Relatório: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
