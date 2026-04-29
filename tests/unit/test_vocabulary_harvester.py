from __future__ import annotations

from core.main import VocabularyHarvester


def _harvester_without_init() -> VocabularyHarvester:
    return object.__new__(VocabularyHarvester)


def test_is_high_signal_term_accepts_advanced_terms() -> None:
    harvester = _harvester_without_init()
    assert harvester._is_high_signal_term("kubernetes")
    assert harvester._is_high_signal_term("vectorstore")
    assert harvester._is_high_signal_term("telemetry")
    assert harvester._is_high_signal_term("distributedcache")


def test_is_high_signal_term_rejects_generic_noise_terms() -> None:
    harvester = _harvester_without_init()
    assert not harvester._is_high_signal_term("main")
    assert not harvester._is_high_signal_term("resultado")
    assert not harvester._is_high_signal_term("with")
    assert not harvester._is_high_signal_term("python")


def test_term_signal_score_grades_terms() -> None:
    harvester = _harvester_without_init()
    assert harvester._term_signal_score("kubernetes") >= 2
    assert harvester._term_signal_score("vectorstore") >= 2
    assert harvester._term_signal_score("main") < 2
