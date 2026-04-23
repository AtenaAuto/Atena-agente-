#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos mínimos para reduzir acoplamento entre runtime e módulos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class MissionOutcome:
    mission_id: str
    status: str
    score: float
    details: str = ""


class RunnableMission(Protocol):
    def run(self) -> MissionOutcome: ...
