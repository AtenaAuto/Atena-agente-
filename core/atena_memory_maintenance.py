#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manutenção de memória episódica: pruning de memórias irrelevantes."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atena_brain" / "memory" / "episodic_memory.db"


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", (text or "").lower()) if len(t) > 2}


def _parse_dt(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def run_memory_maintenance(db_path: Path, relevance_threshold: float = 0.05, min_age_days: int = 7) -> dict[str, object]:
    if not db_path.exists():
        return {"status": "warn", "reason": "memory_db_not_found", "deleted": 0, "total": 0}

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, timestamp, prompt, response, tags FROM experiences").fetchall()
    now = datetime.now(timezone.utc)
    delete_ids: list[int] = []

    for row_id, timestamp, prompt, response, tags in rows:
        p = _tokenize(prompt)
        r = _tokenize(response)
        t = _tokenize(tags)
        union = max(1, len(p | r | t))
        overlap = len((p & r) | (p & t))
        relevance = overlap / union

        dt = _parse_dt(str(timestamp))
        old_enough = False
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            old_enough = dt < (now - timedelta(days=min_age_days))

        if relevance < relevance_threshold and old_enough:
            delete_ids.append(int(row_id))

    for row_id in delete_ids:
        conn.execute("DELETE FROM experiences WHERE id=?", (row_id,))
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "total": len(rows),
        "deleted": len(delete_ids),
        "kept": max(0, len(rows) - len(delete_ids)),
        "relevance_threshold": relevance_threshold,
        "min_age_days": min_age_days,
        "timestamp": now.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Memory Maintenance")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--relevance-threshold", type=float, default=0.05)
    parser.add_argument("--min-age-days", type=int, default=7)
    parser.add_argument("--out-dir", default=str(ROOT / "analysis_reports"))
    args = parser.parse_args()

    payload = run_memory_maintenance(
        Path(args.db_path),
        relevance_threshold=args.relevance_threshold,
        min_age_days=args.min_age_days,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "ATENA_Memory_Maintenance.json"
    out_md = out_dir / "ATENA_Memory_Maintenance.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        (
            "# ATENA Memory Maintenance\n\n"
            f"- Status: **{payload['status']}**\n"
            f"- Total: `{payload['total']}`\n"
            f"- Deleted: `{payload['deleted']}`\n"
            f"- Kept: `{payload['kept']}`\n"
            f"- Threshold: `{payload['relevance_threshold']}`\n"
        ),
        encoding="utf-8",
    )
    print("🧹 ATENA Memory Maintenance")
    print(f"Deleted: {payload['deleted']} / {payload['total']}")
    print(f"JSON: {out_json}")
    print(f"MD: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
