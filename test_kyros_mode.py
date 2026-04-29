#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_kyros_mode import run_cmd, main


def test_run_cmd_success():
    rc, out = run_cmd(["bash", "-lc", "echo kyros_ok"], timeout=5)
    assert rc == 0
    assert "kyros_ok" in out


def test_run_cmd_timeout_is_handled():
    rc, out = run_cmd(["bash", "-lc", "sleep 2"], timeout=1)
    assert rc == 124
    assert "Timeout" in out


def test_main_status_returns_zero():
    rc = main(["--status"])
    assert rc == 0


def test_main_capabilities_returns_zero():
    rc = main(["--capabilities"])
    assert rc == 0
