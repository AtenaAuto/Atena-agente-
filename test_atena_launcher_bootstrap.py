#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from types import SimpleNamespace

from core import atena_launcher


def test_launcher_runs_bootstrap_and_prepare_before_assistant(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "1")
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1")

    rc = atena_launcher.main(["./atena", "assistant"])

    assert rc == 0
    assert len(calls) == 3
    assert calls[0]["cmd"][1].endswith("core/atena_env_bootstrap.py")
    assert calls[0]["timeout"] == 180
    assert calls[1]["cmd"][1] == "-c"
    assert calls[1]["timeout"] == 300
    assert calls[2]["cmd"][1].endswith("core/atena_terminal_assistant.py")
    assert calls[2]["env"]["ATENA_AUTO_PREPARE_LOCAL_MODEL"] == "0"


def test_launcher_aborts_when_strict_bootstrap_fails(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        if cmd[1].endswith("core/atena_env_bootstrap.py"):
            return SimpleNamespace(returncode=2, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "1")
    monkeypatch.setenv("ATENA_STRICT_BOOTSTRAP", "1")

    rc = atena_launcher.main(["./atena", "assistant"])

    assert rc == 2
    assert len(calls) == 1


def test_launcher_executes_enterprise_readiness_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "enterprise-readiness", "--pilots", "5"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("protocols/atena_enterprise_readiness_mission.py")
    assert calls[0]["cmd"][2:] == ["--pilots", "5"]


def test_launcher_executes_enterprise_advanced_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "enterprise-advanced", "--tenant", "corp-a"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("protocols/atena_enterprise_advanced_mission.py")
    assert calls[0]["cmd"][2:] == ["--tenant", "corp-a"]


def test_launcher_executes_secret_scan_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "secret-scan"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_secret_scan.py")


def test_launcher_auto_installs_missing_dependency_and_retries(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        if cmd[1].endswith("protocols/atena_enterprise_readiness_mission.py") and kwargs.get("capture_output"):
            return SimpleNamespace(returncode=1, stdout="", stderr="ModuleNotFoundError: No module named 'yaml'")
        if cmd[1] == "-m" and cmd[2] == "pip":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")
    monkeypatch.setenv("ATENA_AUTO_INSTALL_MISSING_DEPS", "1")

    rc = atena_launcher.main(["./atena", "enterprise-readiness"])

    assert rc == 0
    assert len(calls) == 3
    assert calls[1]["cmd"][:4] == [atena_launcher.sys.executable, "-m", "pip", "install"]
    assert calls[1]["cmd"][4] == "pyyaml"


def test_launcher_executes_evolution_scorecard_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "evolution-scorecard"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_evolution_scorecard.py")


def test_launcher_executes_memory_relevance_audit_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "memory-relevance-audit"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_memory_relevance_audit.py")


def test_launcher_executes_memory_maintenance_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "memory-maintenance"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_memory_maintenance.py")


def test_launcher_executes_weekly_evolution_loop_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "weekly-evolution-loop"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_weekly_evolution_loop.py")


def test_launcher_hacker_recon_requires_topic(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=2, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "hacker-recon"])

    assert rc == 2
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_hacker_recon.py")


def test_launcher_hacker_alias_routes_to_recon(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "hacker", "--topic", "zero-day ai", "--auto", "--cycles", "2"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_hacker_recon.py")
    assert calls[0]["cmd"][2:] == ["--topic", "zero-day ai", "--auto", "--cycles", "2"]
