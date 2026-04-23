#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Módulo de memória corporativa + RAG com governança por classificação."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


@dataclass(frozen=True)
class MemoryEntry:
    tenant_id: str
    content: str
    citation: str
    classification: str
    tags: list[str]
    created_at: str


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 2}


class TenantMemoryRAG:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citation TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert(
        self,
        tenant_id: str,
        content: str,
        citation: str,
        classification: str = "internal",
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        created_at = datetime.now(timezone.utc).isoformat()
        tags = tags or []
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory (tenant_id, content, citation, classification, tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, content, citation, classification, json.dumps(tags, ensure_ascii=False), created_at),
            )
            conn.commit()
        return {
            "status": "ok",
            "tenant_id": tenant_id,
            "classification": classification,
            "created_at": created_at,
            "citation": citation,
        }

    def query(
        self,
        tenant_id: str,
        question: str,
        top_k: int = 3,
        classification: str | None = None,
    ) -> dict[str, object]:
        with self._connect() as conn:
            if classification:
                rows = conn.execute(
                    "SELECT content,citation,classification,tags_json,created_at FROM memory WHERE tenant_id=? AND classification=?",
                    (tenant_id, classification),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT content,citation,classification,tags_json,created_at FROM memory WHERE tenant_id=?",
                    (tenant_id,),
                ).fetchall()

        q_tokens = _tokenize(question)
        scored = []
        for content, citation, cls, tags_json, created_at in rows:
            c_tokens = _tokenize(content)
            inter = len(q_tokens & c_tokens)
            union = max(1, len(q_tokens | c_tokens))
            score = inter / union
            scored.append(
                {
                    "score": round(score, 4),
                    "content": content,
                    "citation": citation,
                    "classification": cls,
                    "tags": json.loads(tags_json),
                    "created_at": created_at,
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        selected = scored[:top_k]
        missing_citations = [i for i, item in enumerate(selected) if not item.get("citation")]
        return {
            "status": "ok",
            "tenant_id": tenant_id,
            "question": question,
            "results": selected,
            "citations_required": len(missing_citations) == 0,
            "missing_citation_indexes": missing_citations,
        }

    def purge_expired(self, retention_days: dict[str, int]) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        deleted = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT id,classification,created_at FROM memory").fetchall()
            for row_id, classification, created_at in rows:
                retention = retention_days.get(classification, retention_days.get("default", 90))
                try:
                    created = datetime.fromisoformat(created_at)
                except ValueError:
                    created = now
                if created < now - timedelta(days=retention):
                    conn.execute("DELETE FROM memory WHERE id=?", (row_id,))
                    deleted += 1
            conn.commit()
        return {"status": "ok", "deleted": deleted, "retention_days": retention_days}


def build_reasoning_trace(steps: list[str], citations: list[str]) -> dict[str, object]:
    redacted_steps = [redact_secrets(step) for step in steps]
    missing = [i for i, c in enumerate(citations) if not c]
    return {
        "status": "ok" if not missing else "warn",
        "steps": redacted_steps,
        "citations": citations,
        "citations_required": len(missing) == 0,
        "missing_citation_indexes": missing,
    }
