from __future__ import annotations

import sqlite3
from pathlib import Path

from core.atena_memory_maintenance import run_memory_maintenance


def _seed(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            prompt TEXT,
            response TEXT,
            score FLOAT,
            tags TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO experiences (timestamp, prompt, response, score, tags) VALUES (?, ?, ?, ?, ?)",
        ("2025-01-01T00:00:00+00:00", "abc", "xyz", 1.0, "none"),
    )
    conn.execute(
        "INSERT INTO experiences (timestamp, prompt, response, score, tags) VALUES (?, ?, ?, ?, ?)",
        ("2026-04-18T00:00:00+00:00", "melhorar memoria atena", "plano memoria atena", 1.0, "memory"),
    )
    conn.commit()
    conn.close()


def test_memory_maintenance_deletes_old_irrelevant_rows(tmp_path: Path):
    db = tmp_path / "episodic_memory.db"
    _seed(db)

    payload = run_memory_maintenance(db, relevance_threshold=0.1, min_age_days=30)

    assert payload["status"] == "ok"
    assert payload["deleted"] >= 1
    assert payload["total"] == 2
