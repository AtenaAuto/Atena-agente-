from __future__ import annotations

import core.main as main_mod


def test_save_intelligence_snapshot_persists_row(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "knowledge.db"
    monkeypatch.setattr(main_mod.Config, "KNOWLEDGE_DB", db_path)

    kb = main_mod.KnowledgeBase()
    try:
        kb.save_intelligence_snapshot(
            generation=7,
            best_score=71.5,
            score_delta=0.2,
            stagnation_cycles=2,
            adaptive_delta=0.01,
            replaced=True,
        )
        row = kb.conn.execute(
            """
            SELECT generation, best_score, score_delta, stagnation_cycles,
                   adaptive_delta, replaced
            FROM intelligence_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        kb.close()

    assert row is not None
    assert row[0] == 7
    assert row[1] == 71.5
    assert row[2] == 0.2
    assert row[3] == 2
    assert row[4] == 0.01
    assert row[5] == 1


def test_intelligence_snapshot_table_exists(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "knowledge.db"
    monkeypatch.setattr(main_mod.Config, "KNOWLEDGE_DB", db_path)

    kb = main_mod.KnowledgeBase()
    try:
        exists = kb.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_snapshots'"
        ).fetchone()
    finally:
        kb.close()

    assert exists is not None
