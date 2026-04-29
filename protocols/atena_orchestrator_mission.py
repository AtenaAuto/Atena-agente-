#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão avançada da ATENA usando o novo Mission Orchestrator."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.mission_orchestrator import AtenaMissionOrchestrator, TaskNode


def main() -> int:
    orchestrator = AtenaMissionOrchestrator(root_path=ROOT)

    def step_github(_ctx):
        data = requests.get(
            "https://api.github.com/repos/AtenaAuto/ATENA-", timeout=12
        ).json()
        return {
            "repo_stars": data.get("stargazers_count", 0),
            "repo_forks": data.get("forks_count", 0),
        }

    def step_hn(_ctx):
        data = requests.get(
            "https://hn.algolia.com/api/v1/search?query=ai%20agent%20security&tags=story&hitsPerPage=3",
            timeout=12,
        ).json()
        titles = [item.get("title") for item in data.get("hits", []) if item.get("title")]
        return {"hn_security_titles": titles}

    def step_signal(ctx):
        score = int(ctx.get("repo_stars", 0)) + len(ctx.get("hn_security_titles", []))
        level = "high" if score >= 20 else "medium" if score >= 5 else "low"
        return {
            "signal_score": score,
            "signal_level": level,
        }

    orchestrator.add_task(TaskNode(name="github_metrics", handler=step_github, retries=1, retry_delay_seconds=0.2))
    orchestrator.add_task(TaskNode(name="hn_security_scan", handler=step_hn, retries=1, retry_delay_seconds=0.2))
    orchestrator.add_task(TaskNode(name="signal_synthesis", handler=step_signal))

    result = orchestrator.run(initial_context={"mission": "atena_orchestrator_mission"})

    out = ROOT / "atena_evolution" / f"orchestrator_mission_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🧠 ATENA Orchestrator Mission concluída")
    print(f"Status: {result.get('status')}")
    print(f"Steps: {result.get('completed_steps')}/{result.get('total_tasks')}")
    print(f"Signal: {result.get('context', {}).get('signal_level')} (score={result.get('context', {}).get('signal_score')})")
    print(f"Checkpoint: {result.get('checkpoint_path')}")
    print(f"Artefato: {out.relative_to(ROOT)}")
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
