from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "scan_github_ai_repos.py"
    spec = importlib.util.spec_from_file_location("scan_github_ai_repos", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dedupe_rank_keeps_highest_star_entry():
    mod = _load_module()
    repos = [
        mod.RepoSnapshot("org/a", "u", "d", 10, "Python", "2026-01-01"),
        mod.RepoSnapshot("org/a", "u", "d", 100, "Python", "2026-01-02"),
        mod.RepoSnapshot("org/b", "u", "d", 50, "Go", "2026-01-03"),
    ]

    ranked = mod.dedupe_rank(repos, top_n=10)

    assert [r.full_name for r in ranked] == ["org/a", "org/b"]
    assert ranked[0].stargazers_count == 100


def test_main_writes_watchlist(monkeypatch, tmp_path):
    mod = _load_module()

    def fake_search(_query: str, per_page: int = 20):
        return [
            mod.RepoSnapshot("org/x", "https://example/x", "desc", 999, "Python", "2026-01-01"),
            mod.RepoSnapshot("org/y", "https://example/y", "desc", 500, "Go", "2026-01-02"),
        ]

    monkeypatch.setattr(mod, "search_repos", fake_search)
    monkeypatch.chdir(tmp_path)

    rc = mod.main()
    assert rc == 0

    out_file = tmp_path / "docs" / "ai_repo_watchlist.json"
    assert out_file.exists()

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["count"] >= 2
    assert payload["repos"][0]["full_name"] == "org/x"
