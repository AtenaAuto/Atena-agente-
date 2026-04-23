#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_terminal_assistant as assistant


def test_validate_self_generated_assets_success(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant, "ROOT", tmp_path)

    module = tmp_path / "modules" / "auto_generated" / "auto_ok.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("def describe() -> str:\n    return 'ok'\n", encoding="utf-8")

    skill = tmp_path / "skills" / "auto-evolution" / "ok" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# skill\n", encoding="utf-8")

    plugin = tmp_path / "plugins" / "auto-evolution" / "ok" / "README.md"
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_text("# plugin\n", encoding="utf-8")

    created = [
        {
            "manifest_key": "test::ok",
            "module_path": str(module.relative_to(tmp_path)),
            "skill_path": str(skill.relative_to(tmp_path)),
            "plugin_path": str(plugin.relative_to(tmp_path)),
        }
    ]

    result = assistant.validate_self_generated_assets(created)
    assert result["status"] == "ok"
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_validate_self_generated_assets_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant, "ROOT", tmp_path)

    bad_module = tmp_path / "modules" / "auto_generated" / "auto_bad.py"
    bad_module.parent.mkdir(parents=True, exist_ok=True)
    bad_module.write_text("def broken(:\n    pass\n", encoding="utf-8")

    created = [
        {
            "manifest_key": "test::bad",
            "module_path": str(bad_module.relative_to(tmp_path)),
            "skill_path": "skills/auto-evolution/bad/SKILL.md",
            "plugin_path": "plugins/auto-evolution/bad/README.md",
        }
    ]

    result = assistant.validate_self_generated_assets(created)
    assert result["status"] == "failed"
    assert result["passed"] == 0
    assert result["failed"] == 1
    assert result["checks"][0]["module_ok"] is False
