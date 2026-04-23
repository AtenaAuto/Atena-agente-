#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from core.atena_mission_runner import run_async_mission
from core.atena_mission_runner import run_mission
from core.atena_runtime_contracts import MissionOutcome


class TestMissionRunnerContract(unittest.TestCase):
    def test_run_mission_returns_outcome(self):
        def _runner() -> MissionOutcome:
            return MissionOutcome(mission_id="m:test", status="ok", score=0.9, details="fine")

        outcome = run_mission("m:test", _runner)
        self.assertEqual(outcome.status, "ok")
        self.assertAlmostEqual(outcome.score, 0.9)

    def test_run_async_mission_returns_outcome(self):
        async def _runner() -> MissionOutcome:
            return MissionOutcome(mission_id="m:async", status="ok", score=1.0, details="async-ok")

        import asyncio

        outcome = asyncio.run(run_async_mission("m:async", _runner))
        self.assertEqual(outcome.status, "ok")
        self.assertAlmostEqual(outcome.score, 1.0)


if __name__ == "__main__":
    unittest.main()
