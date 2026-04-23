from __future__ import annotations

import core.atena_terminal_assistant as ta


def test_prompt_label_hides_local_brain_details(monkeypatch):
    monkeypatch.setattr(ta, "HAS_RICH", False)
    monkeypatch.setattr(ta, "git_branch", lambda: "work")

    label = ta.get_prompt_label("local:local-brain")

    assert "[work]" in label
    assert "[local]" in label
    assert "brain" not in label
