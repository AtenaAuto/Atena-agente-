from __future__ import annotations

import sqlite3
from pathlib import Path

from core.atena_memory_relevance_audit import run_memory_relevance_audit


def _build_db(db_path: Path) -> None:
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
        ("2026-01-01T00:00:00Z", "melhorar memória da atena", "plano para melhorar memória da atena", 1.0, "memory,atena"),
    )
    conn.commit()
    conn.close()


def test_memory_relevance_audit_warn_when_db_missing(tmp_path: Path):
    payload = run_memory_relevance_audit(tmp_path / "missing.db")
    assert payload["status"] == "warn"
    assert payload["sample_size"] == 0


def test_memory_relevance_audit_ok_with_relevant_samples(tmp_path: Path):
    db = tmp_path / "episodic_memory.db"
    _build_db(db)
    payload = run_memory_relevance_audit(db)
    assert payload["sample_size"] == 1
    assert payload["relevance_avg"] > 0
