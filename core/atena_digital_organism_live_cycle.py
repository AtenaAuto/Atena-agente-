#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ciclo vivo de organismo digital: aprende da internet -> cria -> executa -> testa."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.internet_challenge import run_internet_challenge
from modules.atena_code_module import AtenaCodeModule


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    safe = re.sub(r"[^a-z0-9_-]+", "-", lowered)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe or "atena-project"


def _safe_project_name(topic: str, max_slug_len: int = 80) -> str:
    slug = _slugify(topic)
    if len(slug) > max_slug_len:
        slug = slug[:max_slug_len].rstrip("-")
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    return f"{slug}-{ts}"


def _memory_success_bias(root: Path) -> dict[str, float]:
    memory_path = root / "atena_evolution" / "digital_organism_memory.jsonl"
    if not memory_path.exists():
        return {}

    stats: dict[str, dict[str, float]] = {}
    for raw in memory_path.read_text(encoding="utf-8").splitlines():
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

    bias: dict[str, float] = {}
    for ptype, bucket in stats.items():
        total = bucket["total"]
        if total > 0:
            bias[ptype] = round(bucket["ok"] / total, 3)
    return bias


def _pick_project_type(learning_payload: dict[str, Any], memory_bias: dict[str, float] | None = None) -> str:
    sources = {item.get("source"): item for item in learning_payload.get("sources", [])}
    weighted_conf = float(learning_payload.get("weighted_confidence", 0.0))

    npm_q = float(sources.get("npm", {}).get("quality_score", 0.0))
    gh_q = float(sources.get("github", {}).get("quality_score", 0.0))

    if weighted_conf >= 0.70 and (npm_q >= 0.70 or gh_q >= 0.70):
        base = "api"
    elif weighted_conf >= 0.60:
        base = "site"
    else:
        base = "cli"

    # Ajuste inteligente com memória histórica (evita repetir tipo com baixa taxa de sucesso).
    memory_bias = memory_bias or {}
    if not memory_bias:
        return base

    best = max(memory_bias.items(), key=lambda kv: kv[1])[0]
    best_rate = float(memory_bias.get(best, 0.0))
    base_rate = float(memory_bias.get(base, 0.0))
    if best_rate - base_rate >= 0.20:
        return best
    return base


