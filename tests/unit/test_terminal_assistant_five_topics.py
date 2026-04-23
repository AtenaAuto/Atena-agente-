from __future__ import annotations

from core.atena_terminal_assistant import (
    _build_five_topics_prompt,
    _format_five_topics_response,
    _wants_five_topics,
)


def test_wants_five_topics_detects_variants():
    assert _wants_five_topics("me responda em 5 tópicos")
    assert _wants_five_topics("me responda em 5 topicos")
    assert not _wants_five_topics("me responda livremente")


def test_format_five_topics_response_parses_json():
    raw = '{"topicos":["A","B","C","D","E"]}'
    formatted = _format_five_topics_response(raw, "como evoluir")
    assert formatted.splitlines()[0] == "1. A"
    assert formatted.splitlines()[-1] == "5. E"


def test_format_five_topics_response_fallback_when_unstructured():
    raw = "texto confuso sem lista"
    formatted = _format_five_topics_response(raw, "como evoluir")
    lines = formatted.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("1.")


def test_build_five_topics_prompt_enforces_json_contract():
    prompt = _build_five_topics_prompt("como evoluir")
    assert "JSON válido" in prompt
    assert "\"topicos\"" in prompt
