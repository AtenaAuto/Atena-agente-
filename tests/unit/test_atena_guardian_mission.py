#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from protocols.atena_guardian_mission import is_autopilot_acceptable


def test_is_autopilot_acceptable_accepts_ok():
    assert is_autopilot_acceptable({"status": "ok", "risk_score": 0.9, "confidence": 0.1}) is True


def test_is_autopilot_acceptable_accepts_safe_partial():
    assert is_autopilot_acceptable({"status": "partial", "risk_score": 0.45, "confidence": 0.60}) is True


def test_is_autopilot_acceptable_rejects_risky_partial():
    assert is_autopilot_acceptable({"status": "partial", "risk_score": 0.75, "confidence": 0.70}) is False