def _validate_execution(project_type: str, project_dir: Path) -> dict[str, Any]:
    if project_type == "site":
        index = project_dir / "index.html"
        if not index.exists():
            return {"ok": False, "reason": "index.html ausente"}
        content = index.read_text(encoding="utf-8")
        ok = "<html" in content.lower() and len(content) > 200
        return {"ok": ok, "reason": "estrutura html validada" if ok else "html inválido"}

    main_py = project_dir / "main.py"
    if not main_py.exists():
        return {"ok": False, "reason": "main.py ausente"}

    compile_proc = subprocess.run(
        ["python3", "-m", "py_compile", str(main_py)],
        capture_output=True,
        text=True,
        check=False,
    )
    if compile_proc.returncode != 0:
        return {"ok": False, "reason": "py_compile falhou", "stderr": compile_proc.stderr[-400:]}

    if project_type == "api":
        content = main_py.read_text(encoding="utf-8")
        ok = "@app.get('/health')" in content and "@app.get('/idea')" in content
        return {"ok": ok, "reason": "endpoints health/idea presentes" if ok else "endpoints ausentes"}

    run_proc = subprocess.run(
        ["python3", str(main_py), "ATENA"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    ok = run_proc.returncode == 0 and "ATENA" in (run_proc.stdout or "")
    return {
        "ok": ok,
        "reason": "CLI executada com sucesso" if ok else "CLI falhou",
        "stdout_tail": (run_proc.stdout or "")[-300:],
        "stderr_tail": (run_proc.stderr or "")[-300:],
    }


def _persist_learning_memory(root: Path, entry: dict[str, Any]) -> Path:
    evo = root / "atena_evolution"
    evo.mkdir(parents=True, exist_ok=True)
    memory_path = evo / "digital_organism_memory.jsonl"
    with memory_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return memory_path


def _save_cycle_artifacts(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evo = root / "atena_evolution"
    reports = root / "analysis_reports"
    evo.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    json_path = evo / f"digital_organism_live_cycle_{ts}.json"
    md_path = reports / f"ATENA_Organismo_Digital_Live_Cycle_{date}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# ATENA — Live Cycle de Organismo Digital ({date})",
        "",
        f"- Tópico: **{payload['topic']}**",
        f"- Status geral: **{payload['status']}**",
        f"- Projeto criado: **{payload['build']['project_type']} / {payload['build']['project_name']}**",
        f"- Execução/Teste: **{'ok' if payload['execution']['ok'] else 'fail'}**",
        "",
        "## Aprendizado da internet",
        f"- confidence={payload['learning']['confidence']}",
        f"- weighted_confidence={payload['learning']['weighted_confidence']}",
        f"- source_count={payload['learning']['source_count']}",
        "",
        "## Próxima ação autônoma",
        f"- {payload['next_action']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _build_and_validate(
    root: Path,
    topic: str,
    project_type: str,
    code_module: AtenaCodeModule,
) -> tuple[dict[str, Any], dict[str, Any]]:
    project_name = _safe_project_name(topic)
    build = code_module.build(project_type=project_type, project_name=project_name)
    build_payload = {
        "ok": build.ok,
        "project_type": build.project_type,
        "project_name": build.project_name,
        "output_dir": build.output_dir,
        "message": build.message,
    }
    execution = {"ok": False, "reason": "build_failed"}
    if build.ok:
        execution = _validate_execution(build.project_type, Path(build.output_dir))
    return build_payload, execution


def run_live_cycle(root: Path, topic: str, max_recovery_attempts: int = 1) -> dict[str, Any]:
    learning = run_internet_challenge(topic)
    memory_bias = _memory_success_bias(root)
    project_type = _pick_project_type(learning, memory_bias=memory_bias)

    code_module = AtenaCodeModule(root)
    build_payload, execution = _build_and_validate(root, topic, project_type, code_module)
    recovery_chain: list[dict[str, Any]] = []

    if (not execution.get("ok")) and max_recovery_attempts > 0:
        fallback_order = [ptype for ptype in ("cli", "site", "api") if ptype != project_type]
        for fallback_type in fallback_order[:max_recovery_attempts]:
            retry_build, retry_exec = _build_and_validate(root, f"{topic}-recovery", fallback_type, code_module)
            recovery_chain.append(
                {
                    "fallback_type": fallback_type,
                    "build": retry_build,
                    "execution": retry_exec,
                }
            )
            if retry_build.get("ok") and retry_exec.get("ok"):
                build_payload = retry_build
                execution = retry_exec
                break

    overall_ok = bool(build_payload.get("ok") and execution.get("ok"))
    next_action = (
        "Promover baseline e iniciar iteração com testes mais profundos."
        if overall_ok
        else "Ajustar estratégia de geração e repetir ciclo com tópico mais específico."
    )

    payload = {
        "status": "ok" if overall_ok else "partial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "learning": {
            "status": learning.get("status"),
            "confidence": learning.get("confidence"),
            "weighted_confidence": learning.get("weighted_confidence"),
            "source_count": learning.get("source_count"),
            "recommendation": learning.get("recommendation"),
        },
        "memory_bias": memory_bias,
        "build": build_payload,
        "execution": execution,
        "recovery_used": bool(recovery_chain),
        "recovery_chain": recovery_chain,
        "next_action": next_action,
    }

    memory_entry = {
        "timestamp": payload["generated_at"],
        "topic": topic,
        "learning": payload["learning"],
        "build": payload["build"],
        "execution": payload["execution"],
        "status": payload["status"],
    }
    memory_path = _persist_learning_memory(root, memory_entry)
    json_path, md_path = _save_cycle_artifacts(root, payload)

    payload["memory_path"] = str(memory_path)
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return payload


def _next_topic(previous_topic: str, cycle_payload: dict[str, Any], step: int) -> str:
    if cycle_payload.get("status") == "ok":
        return f"{previous_topic} optimization cycle {step}"
    recommendation = str(cycle_payload.get("learning", {}).get("recommendation", "")).strip().lower()
    if "específicos" in recommendation or "specific" in recommendation:
        return f"{previous_topic} production reliability"
    return f"{previous_topic} resilient architecture"


def run_live_cycles(root: Path, seed_topic: str, iterations: int = 3, strict: bool = False) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations deve ser > 0")

    cycles: list[dict[str, Any]] = []
    topic = seed_topic
    for idx in range(1, iterations + 1):
        cycle_payload = run_live_cycle(root, topic)
        cycle_payload["cycle"] = idx
        cycles.append(cycle_payload)
        topic = _next_topic(topic, cycle_payload, idx + 1)

    ok_count = sum(1 for c in cycles if c.get("status") == "ok")
    learning_scores = [float(c.get("learning", {}).get("weighted_confidence", 0.0) or 0.0) for c in cycles]
    avg_learning = round(sum(learning_scores) / max(1, len(learning_scores)), 3)
    success_rate = round(ok_count / len(cycles), 3)
    consistently_learning = success_rate >= 0.67 and avg_learning >= 0.65

    status = "ok" if consistently_learning else "partial"
    if strict and not consistently_learning:
        status = "fail"

    summary = {
        "status": status,
        "seed_topic": seed_topic,
        "iterations": iterations,
        "ok_cycles": ok_count,
        "success_rate": success_rate,
        "avg_learning_confidence": avg_learning,
        "consistently_learning": consistently_learning,
    }

    root_evo = root / "atena_evolution"
    root_reports = root / "analysis_reports"
    root_evo.mkdir(parents=True, exist_ok=True)
    root_reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    batch_json = root_evo / f"digital_organism_live_batch_{ts}.json"
    batch_md = root_reports / f"ATENA_Organismo_Digital_Live_Batch_{date}.md"
    payload = {"summary": summary, "cycles": cycles}
    batch_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    batch_md.write_text(
        "\n".join(
            [
                f"# ATENA — Live Batch de Organismo Digital ({date})",
                "",
                f"- status={summary['status']}",
                f"- iterations={summary['iterations']}",
                f"- success_rate={summary['success_rate']}",
                f"- avg_learning_confidence={summary['avg_learning_confidence']}",
                f"- consistently_learning={summary['consistently_learning']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary["batch_json"] = str(batch_json)
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
    if iterations_per_batch <= 0:
        raise ValueError("iterations_per_batch deve ser > 0")

    history: list[dict[str, Any]] = []
    topic = seed_topic
    for batch_idx in range(1, batches + 1):
        batch_payload = run_live_cycles(
            root,
            seed_topic=topic,
            iterations=iterations_per_batch,
            strict=strict,
        )
        batch_summary = dict(batch_payload["summary"])
        batch_summary["batch_index"] = batch_idx
        history.append(batch_summary)

        # Próximo tópico guiado pelos ciclos mais bem-sucedidos.
        best_cycle = None
        for cycle in batch_payload.get("cycles", []):
            if not best_cycle:
                best_cycle = cycle
                continue
            best_conf = float(best_cycle.get("learning", {}).get("weighted_confidence", 0.0) or 0.0)
            cur_conf = float(cycle.get("learning", {}).get("weighted_confidence", 0.0) or 0.0)
            if cur_conf > best_conf:
                best_cycle = cycle
        if best_cycle:
            topic = _next_topic(str(best_cycle.get("topic", topic)), best_cycle, batch_idx + 1)

    avg_success = round(
        sum(float(item.get("success_rate", 0.0) or 0.0) for item in history) / max(1, len(history)),
        3,
    )
    all_consistent = all(bool(item.get("consistently_learning", False)) for item in history)
    daemon_status = "ok" if (avg_success >= min_success_rate and all_consistent) else "partial"
    if strict and daemon_status != "ok":
        daemon_status = "fail"

    summary = {
        "status": daemon_status,
        "seed_topic": seed_topic,
        "final_topic": topic,
        "batches": batches,
        "iterations_per_batch": iterations_per_batch,
        "avg_success_rate": avg_success,
        "all_batches_consistently_learning": all_consistent,
        "min_success_rate": min_success_rate,
    }

    root_evo = root / "atena_evolution"
    root_reports = root / "analysis_reports"
    root_evo.mkdir(parents=True, exist_ok=True)
    root_reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daemon_json = root_evo / f"digital_organism_daemon_{ts}.json"
    daemon_md = root_reports / f"ATENA_Organismo_Digital_Daemon_{date}.md"
    payload = {"summary": summary, "batches": history}
    daemon_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    daemon_md.write_text(
        "\n".join(
            [
                f"# ATENA — Daemon de Organismo Digital ({date})",
                "",
                f"- status={summary['status']}",
                f"- batches={summary['batches']}",
                f"- iterations_per_batch={summary['iterations_per_batch']}",
                f"- avg_success_rate={summary['avg_success_rate']}",
                f"- all_batches_consistently_learning={summary['all_batches_consistently_learning']}",
                f"- final_topic={summary['final_topic']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary["daemon_json"] = str(daemon_json)
    summary["daemon_markdown"] = str(daemon_md)
    return payload
