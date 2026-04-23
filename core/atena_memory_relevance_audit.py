#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audita relevância da memória episódica da ATENA."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atena_brain" / "memory" / "episodic_memory.db"


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", (text or "").lower()) if len(t) > 2}


def run_memory_relevance_audit(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {
            "status": "warn",
            "reason": "memory_db_not_found",
            "relevance_avg": 0.0,
            "sample_size": 0,
        }

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT prompt, response, score, tags FROM experiences ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()

    if not rows:
        return {
            "status": "warn",
            "reason": "no_experiences",
            "relevance_avg": 0.0,
            "sample_size": 0,
        }

    relevance_scores = []
    for prompt, response, _score, tags in rows:
        p = _tokenize(prompt)
        r = _tokenize(response)
        t = _tokenize(tags)
        union = max(1, len(p | r | t))
        overlap = len((p & r) | (p & t))
        relevance_scores.append(overlap / union)

    avg = round(sum(relevance_scores) / len(relevance_scores), 4)
    p90 = round(sorted(relevance_scores)[int(0.9 * (len(relevance_scores) - 1))], 4)
    status = "ok" if avg >= 0.12 else "warn"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(rows),
        "relevance_avg": avg,
        "relevance_p90": p90,
        "threshold_avg": 0.12,
        "recommendations": [
            "Aumentar qualidade de tags semânticas por memória",
            "Armazenar embeddings e usar reranking por similaridade",
            "Aplicar pruning de memórias irrelevantes em lote semanal",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Memory Relevance Audit")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--out-dir", default=str(ROOT / "analysis_reports"))
    args = parser.parse_args()

    payload = run_memory_relevance_audit(Path(args.db_path))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "ATENA_Memory_Relevance_Audit.json"
    out_md = out_dir / "ATENA_Memory_Relevance_Audit.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        (
            "# ATENA Memory Relevance Audit\n\n"
            f"- Status: **{payload['status']}**\n"
            f"- Sample size: `{payload['sample_size']}`\n"
            f"- Relevance avg: `{payload['relevance_avg']}`\n"
            f"- Relevance p90: `{payload.get('relevance_p90')}`\n"
        ),
        encoding="utf-8",
    )
    print("🧠 ATENA Memory Relevance Audit")
    print(f"Status: {payload['status']}")
    print(f"JSON: {out_json}")
    print(f"MD: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
