#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Ciclo de Vida do Organismo Digital (v2 — integrado)
Agora conecta: ParallelEvolution, SmartRollback, SelfHealing, EventBus, RLHF e MetaLearner.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.internet_challenge import run_internet_challenge
from modules.atena_code_module import AtenaCodeModule

# ── Novos módulos integrados ──────────────────────────────────────────────────
try:
    from core.atena_event_bus import get_event_bus, EventType, emit as bus_emit
    _BUS = get_event_bus()
    HAS_BUS = True
except Exception:
    HAS_BUS = False
    def bus_emit(t, s, p=None): pass  # noqa

try:
    from core.atena_parallel_evolution import ParallelEvolutionEngine
    HAS_EVOLUTION = True
except Exception:
    HAS_EVOLUTION = False

try:
    from core.atena_smart_rollback import SmartRollbackManager
    _ROLLBACK = SmartRollbackManager()
    HAS_ROLLBACK = True
except Exception:
    HAS_ROLLBACK = False
    _ROLLBACK = None

try:
    from core.atena_self_healing import SelfHealingSystem
    _HEALING = SelfHealingSystem()
    HAS_HEALING = True
except Exception:
    HAS_HEALING = False
    _HEALING = None

try:
    from modules.rlhf_engine import RLHFEngine
    _RLHF = RLHFEngine()
    HAS_RLHF = True
except Exception:
    HAS_RLHF = False
    _RLHF = None

try:
    from core.atena_meta_learner import SelfReflectiveMetaLearner
    _META = SelfReflectiveMetaLearner()
    HAS_META = True
except Exception:
    HAS_META = False
    _META = None

logger = logging.getLogger("atena.live_cycle")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    safe = re.sub(r"[^a-z0-9_-]+", "-", lowered)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe or "atena-project"


def _safe_project_name(topic: str, max_slug_len: int = 80) -> str:
    slug = _slugify(topic)[:max_slug_len].rstrip("-")
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    return f"{slug}-{ts}"


def _memory_success_bias(root: Path) -> dict[str, float]:
    memory_path = root / "atena_evolution" / "digital_organism_memory.jsonl"
    if not memory_path.exists():
        return {}
    stats: dict[str, dict[str, float]] = {}
    for raw in memory_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        ptype = str(entry.get("build", {}).get("project_type", "")).strip()
        if not ptype:
            continue
        ok = bool(entry.get("execution", {}).get("ok", False))
        bucket = stats.setdefault(ptype, {"total": 0.0, "ok": 0.0})
        bucket["total"] += 1.0
        if ok:
            bucket["ok"] += 1.0
    return {
        ptype: round(b["ok"] / b["total"], 3)
        for ptype, b in stats.items()
        if b["total"] > 0
    }


def _pick_project_type(learning_payload: dict[str, Any], memory_bias: dict[str, float] | None = None) -> str:
    sources = {item.get("source"): item for item in learning_payload.get("sources", [])}
    weighted_conf = float(learning_payload.get("weighted_confidence", 0.0))
    npm_q  = float(sources.get("npm",    {}).get("quality_score", 0.0))
    gh_q   = float(sources.get("github", {}).get("quality_score", 0.0))

    if weighted_conf >= 0.70 and (npm_q >= 0.70 or gh_q >= 0.70):
        base = "api"
    elif weighted_conf >= 0.60:
        base = "site"
    else:
        base = "cli"

    memory_bias = memory_bias or {}
    if not memory_bias:
        return base
    best = max(memory_bias, key=lambda k: memory_bias[k])
    if memory_bias[best] - memory_bias.get(base, 0.0) >= 0.20:
        return best
    return base


def _validate_execution(project_type: str, project_dir: Path) -> dict[str, Any]:
    if project_type == "site":
        index = project_dir / "index.html"
        if not index.exists():
            return {"ok": False, "reason": "index.html ausente"}
        content = index.read_text(encoding="utf-8", errors="replace")
        ok = "<html" in content.lower() and len(content) > 200
        return {"ok": ok, "reason": "html validado" if ok else "html inválido"}

    main_py = project_dir / "main.py"
    if not main_py.exists():
        return {"ok": False, "reason": "main.py ausente"}

    compile_proc = subprocess.run(
        ["python3", "-m", "py_compile", str(main_py)],
        capture_output=True, text=True, check=False,
    )
    if compile_proc.returncode != 0:
        return {"ok": False, "reason": "py_compile falhou", "stderr": compile_proc.stderr[-400:]}

    if project_type == "api":
        content = main_py.read_text(encoding="utf-8", errors="replace")
        ok = "@app.get('/health')" in content and "@app.get('/idea')" in content
        return {"ok": ok, "reason": "endpoints ok" if ok else "endpoints ausentes"}

    run_proc = subprocess.run(
        ["python3", str(main_py), "ATENA"],
        cwd=str(project_dir), capture_output=True, text=True, check=False,
    )
    ok = run_proc.returncode == 0 and "ATENA" in (run_proc.stdout or "")
    return {
        "ok": ok,
        "reason": "CLI ok" if ok else "CLI falhou",
        "stdout_tail": (run_proc.stdout or "")[-300:],
        "stderr_tail":  (run_proc.stderr or "")[-300:],
    }


