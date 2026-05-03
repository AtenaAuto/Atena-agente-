from __future__ import annotations

from pathlib import Path

import protocols.atena_complex_research_mission as mission


class _FakeAgent:
    async def launch(self, headless: bool = True):
        return None

    async def navigate(self, url: str):
        return True, "<html></html>"

    async def get_text_content(self):
        return ""

    async def close(self):
        return None


def test_research_mission_uses_fallback_when_text_is_empty(monkeypatch) -> None:
    monkeypatch.setattr(mission, "AtenaBrowserAgent", _FakeAgent)
    mission.asyncio.run(mission.run_research_mission())

    report_path = Path(mission.__file__).parent.parent / "docs" / "ia_trends_2026_report.md"
    content = report_path.read_text(encoding="utf-8")

    assert "Apêndice: Evidência de pesquisa (trecho)" in content
    assert "síntese estratégica" in content
