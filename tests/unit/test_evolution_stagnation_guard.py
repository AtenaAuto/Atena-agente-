#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.evolution_stagnation_guard import analyze


def test_stagnation_detected_when_failures_and_score_flat():
    entries = [
        {
            "generation": i,
            "mutation": "Add type hints" if i % 2 == 0 else "Add docstring",
            "success": False,
            "score": 18.1333333333,
        }
        for i in range(100, 150)
    ]
    result = analyze(entries, window=40)
    assert result["mode"] == "stagnated"
    assert result["recommended_cycles"] == 10
    assert "--checker" in result["recommended_extra_flags"]


def test_stagnation_not_detected_with_mixed_success_and_score():
    entries = []
    for i in range(100, 150):
        entries.append(
            {
                "generation": i,
                "mutation": f"mutation-{i}",
                "success": i % 3 == 0,
                "score": 15.0 + (i % 5),
            }
        )
    result = analyze(entries, window=40)
    assert result["mode"] == "normal"
    assert result["recommended_cycles"] == 30