def _persist_learning_memory(root: Path, entry: dict[str, Any]) -> Path:
    evo = root / "atena_evolution"
    evo.mkdir(parents=True, exist_ok=True)
    memory_path = evo / "digital_organism_memory.jsonl"
    with memory_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return memory_path


def _save_cycle_artifacts(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evo     = root / "atena_evolution"
    reports = root / "analysis_reports"
    evo.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = evo     / f"digital_organism_live_cycle_{ts}.json"
    md_path   = reports / f"ATENA_Organismo_Digital_Live_Cycle_{date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# ATENA — Live Cycle ({date})",
        f"- Tópico: **{payload['topic']}**",
        f"- Status: **{payload['status']}**",
        f"- Projeto: **{payload['build']['project_type']} / {payload['build']['project_name']}**",
        f"- Execução: **{'ok' if payload['execution']['ok'] else 'fail'}**",
        f"- Fitness: **{payload.get('fitness', 'N/A')}**",
        "",
        "## Sistemas Integrados",
        f"- Evolução paralela : {'✅' if payload.get('evolution_applied') else '⬜'}",
        f"- Rollback manager  : {'✅' if HAS_ROLLBACK else '⬜'}",
        f"- Self-healing      : {'✅' if HAS_HEALING else '⬜'}",
        f"- RLHF feedback     : {'✅' if HAS_RLHF else '⬜'}",
        f"- Meta-aprendizado  : {'✅' if HAS_META else '⬜'}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _build_and_validate(
    root: Path, topic: str, project_type: str, code_module: AtenaCodeModule
) -> tuple[dict[str, Any], dict[str, Any]]:
    project_name = _safe_project_name(topic)
    build = code_module.build(project_type=project_type, project_name=project_name)
    build_payload = {
        "ok": build.ok, "project_type": build.project_type,
        "project_name": build.project_name, "output_dir": build.output_dir,
        "message": build.message,
    }
    execution = {"ok": False, "reason": "build_failed"}
    if build.ok:
        execution = _validate_execution(build.project_type, Path(build.output_dir))
    return build_payload, execution


def _compute_fitness(build_payload: dict, execution: dict, learning: dict) -> float:
    score = 0.0
    if build_payload.get("ok"):        score += 40.0
    if execution.get("ok"):            score += 40.0
    conf = float(learning.get("weighted_confidence", 0.0) or 0.0)
    score += conf * 20.0
    return round(min(100.0, score), 2)


# ── Ciclo principal ───────────────────────────────────────────────────────────

