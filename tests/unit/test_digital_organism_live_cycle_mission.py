from __future__ import annotations

from protocols.atena_digital_organism_live_cycle_mission import _resolve_topic


def test_resolve_topic_uses_explicit_topic() -> None:
    assert _resolve_topic("custom hard task", "agi-only") == "custom hard task"


def test_resolve_topic_uses_preset_for_agi_only_when_topic_missing() -> None:
    topic = _resolve_topic("", "agi-only")
    assert "multi-agent" in topic
    assert "self-recovers" in topic


def test_resolve_topic_falls_back_to_default_preset_for_unknown_level() -> None:
    assert _resolve_topic("", "unknown-level") == "autonomous ai engineering"
