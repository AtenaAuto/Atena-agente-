from __future__ import annotations

import types

import core.atena_env_bootstrap as bootstrap


def test_bootstrap_main_when_all_installed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(bootstrap, "is_installed", lambda _pkg: True)

    rc = bootstrap.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "já estão instaladas" in out


def test_bootstrap_installs_missing_dependencies(monkeypatch, capsys) -> None:
    installed_after = {"requests", "astor", "numpy", "aiosqlite", "rich"}

    def fake_is_installed(pkg: str) -> bool:
        return pkg in installed_after

    seen_cmd: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], check: bool = False):  # noqa: ARG001
        seen_cmd["cmd"] = cmd
        installed_after.add("psutil")
        installed_after.add("transformers")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(bootstrap, "is_installed", fake_is_installed)
    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)

    rc = bootstrap.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "psutil" in out
    assert "cmd" in seen_cmd
    assert "psutil" in seen_cmd["cmd"]
    assert "transformers" in seen_cmd["cmd"]
