#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper avançado para executar Hacker Recon com saída estruturada."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = ROOT / "core" / "main.py"
REPORTS_DIR = ROOT / "analysis_reports"


def _build_main_args(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, str(MAIN_SCRIPT), "--recon", args.topic]
    if args.auto:
        cmd.append("--auto")
    if args.cycles is not None:
        cmd.extend(["--cycles", str(args.cycles)])
    if args.deep:
        cmd.append("--deep")
    if args.checker:
        cmd.append("--checker")
    return cmd


def _load_topics(primary_topic: str | None, batch_file: str | None) -> list[str]:
    topics: list[str] = []
    if primary_topic:
        cleaned = primary_topic.strip()
        if cleaned:
            topics.append(cleaned)
    if batch_file:
        p = Path(batch_file)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"Arquivo de tópicos não encontrado: {p}")
        file_topics = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        topics.extend(file_topics)
    # dedup preservando ordem
    seen = set()
    deduped: list[str] = []
    for topic in topics:
        if topic not in seen:
            deduped.append(topic)
            seen.add(topic)
    return deduped


def _resolve_path(path_value: str) -> Path:
    p = Path(path_value)
    if not p.is_absolute():
        p = ROOT / p
    return p


def _load_history_scores(history_path: Path) -> dict[str, float]:
    if not history_path.exists():
        return {}
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    entries = data.get("entries", [])
    by_topic: dict[str, list[int]] = {}
    for entry in entries:
        topic = entry.get("topic")
        score = entry.get("recon_score")
        if not isinstance(topic, str) or not isinstance(score, (int, float)):
            continue
        by_topic.setdefault(topic, []).append(int(score))
    return {topic: sum(scores) / len(scores) for topic, scores in by_topic.items() if scores}


