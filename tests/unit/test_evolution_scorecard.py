from __future__ import annotations

import json
from pathlib import Path

from core.atena_evolution_scorecard import build_scorecard


def test_build_scorecard_with_minimal_inputs(tmp_path: Path):
    # estrutura mínima
    (tmp_path / "atena_evolution" / "enterprise_advanced").mkdir(parents=True)
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "atena_evolution" / "enterprise_advanced" / "enterprise_advanced_report.json").write_text(
        json.dumps(
            {
                "sre_auto_hardening": {"regression": {"risk": "medium"}},
                "internet_research_engine": {"weighted_confidence": 0.8},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "ANALISE_VALOR_ARTEFATOS_ATENA_2026-04-18.md").write_text(
        "- Valor médio dos artefatos: **3.3/5**.",
        encoding="utf-8",
    )

    scorecard = build_scorecard(tmp_path)

    assert scorecard["status"] in {"ok", "warn"}
    assert 0 <= scorecard["score_0_100"] <= 100
    assert "pillars" in scorecard
