from __future__ import annotations

import sqlite3

from modules.curiosity_engine import CuriosityEngine


def test_generate_contextual_topics_creates_advanced_variants(tmp_path) -> None:
    engine = CuriosityEngine(db_path=str(tmp_path / "knowledge.db"))

    topics = engine._generate_contextual_topics(["telemetry", "vectorstore", "x", "k8s123"])

    assert topics
    assert "telemetry optimization" in topics
    assert "vectorstore for autonomous agents" in topics
    assert all("k8s123" not in topic for topic in topics)


def test_get_next_topic_accepts_context_terms(tmp_path, monkeypatch) -> None:
    engine = CuriosityEngine(db_path=str(tmp_path / "knowledge.db"))
    # força ramo de exploração aleatória
    monkeypatch.setattr("modules.curiosity_engine.random.random", lambda: 0.1)
    monkeypatch.setattr("modules.curiosity_engine.random.choice", lambda seq: seq[-1])

    topic = engine.get_next_topic(context_terms=["telemetry"])

    assert isinstance(topic, str)
    assert topic
    assert "telemetry" in topic or topic in engine.base_topics


def test_init_db_recovers_from_corrupted_sqlite_file(tmp_path) -> None:
    db_path = tmp_path / "knowledge.db"
    db_path.write_bytes(b"not-a-valid-sqlite-db")

    engine = CuriosityEngine(db_path=str(db_path))

    backup = tmp_path / "knowledge.db.corrupted"
    assert backup.exists()
    assert db_path.exists()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='curiosity_topics'")
    assert cur.fetchone() is not None
    conn.close()
    assert engine.db_path == str(db_path)