def _append_history(history_path: Path, results: list[dict[str, Any]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {"entries": []}
    if history_path.exists():
        try:
            existing = json.loads(history_path.read_text(encoding="utf-8"))
            if "entries" not in existing or not isinstance(existing["entries"], list):
                existing = {"entries": []}
        except json.JSONDecodeError:
            existing = {"entries": []}

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for r in results:
        existing["entries"].append(
            {
                "timestamp_utc": now,
                "topic": r["topic"],
                "recon_score": r["recon_score"],
                "ok": r["ok"],
                "duration_s": r["duration_s"],
            }
        )
    # mantém histórico compacto (últimas 1000 execuções)
    existing["entries"] = existing["entries"][-1000:]
    history_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(cmd: list[str], rc: int, output: str, topic: str, duration_s: float, recon_score: int, timed_out: bool) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    report = REPORTS_DIR / f"HACKER_RECON_{ts}.md"
    tail = "\n".join(output.strip().splitlines()[-40:]) if output.strip() else "(sem saída capturada)"
    report.write_text(
        "\n".join(
            [
                "# ATENA Hacker Recon Report",
                "",
                f"- Timestamp (UTC): {dt.datetime.now(dt.timezone.utc).isoformat()}",
                f"- Topic: `{topic}`",
                f"- Exit code: `{rc}`",
                f"- Duration (s): `{duration_s}`",
                f"- Timed out: `{timed_out}`",
                f"- Recon score: `{recon_score}/100`",
                f"- Command: `{' '.join(cmd)}`",
                "",
                "## Output (tail)",
                "```text",
                tail,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report


def _compute_recon_score(output: str, rc: int) -> int:
    """Score simples (0-100) para sinalizar qualidade da execução de recon."""
    score = 0
    if rc == 0:
        score += 40
    lowered = output.lower()
    if "recon:" in lowered:
        score += 20
    if "dashboard dispon" in lowered:
        score += 10
    if "modelo de embedding carregado" in lowered:
        score += 10
    if "error" not in lowered and "traceback" not in lowered:
        score += 20
    return max(0, min(100, score))


def _run_single_topic(base_args: argparse.Namespace, topic: str) -> dict[str, Any]:
    local_args = argparse.Namespace(**vars(base_args))
    local_args.topic = topic
    cmd = _build_main_args(local_args)
    attempts = 0
    proc: subprocess.CompletedProcess[str] | None = None
    timed_out = False
    started = time.time()
    max_attempts = max(1, int(base_args.retries) + 1)
    while attempts < max_attempts:
        attempts += 1
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=base_args.timeout)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(exc.cmd, returncode=124, stdout=exc.stdout or "", stderr=(exc.stderr or "") + "\nTimeout excedido.")
            timed_out = True
        if proc.returncode == 0:
            break
    elapsed_s = round(time.time() - started, 3)
    assert proc is not None
    output = f"{proc.stdout}\n{proc.stderr}"
    recon_score = _compute_recon_score(output, proc.returncode)
    return {
        "topic": topic,
        "command": cmd,
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "timed_out": timed_out,
        "duration_s": elapsed_s,
        "recon_score": recon_score,
        "attempts": attempts,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output": output,
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Executa o Hacker Recon da ATENA com opções avançadas.")
    parser.add_argument("--topic", default=None, help="Tópico para o recon.")
    parser.add_argument("--batch-file", default=None, help="Arquivo TXT com tópicos (um por linha).")
    parser.add_argument("--auto", action="store_true", help="Ativa modo autônomo no core.")
    parser.add_argument("--cycles", type=int, default=None, help="Número de ciclos quando --auto estiver ativo.")
    parser.add_argument("--deep", action="store_true", help="Ativa self-mod profundo no core.")
    parser.add_argument("--checker", action="store_true", help="Ativa checker evolve no core.")
    parser.add_argument("--json", action="store_true", help="Exibe resumo final em JSON.")
    parser.add_argument("--output-json", default=None, help="Salva resumo JSON em arquivo.")
    parser.add_argument("--no-report", action="store_true", help="Não salvar relatório em analysis_reports/.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout máximo da execução em segundos.")
    parser.add_argument("--stop-on-fail", action="store_true", help="Interrompe o batch no primeiro erro.")
    parser.add_argument("--history-json", default="analysis_reports/hacker_recon_history.json", help="Arquivo JSON para histórico de score.")
    parser.add_argument("--prioritize-history", action="store_true", help="No batch, ordena tópicos por score histórico (maior para menor).")
    parser.add_argument("--parallel", type=int, default=1, help="Executa batch em paralelo (>=1).")
    parser.add_argument("--retries", type=int, default=0, help="Tentativas extras por tópico em caso de falha.")
    args = parser.parse_args(argv)
    topics = _load_topics(args.topic, args.batch_file)
    if not topics:
        print("❌ Informe --topic ou --batch-file com pelo menos um tópico.")
        return 2
    history_path = _resolve_path(args.history_json)
    if args.prioritize_history and len(topics) > 1:
        history_scores = _load_history_scores(history_path)
        topics = sorted(topics, key=lambda t: history_scores.get(t, -1), reverse=True)

    results: list[dict[str, Any]] = []
    parallel = max(1, int(args.parallel))
    if parallel == 1 or len(topics) == 1 or args.stop_on_fail:
        for topic in topics:
            result = _run_single_topic(args, topic)
            results.append(result)

            if result["stdout"]:
                print(result["stdout"], end="")
            if result["stderr"]:
                print(result["stderr"], end="", file=sys.stderr)

            if args.stop_on_fail and not result["ok"]:
                break
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            future_map = {pool.submit(_run_single_topic, args, topic): topic for topic in topics}
            for future in as_completed(future_map):
                result = future.result()
                results.append(result)
                if result["stdout"]:
                    print(result["stdout"], end="")
                if result["stderr"]:
                    print(result["stderr"], end="", file=sys.stderr)
        # mantém ordem estável da entrada para facilitar leitura de relatório
        pos = {topic: i for i, topic in enumerate(topics)}
        results.sort(key=lambda r: pos.get(r["topic"], 999999))

    report_paths: list[str] = []
    if not args.no_report:
        for result in results:
            report_path = _write_report(
                result["command"],
                result["exit_code"],
                result["output"],
                result["topic"],
                result["duration_s"],
                result["recon_score"],
                result["timed_out"],
            )
            try:
                report_label = str(report_path.relative_to(ROOT))
            except ValueError:
                report_label = str(report_path)
            report_paths.append(report_label)
            print(f"📝 Relatório salvo em: {report_label}")

    success_count = sum(1 for r in results if r["ok"])
    summary = {
        "ok": success_count == len(results),
        "topics_total": len(results),
        "topics_ok": success_count,
        "topics_failed": len(results) - success_count,
        "best_topic": max(results, key=lambda r: r["recon_score"])["topic"] if results else None,
        "results": [
            {
                "topic": r["topic"],
                "ok": r["ok"],
                "exit_code": r["exit_code"],
                "timed_out": r["timed_out"],
                "duration_s": r["duration_s"],
                "recon_score": r["recon_score"],
                "attempts": r["attempts"],
                "command": r["command"],
            }
            for r in results
        ],
        "report_paths": report_paths,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    _append_history(history_path, results)
    summary["history_path"] = str(history_path)

    if args.output_json:
        output_json_path = _resolve_path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"🧾 JSON salvo em: {output_json_path}")

    # mantém compatibilidade: retorno 0 apenas se todas execuções passaram.
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
