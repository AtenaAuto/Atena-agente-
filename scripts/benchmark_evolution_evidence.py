#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, statistics, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "protocols" / "atena_digital_organism_live_cycle_mission.py"
HISTORY = ROOT / "analysis_reports" / "evolution_evidence_history.jsonl"


def run_batch(iterations: int, topic: str, strict: bool) -> dict:
    cmd = ["python3", str(MISSION), "--iterations", str(iterations), "--topic", topic]
    if strict:
        cmd.append("--strict")
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    m = re.search(r"json=(.*)", out.stdout)
    payload = json.loads(Path(m.group(1).strip()).read_text(encoding="utf-8"))
    return payload["summary"]


def slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    xbar = statistics.mean(xs)
    ybar = statistics.mean(values)
    num = sum((x-xbar)*(y-ybar) for x,y in zip(xs, values))
    den = sum((x-xbar)**2 for x in xs) or 1.0
    return num/den


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--topic", default="autonomous ai engineering")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    rows = []
    for _ in range(args.rounds):
        s = run_batch(args.iterations, args.topic, args.strict)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "iterations": args.iterations,
            "topic": args.topic,
            "success_rate": s.get("success_rate", 0.0),
            "learning_conf": s.get("avg_learning_confidence", 0.0),
            "fitness": s.get("avg_fitness", 0.0),
        }
        rows.append(row)

    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    hist = [json.loads(x) for x in HISTORY.read_text(encoding='utf-8').splitlines() if x.strip()]
    recent = hist[-max(5, args.rounds):]
    fit_vals = [float(r.get("fitness", 0.0)) for r in recent]
    conf_vals = [float(r.get("learning_conf", 0.0)) for r in recent]
    sr_vals = [float(r.get("success_rate", 0.0)) for r in recent]

    fit_slope = slope(fit_vals)
    conf_slope = slope(conf_vals)
    sr_mean = statistics.mean(sr_vals) if sr_vals else 0.0

    evolving = (sr_mean >= 0.9) and (fit_slope >= 0.0) and (conf_slope >= 0.0)

    report = {
        "recent_runs": len(recent),
        "success_rate_mean": sr_mean,
        "fitness_slope": fit_slope,
        "learning_conf_slope": conf_slope,
        "evolving": evolving,
    }
    out = ROOT / "analysis_reports" / "evolution_evidence_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"history={HISTORY}")
    print(f"report={out}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
