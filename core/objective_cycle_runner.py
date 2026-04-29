#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runner objetivo: evolução por ciclos com benchmark externo por janela."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Callable


@dataclass
class CycleSnapshot:
    cycle: int
    generation: int
    score: float
    mutation: str
    replaced: bool
    elapsed_sec: float


@dataclass
class ExternalBenchmarkSnapshot:
    cycle: int
    topic: str
    status: str
    confidence: float
    elapsed_sec: float


def _default_output_path(root: Path) -> Path:
    out_dir = root / "atena_evolution" / "objective_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return out_dir / f"objective_run_{stamp}.json"


def _trend_slope(samples: list[float]) -> float:
    """Retorna inclinação linear simples (ciclos x valor)."""
    n = len(samples)
    if n < 2:
        return 0.0
    xs = list(range(1, n + 1))
    x_mean = mean(xs)
    y_mean = mean(samples)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, samples))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return float(num / den)


def _build_learning_assessment(
    cycle_data: list[CycleSnapshot], benchmark_data: list[ExternalBenchmarkSnapshot]
) -> dict[str, Any]:
    if not cycle_data:
        return {
            "is_learning": False,
            "reason": "no_cycles",
            "score_trend_slope": 0.0,
            "positive_score_delta_ratio": 0.0,
            "benchmark_confidence_trend_slope": 0.0,
            "intelligence_index": 0.0,
        }

    scores = [c.score for c in cycle_data]
    score_deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
    positive_ratio = (
        sum(1 for d in score_deltas if d > 0) / len(score_deltas) if score_deltas else 0.0
    )
    score_slope = _trend_slope(scores)

    bench_conf = [b.confidence for b in benchmark_data]
    bench_slope = _trend_slope(bench_conf) if bench_conf else 0.0

    # Índice composto simples (0..1+) para dar leitura rápida de inteligência operacional.
    intelligence_index = (
        max(0.0, score_slope) * 0.5
        + positive_ratio * 0.3
        + max(0.0, bench_slope) * 0.2
    )

    # Critério objetivo mínimo de aprendizagem.
    is_learning = (
        len(scores) >= 20
        and score_slope > 0.0
        and positive_ratio >= 0.5
        and (not bench_conf or bench_slope >= 0.0)
    )

    return {
        "is_learning": is_learning,
        "reason": "ok" if is_learning else "insufficient_positive_trend",
        "score_trend_slope": round(score_slope, 6),
        "positive_score_delta_ratio": round(positive_ratio, 4),
        "benchmark_confidence_trend_slope": round(bench_slope, 6),
        "intelligence_index": round(float(intelligence_index), 6),
    }


def run_objective_cycles(
    *,
    cycles: int,
    benchmark_window: int,
    topic_template: str,
    output_path: Path | None = None,
    core_factory: Callable[[], Any] | None = None,
    benchmark_fn: Callable[[str], dict[str, Any]] | None = None,
    require_main_core: bool = True,
) -> dict[str, Any]:
    if cycles <= 0:
        raise ValueError("cycles deve ser > 0")
    if benchmark_window <= 0:
        raise ValueError("benchmark_window deve ser > 0")

    core_source = "injected"
    if core_factory is None:
        try:
            from core.main import AtenaCore

            core_factory = AtenaCore
            core_source = "core.main.AtenaCore"
        except Exception as exc:
            if require_main_core:
                raise RuntimeError(
                    "Falha ao carregar core.main.AtenaCore. Instale dependências e rode novamente."
                ) from exc
            from modules.atena_engine import AtenaCore

            core_factory = AtenaCore
            core_source = "modules.atena_engine.AtenaCore"
    if benchmark_fn is None:
        from core.internet_challenge import run_internet_challenge

        benchmark_fn = run_internet_challenge

    core = core_factory()
    if core_source == "injected":
        core_source = f"{core.__class__.__module__}.{core.__class__.__name__}"
    cycle_data: list[CycleSnapshot] = []
    benchmark_data: list[ExternalBenchmarkSnapshot] = []

    start = perf_counter()
    for cycle in range(1, cycles + 1):
        cycle_start = perf_counter()
        result = core.evolve_one_cycle()
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        cycle_data.append(
            CycleSnapshot(
                cycle=cycle,
                generation=int(result.get("generation", cycle)),
                score=float(result.get("score", 0.0)),
                mutation=str(result.get("mutation", "none")),
                replaced=bool(result.get("replaced", False)),
                elapsed_sec=round(perf_counter() - cycle_start, 4),
            )
        )

        should_benchmark = (cycle % benchmark_window == 0) or (cycle == cycles)
        if should_benchmark:
            topic = topic_template.format(cycle=cycle, generation=int(result.get("generation", cycle)))
            bench_start = perf_counter()
            bench = benchmark_fn(topic)
            benchmark_data.append(
                ExternalBenchmarkSnapshot(
                    cycle=cycle,
                    topic=topic,
                    status=str(bench.get("status", "unknown")),
                    confidence=float(bench.get("confidence", 0.0)),
                    elapsed_sec=round(perf_counter() - bench_start, 4),
                )
            )

    total_elapsed = round(perf_counter() - start, 4)
    accepted = sum(1 for item in cycle_data if item.replaced)
    learning = _build_learning_assessment(cycle_data, benchmark_data)
    summary = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycles_requested": cycles,
        "cycles_completed": len(cycle_data),
        "benchmark_window": benchmark_window,
        "benchmarks_executed": len(benchmark_data),
        "accepted_mutations": accepted,
        "acceptance_rate": round(accepted / max(1, len(cycle_data)), 4),
        "final_score": cycle_data[-1].score if cycle_data else 0.0,
        "total_elapsed_sec": total_elapsed,
        "avg_cycle_sec": round(total_elapsed / max(1, len(cycle_data)), 4),
        "learning_assessment": learning,
        "core_source": core_source,
    }

    payload = {
        "summary": summary,
        "cycles": [asdict(item) for item in cycle_data],
        "external_benchmarks": [asdict(item) for item in benchmark_data],
    }

    out = output_path or _default_output_path(Path(__file__).resolve().parent.parent)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa ciclos da ATENA com benchmark externo por janela")
    parser.add_argument("--cycles", type=int, default=300)
    parser.add_argument("--benchmark-window", type=int, default=25)
    parser.add_argument(
        "--topic-template",
        default="artificial intelligence benchmark cycle {cycle}",
        help="Template do tópico para benchmark externo. Suporta {cycle} e {generation}.",
    )
    parser.add_argument("--output", type=str, default="")
    parser.add_argument(
        "--strict-learning",
        action="store_true",
        help="Retorna exit code 2 se a avaliação indicar que não houve aprendizado consistente.",
    )
    parser.add_argument(
        "--allow-fallback-core",
        action="store_true",
        help="Permite fallback para modules.atena_engine.AtenaCore se o main não carregar.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve() if args.output else None
    payload = run_objective_cycles(
        cycles=args.cycles,
        benchmark_window=args.benchmark_window,
        topic_template=args.topic_template,
        output_path=output_path,
        require_main_core=not args.allow_fallback_core,
    )

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"report: {payload['output_path']}")
    if args.strict_learning and not payload["summary"]["learning_assessment"]["is_learning"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
