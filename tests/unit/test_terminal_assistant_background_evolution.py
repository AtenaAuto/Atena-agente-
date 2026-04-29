#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from core import atena_terminal_assistant as ta


def test_materialize_self_generated_assets_creates_files(monkeypatch, tmp_path):
    monkeypatch.setattr(ta, "ROOT", tmp_path)
    payload = {
        "status": "ok",
        "sources": [
            {
                "source": "github",
                "ok": True,
                "details": {"top_repos": [{"full_name": "org/always-on-agent"}]},
            }
        ],
    }

    created = ta.materialize_self_generated_assets("always-on evolution", payload)
    assert len(created) == 1
    assert (tmp_path / created[0]["module_path"]).exists()
    assert (tmp_path / created[0]["skill_path"]).exists()
    assert (tmp_path / created[0]["plugin_path"]).exists()

    manifest = json.loads((tmp_path / "atena_evolution" / "self_generated_assets.json").read_text(encoding="utf-8"))
    assert manifest["assets"]


def test_background_cycle_always_materializes(monkeypatch):
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {"status": "ok", "confidence": 0.8, "sources": [{"source": "x"}], "topic": topic},
    )
    called = {"value": False}

    def _fake_materialize(topic, payload):
        called["value"] = True
        return []

    monkeypatch.setattr(ta, "materialize_self_generated_assets", _fake_materialize)
    monkeypatch.setattr(ta, "append_learning_memory", lambda entry: None)
    ta.run_background_internet_learning_cycle("always-on")
    assert called["value"] is True


def test_parse_background_topics_defaults():
    topics = ta.parse_background_topics(None)
    assert len(topics) >= 2
