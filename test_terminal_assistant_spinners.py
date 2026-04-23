#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_terminal_assistant import build_spinner


def test_spinner_presets_have_distinct_messages():
    task = build_spinner("task")
    plan = build_spinner("plan")
    brief = build_spinner("brief")
    assert task.message != plan.message
    assert plan.message != brief.message


def test_unknown_spinner_kind_falls_back_to_chat():
    spinner = build_spinner("unknown-kind")
    assert spinner.message == "Pensando resposta"