def run_live_cycle(root: Path, topic: str, max_recovery_attempts: int = 1) -> dict[str, Any]:
    t0 = time.monotonic()
    bus_emit(EventType.CYCLE_START, "live_cycle", {"topic": topic})
    logger.info("🌀 Ciclo iniciado: %s", topic)

    # 1. Aprendizado da internet
    learning = run_internet_challenge(topic)

    # 2. Seleção de tipo de projeto
    memory_bias  = _memory_success_bias(root)
    project_type = _pick_project_type(learning, memory_bias=memory_bias)

    # 3. Build + validação
    code_module = AtenaCodeModule(root)
    build_payload, execution = _build_and_validate(root, topic, project_type, code_module)
    recovery_chain: list[dict] = []

    # 4. Self-healing: registra componente e reporta falha se necessário
    if HAS_HEALING and _HEALING:
        _HEALING.register_component(
            "code_module",
            module_path="modules.atena_code_module",
            db_path=str(root / "atena_evolution" / "knowledge" / "knowledge.db"),
        )
        if not build_payload.get("ok"):
            _HEALING.report_failure("code_module", build_payload.get("message", "build falhou"))
            bus_emit(EventType.COMPONENT_FAILED, "live_cycle", {"component": "code_module"})
        else:
            _HEALING.report_success("code_module")

    # 5. Recuperação por fallback de tipo de projeto
    if not execution.get("ok") and max_recovery_attempts > 0:
        fallbacks = [t for t in ("cli", "site", "api") if t != project_type]
        for fallback_type in fallbacks[:max_recovery_attempts]:
            retry_build, retry_exec = _build_and_validate(root, f"{topic}-recovery", fallback_type, code_module)
            recovery_chain.append({"fallback_type": fallback_type, "build": retry_build, "execution": retry_exec})
            if retry_build.get("ok") and retry_exec.get("ok"):
                build_payload = retry_build
                execution     = retry_exec
                break

    # 6. Calcular fitness
    fitness = _compute_fitness(build_payload, execution, learning)
    overall_ok = bool(build_payload.get("ok") and execution.get("ok"))

    # 7. Smart Rollback — salva snapshot e verifica degradação
    evolution_applied = False
    rollback_triggered = False
    if HAS_ROLLBACK and _ROLLBACK:
        snap_id = _ROLLBACK.save(
            code=json.dumps(build_payload, ensure_ascii=False),
            fitness=fitness,
            label=f"cycle_{topic[:30]}",
            metadata={"topic": topic, "project_type": project_type},
        )
        if _ROLLBACK.should_rollback(fitness, threshold=0.90):
            rollback_triggered = True
            bus_emit(EventType.ROLLBACK_TRIGGERED, "live_cycle", {"fitness": fitness, "snap_id": snap_id})
            logger.warning("⏪ Rollback ativado — fitness %.1f degradou vs. melhor %.1f", fitness, _ROLLBACK.best_fitness())

    # 8. Evolução paralela — aplica mutações no código do projeto gerado
    if HAS_EVOLUTION and overall_ok and not rollback_triggered:
        main_py = Path(build_payload.get("output_dir", "")) / "main.py"
        if main_py.exists():
            try:
                engine = ParallelEvolutionEngine(population_size=3, workers=2)
                source = main_py.read_text(encoding="utf-8", errors="replace")
                best_code, evo_history = engine.evolve(source, generations=1)
                new_fitness = engine.score_code(best_code)
                if new_fitness > fitness:
                    main_py.write_text(best_code, encoding="utf-8")
                    fitness = new_fitness
                    evolution_applied = True
                    bus_emit(EventType.EVOLUTION_IMPROVED, "live_cycle", {"new_fitness": new_fitness})
                    logger.info("🧬 Evolução paralela melhorou fitness: %.1f", new_fitness)
            except Exception as exc:
                logger.warning("evolução paralela falhou: %s", exc)

    # 9. RLHF — registra feedback por tipo de projeto
    if HAS_RLHF and _RLHF:
        _RLHF.record_feedback(project_type, success=overall_ok, fitness=fitness)
        bus_emit(EventType.RLHF_FEEDBACK, "live_cycle", {
            "type": project_type, "success": overall_ok, "fitness": fitness
        })

    # 10. Meta-learner — registra resultado da mutação
    if HAS_META and _META:
        _META.record_mutation_result(project_type, success=overall_ok, fitness=fitness)

    # 11. Montar payload final
    elapsed = round(time.monotonic() - t0, 2)
    next_action = (
        "Promover baseline e iniciar iteração com testes mais profundos."
        if overall_ok else
        "Ajustar estratégia de geração e repetir ciclo com tópico mais específico."
    )

    payload: dict[str, Any] = {
        "status":           "ok" if overall_ok else "partial",
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "topic":            topic,
        "elapsed_s":        elapsed,
        "fitness":          fitness,
        "evolution_applied":evolution_applied,
        "rollback_triggered": rollback_triggered,
        "learning": {
            "status":               learning.get("status"),
            "confidence":           learning.get("confidence"),
            "weighted_confidence":  learning.get("weighted_confidence"),
            "source_count":         learning.get("source_count"),
            "recommendation":       learning.get("recommendation"),
        },
        "memory_bias": memory_bias,
        "build":       build_payload,
        "execution":   execution,
        "recovery_used":  bool(recovery_chain),
        "recovery_chain": recovery_chain,
        "next_action": next_action,
        "systems": {
            "event_bus":      HAS_BUS,
            "evolution":      HAS_EVOLUTION,
            "rollback":       HAS_ROLLBACK,
            "self_healing":   HAS_HEALING,
            "rlhf":           HAS_RLHF,
            "meta_learner":   HAS_META,
        },
    }

    # 12. Persistência
    memory_entry = {
        "timestamp":  payload["generated_at"],
        "topic":      topic,
        "learning":   payload["learning"],
        "build":      payload["build"],
        "execution":  payload["execution"],
        "status":     payload["status"],
        "fitness":    fitness,
    }
    memory_path = _persist_learning_memory(root, memory_entry)
    json_path, md_path = _save_cycle_artifacts(root, payload)
    payload["memory_path"]   = str(memory_path)
    payload["json_path"]     = str(json_path)
    payload["markdown_path"] = str(md_path)

    bus_emit(
        EventType.CYCLE_END if overall_ok else EventType.CYCLE_FAIL,
        "live_cycle",
        {"topic": topic, "fitness": fitness, "elapsed_s": elapsed},
    )
    logger.info("✅ Ciclo concluído: %s | fitness=%.1f | %.2fs", topic, fitness, elapsed)
    return payload


