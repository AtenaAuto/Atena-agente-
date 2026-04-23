#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mostra status do aprendizado persistido da ATENA (memória episódica)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "atena_brain" / "memory" / "episodic_memory.db"


def main() -> int:
    if not DB.exists():
        print("⚠️ Memória episódica ainda não criada.")
        print(f"Arquivo esperado: {DB}")
        return 1

    conn = sqlite3.connect(DB)
    try:
        total = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
        last = conn.execute(
            "SELECT timestamp, prompt, score, tags FROM experiences ORDER BY id DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    print(f"🧠 Memórias persistidas: {total}")
    for row in last:
        ts, prompt, score, tags = row
        prompt_preview = (prompt or "")[:80].replace("\n", " ")
        print(f"- {ts} | score={score} | tags={tags} | prompt={prompt_preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
