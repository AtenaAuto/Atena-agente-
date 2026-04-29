#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Rollback Inteligente
Mantém histórico de estados do código com métricas de performance.
Faz rollback automático quando uma mutação degrada o sistema.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("atena.smart_rollback")

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "evolution" / "snapshots"
MAX_SNAPSHOTS = int(__import__("os").getenv("ATENA_MAX_SNAPSHOTS", "20"))


@dataclass
class Snapshot:
    snapshot_id: str
    timestamp: float
    code_hash: str
    code: str
    fitness: float
    label: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("code")  # não serializar código completo no índice
        return d


class SmartRollbackManager:
    """
    Gerencia snapshots de código com histórico de fitness.
    Permite rollback automático ou manual para o melhor estado anterior.

    Fluxo típico:
        mgr = SmartRollbackManager()
        snap_id = mgr.save(current_code, fitness=72.5, label="pre-mutation-gen3")
        # ... aplica mutação ...
        new_fitness = evaluate(new_code)
        if new_fitness < mgr.best_fitness() * 0.95:  # degradou >5%
            code = mgr.rollback_to_best()
    """

    def __init__(self, max_snapshots: int = MAX_SNAPSHOTS):
        self.max_snapshots = max_snapshots
        self._snapshots: deque[Snapshot] = deque(maxlen=max_snapshots)
        self._lock = threading.Lock()
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._load_index()

    # ── API pública ─────────────────────────────────────────────────────────

    def save(self, code: str, fitness: float, label: str = "", metadata: dict | None = None) -> str:
        """Salva um snapshot. Retorna o snapshot_id."""
        snap_id = self._make_id(code)
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        snap = Snapshot(
            snapshot_id=snap_id,
            timestamp=time.time(),
            code_hash=code_hash,
            code=code,
            fitness=fitness,
            label=label or f"snap_{snap_id[:6]}",
            metadata=metadata or {},
        )
        with self._lock:
            self._snapshots.append(snap)
            self._persist(snap)
        logger.debug("💾 snapshot salvo: %s fitness=%.1f", snap_id[:8], fitness)
        return snap_id

    def best(self) -> Optional[Snapshot]:
        """Retorna o snapshot com maior fitness."""
        with self._lock:
            if not self._snapshots:
                return None
            return max(self._snapshots, key=lambda s: s.fitness)

    def best_fitness(self) -> float:
        snap = self.best()
        return snap.fitness if snap else 0.0

    def latest(self) -> Optional[Snapshot]:
        """Retorna o snapshot mais recente."""
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def rollback_to_best(self) -> Optional[str]:
        """Carrega o código do melhor snapshot. Retorna o código ou None."""
        snap = self.best()
        if snap is None:
            logger.warning("rollback: nenhum snapshot disponível")
            return None
        logger.info("⏪ rollback → %s (fitness=%.1f)", snap.label, snap.fitness)
        return snap.code

    def rollback_to(self, snapshot_id: str) -> Optional[str]:
        """Rollback para um snapshot específico pelo ID."""
        with self._lock:
            for snap in self._snapshots:
                if snap.snapshot_id.startswith(snapshot_id):
                    logger.info("⏪ rollback → %s (fitness=%.1f)", snap.label, snap.fitness)
                    return snap.code
        # Tenta carregar do disco
        return self._load_code(snapshot_id)

    def should_rollback(self, new_fitness: float, threshold: float = 0.95) -> bool:
        """Retorna True se new_fitness degradou mais que threshold vs. melhor."""
        best = self.best_fitness()
        if best <= 0:
            return False
        result = new_fitness < best * threshold
        if result:
            logger.warning(
                "🚨 degradação detectada: %.1f < %.1f * %.2f — rollback recomendado",
                new_fitness, best, threshold,
            )
        return result

    def history(self, n: int = 10) -> list[dict]:
        """Retorna os últimos N snapshots (sem o código completo)."""
        with self._lock:
            snaps = list(self._snapshots)[-n:]
        return [s.to_dict() for s in snaps]

    def fitness_trend(self) -> str:
        """Retorna 'melhora', 'estavel' ou 'piora' com base nos últimos 5 snapshots."""
        with self._lock:
            recent = list(self._snapshots)[-5:]
        if len(recent) < 2:
            return "sem_dados"
        fitnesses = [s.fitness for s in recent]
        delta = fitnesses[-1] - fitnesses[0]
        if delta > 2:
            return "melhora"
        elif delta < -2:
            return "piora"
        return "estavel"

    def purge_old(self, keep: int = 5) -> int:
        """Remove snapshots antigos mantendo os `keep` melhores."""
        with self._lock:
            if len(self._snapshots) <= keep:
                return 0
            sorted_snaps = sorted(self._snapshots, key=lambda s: s.fitness, reverse=True)
            to_keep = set(s.snapshot_id for s in sorted_snaps[:keep])
            old = [s for s in self._snapshots if s.snapshot_id not in to_keep]
            for s in old:
                self._delete_snapshot(s.snapshot_id)
            self._snapshots = deque(
                [s for s in self._snapshots if s.snapshot_id in to_keep],
                maxlen=self.max_snapshots,
            )
        logger.info("🧹 purge: %d snapshots antigos removidos", len(old))
        return len(old)

    # ── Persistência ────────────────────────────────────────────────────────

    def _make_id(self, code: str) -> str:
        return hashlib.sha256(f"{time.time()}{code[:100]}".encode()).hexdigest()[:20]

    def _persist(self, snap: Snapshot) -> None:
        code_file = SNAPSHOT_DIR / f"{snap.snapshot_id}.py"
        meta_file = SNAPSHOT_DIR / f"{snap.snapshot_id}.json"
        try:
            code_file.write_text(snap.code, encoding="utf-8")
            meta_file.write_text(json.dumps(snap.to_dict(), ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            logger.warning("falha ao salvar snapshot: %s", e)

    def _load_index(self) -> None:
        """Carrega metadados dos snapshots existentes no disco."""
        try:
            for meta_file in sorted(SNAPSHOT_DIR.glob("*.json"))[-self.max_snapshots:]:
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    code_file = meta_file.with_suffix(".py")
                    code = code_file.read_text(encoding="utf-8") if code_file.exists() else ""
                    self._snapshots.append(Snapshot(
                        snapshot_id=meta["snapshot_id"],
                        timestamp=meta.get("timestamp", 0),
                        code_hash=meta.get("code_hash", ""),
                        code=code,
                        fitness=meta.get("fitness", 0.0),
                        label=meta.get("label", ""),
                        metadata=meta.get("metadata", {}),
                    ))
                except Exception as e:
                    logger.debug("falha ao carregar snapshot %s: %s", meta_file.name, e)
        except OSError:
            pass

    def _load_code(self, snapshot_id: str) -> Optional[str]:
        code_file = SNAPSHOT_DIR / f"{snapshot_id}.py"
        if code_file.exists():
            return code_file.read_text(encoding="utf-8")
        return None

    def _delete_snapshot(self, snapshot_id: str) -> None:
        for ext in (".py", ".json"):
            f = SNAPSHOT_DIR / f"{snapshot_id}{ext}"
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