# ── Multi-ciclo e daemon ──────────────────────────────────────────────────────

def _next_topic(previous_topic: str, cycle_payload: dict[str, Any], step: int) -> str:
    if cycle_payload.get("status") == "ok":
        return f"{previous_topic} optimization cycle {step}"
    rec = str(cycle_payload.get("learning", {}).get("recommendation", "")).strip().lower()
    if "específic" in rec or "specific" in rec:
        return f"{previous_topic} production reliability"
    return f"{previous_topic} resilient architecture"


def run_live_cycles(root: Path, seed_topic: str, iterations: int = 3, strict: bool = False) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations deve ser > 0")
    cycles: list[dict] = []
    topic = seed_topic
    for idx in range(1, iterations + 1):
        cycle_payload = run_live_cycle(root, topic)
        cycle_payload["cycle"] = idx
        cycles.append(cycle_payload)
        topic = _next_topic(topic, cycle_payload, idx + 1)

    ok_count       = sum(1 for c in cycles if c.get("status") == "ok")
    learning_scores= [float(c.get("learning", {}).get("weighted_confidence", 0.0) or 0.0) for c in cycles]
    fitness_scores = [float(c.get("fitness", 0.0)) for c in cycles]
    avg_learning   = round(sum(learning_scores) / max(1, len(learning_scores)), 3)
    avg_fitness    = round(sum(fitness_scores)   / max(1, len(fitness_scores)),  2)
    success_rate   = round(ok_count / len(cycles), 3)
    consistently   = success_rate >= 0.67 and avg_learning >= 0.65

    status = "ok" if consistently else ("fail" if strict else "partial")

    # Relatório de meta-aprendizado ao final do batch
    meta_report = ""
    if HAS_META and _META:
        try:
            meta_report = _META.generate_reflection_report()
        except Exception:
            pass

    summary = {
        "status":                  status,
        "seed_topic":              seed_topic,
        "iterations":              iterations,
        "ok_cycles":               ok_count,
        "success_rate":            success_rate,
        "avg_learning_confidence": avg_learning,
        "avg_fitness":             avg_fitness,
        "consistently_learning":   consistently,
        "meta_report":             meta_report,
    }

    root_evo     = root / "atena_evolution"
    root_reports = root / "analysis_reports"
    root_evo.mkdir(parents=True, exist_ok=True)
    root_reports.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    batch_json = root_evo     / f"digital_organism_live_batch_{ts}.json"
    batch_md   = root_reports / f"ATENA_Organismo_Digital_Live_Batch_{date}.md"
    payload = {"summary": summary, "cycles": cycles}
    batch_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    batch_md.write_text(
        "\n".join([
            f"# ATENA — Live Batch ({date})",
            f"- status={summary['status']}",
            f"- iterations={summary['iterations']}",
            f"- success_rate={summary['success_rate']}",
            f"- avg_fitness={summary['avg_fitness']}",
            f"- consistently_learning={summary['consistently_learning']}",
        ]) + "\n",
        encoding="utf-8",
    )
    summary["batch_json"]     = str(batch_json)
    summary["batch_markdown"] = str(batch_md)
    return payload


def run_live_daemon(
    root: Path,
    seed_topic: str,
    *,
    batches: int = 3,
    iterations_per_batch: int = 3,
    strict: bool = True,
    min_success_rate: float = 0.67,
) -> dict[str, Any]:
    if batches <= 0:
        raise ValueError("batches deve ser > 0")
    history: list[dict] = []
    topic = seed_topic
    for batch_idx in range(1, batches + 1):
        batch_payload = run_live_cycles(root, seed_topic=topic, iterations=iterations_per_batch, strict=strict)
        batch_summary = dict(batch_payload["summary"])
        batch_summary["batch_index"] = batch_idx
        history.append(batch_summary)
        best_cycle = max(
            batch_payload.get("cycles", []),
            key=lambda c: float(c.get("learning", {}).get("weighted_confidence", 0.0) or 0.0),
            default=None,
        )
        if best_cycle:
            topic = _next_topic(str(best_cycle.get("topic", topic)), best_cycle, batch_idx + 1)

    avg_success  = round(sum(float(i.get("success_rate", 0.0)) for i in history) / max(1, len(history)), 3)
    all_consistent = all(bool(i.get("consistently_learning")) for i in history)
    daemon_status  = "ok" if (avg_success >= min_success_rate and all_consistent) else "partial"
    if strict and daemon_status != "ok":
        daemon_status = "fail"

    return {
        "status":                   daemon_status,
        "seed_topic":               seed_topic,
        "final_topic":              topic,
        "batches":                  batches,
        "iterations_per_batch":     iterations_per_batch,
        "avg_success_rate":         avg_success,
        "all_batches_consistently_learning": all_consistent,
        "min_success_rate":         min_success_rate,
        "history":                  history,
    }
