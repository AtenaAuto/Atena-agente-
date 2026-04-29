#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Barramento de Eventos Central
Módulo que conecta todos os sistemas internos da ATENA via pub/sub.
Substitui a comunicação ad-hoc entre módulos por um canal centralizado.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("atena.event_bus")

ROOT    = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "evolution" / "event_bus.db"


# ── Tipos de evento ────────────────────────────────────────────────────────────

class EventType(str, Enum):
    # Ciclo de vida
    CYCLE_START       = "cycle.start"
    CYCLE_END         = "cycle.end"
    CYCLE_FAIL        = "cycle.fail"

    # Evolução
    MUTATION_START    = "mutation.start"
    MUTATION_SUCCESS  = "mutation.success"
    MUTATION_FAIL     = "mutation.fail"
    ROLLBACK_TRIGGERED= "rollback.triggered"
    EVOLUTION_IMPROVED= "evolution.improved"

    # Aprendizado
    LEARNING_ACQUIRED = "learning.acquired"
    MEMORY_UPDATED    = "memory.updated"
    RLHF_FEEDBACK     = "rlhf.feedback"
    META_LEARN_CYCLE  = "meta_learn.cycle"

    # Saúde do sistema
    COMPONENT_HEALTHY = "component.healthy"
    COMPONENT_FAILED  = "component.failed"
    COMPONENT_HEALED  = "component.healed"
    CIRCUIT_OPEN      = "circuit.open"
    CIRCUIT_CLOSED    = "circuit.closed"

    # Internet / APIs
    API_CONNECTED     = "api.connected"
    API_FAILED        = "api.failed"
    API_RATELIMITED   = "api.rate_limited"

    # Projetos
    BUILD_SUCCESS     = "build.success"
    BUILD_FAIL        = "build.fail"
    TEST_PASS         = "test.pass"
    TEST_FAIL         = "test.fail"

    # Genérico
    CUSTOM            = "custom"


@dataclass
class Event:
    type:       EventType
    source:     str                # módulo que emitiu
    payload:    dict[str, Any]     = field(default_factory=dict)
    ts:         float              = field(default_factory=time.time)
    event_id:   Optional[str]     = None

    def __post_init__(self) -> None:
        if self.event_id is None:
            import hashlib
            raw = f"{self.ts}{self.source}{self.type}"
            self.event_id = hashlib.sha1(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value if isinstance(self.type, EventType) else str(self.type)
        return d


# ── Barramento ─────────────────────────────────────────────────────────────────

class AtenaEventBus:
    """
    Barramento de eventos pub/sub thread-safe com persistência opcional.

    Uso:
        bus = get_event_bus()
        bus.subscribe(EventType.MUTATION_SUCCESS, minha_funcao)
        bus.emit(EventType.MUTATION_SUCCESS, "evolution_engine", {"fitness": 82.0})
    """

    def __init__(self, persist: bool = True) -> None:
        self._handlers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._wildcard: list[Callable[[Event], None]] = []  # recebem TODOS os eventos
        self._lock    = threading.Lock()
        self._persist = persist
        self._queue: list[Event] = []
        if persist:
            self._init_db()

    # ── DB ────────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id   TEXT    NOT NULL UNIQUE,
                    ts         REAL    NOT NULL,
                    type       TEXT    NOT NULL,
                    source     TEXT    NOT NULL,
                    payload    TEXT    NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(ts)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _persist_event(self, event: Event) -> None:
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO events (event_id, ts, type, source, payload)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.ts,
                    event.type.value if isinstance(event.type, EventType) else str(event.type),
                    event.source,
                    json.dumps(event.payload, ensure_ascii=False, default=str),
                ))
        except Exception as exc:
            logger.debug("falha ao persistir evento: %s", exc)

    # ── API pública ───────────────────────────────────────────────────────────

    def subscribe(
        self,
        event_type: EventType | str | None,
        handler: Callable[[Event], None],
    ) -> None:
        """
        Registra um handler.
        event_type=None → recebe TODOS os eventos (wildcard).
        """
        with self._lock:
            if event_type is None:
                self._wildcard.append(handler)
            else:
                key = event_type.value if isinstance(event_type, EventType) else str(event_type)
                self._handlers[key].append(handler)

    def unsubscribe(self, event_type: EventType | str | None, handler: Callable) -> bool:
        with self._lock:
            if event_type is None:
                try:
                    self._wildcard.remove(handler)
                    return True
                except ValueError:
                    return False
            key = event_type.value if isinstance(event_type, EventType) else str(event_type)
            lst = self._handlers.get(key, [])
            try:
                lst.remove(handler)
                return True
            except ValueError:
                return False

    def emit(
        self,
        event_type: EventType | str,
        source: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> Event:
        """Emite um evento. Chama handlers síncronos em threads separadas."""
        event = Event(type=event_type, source=source, payload=payload or {})

        if self._persist:
            self._persist_event(event)

        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        with self._lock:
            handlers = list(self._handlers.get(key, [])) + list(self._wildcard)

        for h in handlers:
            threading.Thread(target=self._safe_call, args=(h, event), daemon=True).start()

        logger.debug("📡 %s [%s] → %d handlers", key, source, len(handlers))
        return event

    def _safe_call(self, handler: Callable, event: Event) -> None:
        try:
            handler(event)
        except Exception as exc:
            logger.warning("handler %s falhou para %s: %s", handler.__name__, event.type, exc)

    # ── Consultas ─────────────────────────────────────────────────────────────

    def recent(self, n: int = 50, event_type: Optional[str] = None) -> list[dict]:
        """Retorna os N eventos mais recentes do DB."""
        if not self._persist:
            return []
        try:
            with self._conn() as conn:
                if event_type:
                    rows = conn.execute("""
                        SELECT event_id, ts, type, source, payload
                        FROM events WHERE type = ?
                        ORDER BY ts DESC LIMIT ?
                    """, (event_type, n)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT event_id, ts, type, source, payload
                        FROM events ORDER BY ts DESC LIMIT ?
                    """, (n,)).fetchall()
            return [
                {"event_id": r[0], "ts": r[1], "type": r[2], "source": r[3],
                 "payload": json.loads(r[4])}
                for r in rows
            ]
        except Exception:
            return []

    def stats(self) -> dict:
        """Conta eventos por tipo no DB."""
        if not self._persist:
            return {}
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT type, COUNT(*) FROM events GROUP BY type ORDER BY COUNT(*) DESC"
                ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception:
            return {}


# ── Instância global ──────────────────────────────────────────────────────────

_bus: Optional[AtenaEventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> AtenaEventBus:
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = AtenaEventBus(persist=True)
    return _bus


def emit(event_type: EventType | str, source: str, payload: Optional[dict] = None) -> Event:
    """Atalho global para emitir sem importar o bus inteiro."""
    return get_event_bus().emit(event_type, source, payload)
