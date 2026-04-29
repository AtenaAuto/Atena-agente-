#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Self-Healing Real
Substitui a versão que sempre retornava success=True sem tentar nada.
Agora tenta recuperações reais: reimport, limpeza de DB, reinicialização de estado.
"""
from __future__ import annotations

import importlib
import logging
import os
import sqlite3
import sys
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("atena.self_healing")

ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS  = int(os.getenv("ATENA_HEAL_MAX_ATTEMPTS", "3"))
BASE_BACKOFF  = float(os.getenv("ATENA_HEAL_BACKOFF_S",  "1.5"))


class ComponentStatus(Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    FAILED    = "failed"
    RECOVERING= "recovering"
    DEAD      = "dead"


@dataclass
class ComponentInfo:
    name:              str
    status:            ComponentStatus = ComponentStatus.HEALTHY
    recovery_attempts: int             = 0
    last_error:        str             = ""
    last_check:        float           = field(default_factory=time.time)
    module_path:       Optional[str]   = None   # ex: "modules.curiosity_engine"
    db_path:           Optional[str]   = None   # sqlite db associado
    reset_fn:          Optional[Callable] = None  # função de reset personalizada
    error_count:       int             = 0
    success_count:     int             = 0


class SelfHealingSystem:
    """
    Sistema de auto-cura com recuperações reais por tipo de componente:

    Estratégias implementadas (em ordem de custo crescente):
    1. Re-importar o módulo Python
    2. Limpar e recriar o banco SQLite corrompido
    3. Limpar cache de estado em memória
    4. Chamar reset_fn personalizada do componente
    5. Marcar como DEAD após esgotar tentativas
    """

    def __init__(self) -> None:
        self._components: dict[str, ComponentInfo] = {}
        self._lock = threading.Lock()

    # ── Registro ─────────────────────────────────────────────────────────────

    def register_component(
        self,
        name: str,
        module_path: Optional[str]    = None,
        db_path: Optional[str]        = None,
        reset_fn: Optional[Callable]  = None,
    ) -> None:
        with self._lock:
            self._components[name] = ComponentInfo(
                name=name,
                module_path=module_path,
                db_path=db_path,
                reset_fn=reset_fn,
            )
        logger.info("🛡️ Componente registrado: %s", name)

    # ── Relatório de falha ────────────────────────────────────────────────────

    def report_failure(self, name: str, error_msg: str) -> bool:
        """
        Reporta falha e tenta recuperação real.
        Retorna True se conseguiu recuperar, False caso contrário.
        """
        with self._lock:
            info = self._components.get(name)
            if info is None:
                # Auto-registra componentes desconhecidos
                info = ComponentInfo(name=name)
                self._components[name] = info

            info.status     = ComponentStatus.FAILED
            info.last_error = error_msg
            info.error_count += 1
            logger.error("🚨 %s falhou: %s (erro #%d)", name, error_msg[:120], info.error_count)

        return self._attempt_recovery(name)

    def report_success(self, name: str) -> None:
        with self._lock:
            info = self._components.get(name)
            if info:
                info.status            = ComponentStatus.HEALTHY
                info.recovery_attempts = 0
                info.success_count    += 1

    # ── Recuperação real ──────────────────────────────────────────────────────

    def _attempt_recovery(self, name: str) -> bool:
        with self._lock:
            info = self._components.get(name)
            if info is None:
                return False
            if info.recovery_attempts >= MAX_ATTEMPTS:
                info.status = ComponentStatus.DEAD
                logger.critical("💀 %s: limite de recuperação atingido (%d)", name, MAX_ATTEMPTS)
                return False
            info.status = ComponentStatus.RECOVERING
            attempt     = info.recovery_attempts + 1
            info.recovery_attempts = attempt
            module_path = info.module_path
            db_path     = info.db_path
            reset_fn    = info.reset_fn
            last_error  = info.last_error

        wait = BASE_BACKOFF ** (attempt - 1)
        logger.info("🔧 %s — tentativa %d/%d (aguardando %.1fs)", name, attempt, MAX_ATTEMPTS, wait)
        time.sleep(wait)

        recovered = False
        strategies_tried: list[str] = []

        # Estratégia 1: Re-importar módulo
        if module_path and not recovered:
            recovered = self._heal_reimport(module_path)
            strategies_tried.append(f"reimport:{module_path}")

        # Estratégia 2: Reparar banco SQLite
        if db_path and not recovered:
            recovered = self._heal_db(db_path)
            strategies_tried.append(f"heal_db:{db_path}")

        # Estratégia 3: Limpar arquivo de estado corrompido
        if not recovered and ("corrupt" in last_error.lower() or "json" in last_error.lower()):
            recovered = self._heal_state_files(name)
            strategies_tried.append("clear_state_files")

        # Estratégia 4: Chamar reset_fn personalizada
        if not recovered and reset_fn is not None:
            recovered = self._heal_custom_fn(reset_fn)
            strategies_tried.append("custom_reset_fn")

        with self._lock:
            info = self._components.get(name)
            if info is None:
                return recovered
            if recovered:
                info.status            = ComponentStatus.HEALTHY
                info.recovery_attempts = 0
                logger.info("✅ %s recuperado via: %s", name, ", ".join(strategies_tried))
            else:
                info.status = ComponentStatus.DEGRADED
                logger.warning("⚠️ %s: recuperação parcial — %s", name, ", ".join(strategies_tried))

        # Se ainda não recuperou e há tentativas restantes, tenta novamente
        if not recovered and self._components.get(name, ComponentInfo(name=name)).recovery_attempts < MAX_ATTEMPTS:
            return self._attempt_recovery(name)

        return recovered

    # ── Estratégias concretas ─────────────────────────────────────────────────

    def _heal_reimport(self, module_path: str) -> bool:
        try:
            if module_path in sys.modules:
                del sys.modules[module_path]
            importlib.import_module(module_path)
            logger.debug("reimport ok: %s", module_path)
            return True
        except Exception as e:
            logger.debug("reimport falhou (%s): %s", module_path, e)
            return False

    def _heal_db(self, db_path: str) -> bool:
        p = Path(db_path)
        if not p.exists():
            return True  # não há DB = não há problema
        try:
            # Tenta uma transação simples para verificar integridade
            with sqlite3.connect(str(p)) as conn:
                conn.execute("PRAGMA integrity_check")
                conn.execute("PRAGMA wal_checkpoint(FULL)")
            return True
        except sqlite3.DatabaseError:
            # DB corrompido — faz backup e recria
            backup = p.with_suffix(f".corrupted_{int(time.time())}")
            try:
                p.rename(backup)
                logger.warning("DB corrompido movido para %s", backup.name)
            except OSError:
                try:
                    p.unlink()
                except OSError:
                    pass
            # Cria novo vazio
            try:
                with sqlite3.connect(str(p)) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")
                return True
            except Exception as e:
                logger.error("falha ao recriar DB %s: %s", p.name, e)
                return False

    def _heal_state_files(self, component_name: str) -> bool:
        """Remove arquivos de estado corrompidos conhecidos."""
        recovered = False
        candidates = [
            ROOT / "atena_evolution" / "knowledge" / "knowledge.db",
            ROOT / "evolution" / "meta_learner.db",
            ROOT / "atena_evolution" / "digital_organism_memory.jsonl",
        ]
        for path in candidates:
            if path.exists() and component_name.lower() in path.stem.lower():
                backup = path.with_suffix(f"{path.suffix}.bak_{int(time.time())}")
                try:
                    path.rename(backup)
                    logger.warning("arquivo de estado movido: %s → %s", path.name, backup.name)
                    recovered = True
                except OSError as e:
                    logger.debug("falha ao mover %s: %s", path.name, e)
        return recovered

    def _heal_custom_fn(self, fn: Callable) -> bool:
        try:
            result = fn()
            return result is not False
        except Exception as e:
            logger.debug("reset_fn falhou: %s", e)
            return False

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self, name: str) -> str:
        with self._lock:
            info = self._components.get(name)
            return info.status.value if info else "not_registered"

    def is_healthy(self, name: str) -> bool:
        return self.get_status(name) == "healthy"

    def status_report(self) -> dict[str, Any]:
        with self._lock:
            return {
                name: {
                    "status":       info.status.value,
                    "errors":       info.error_count,
                    "successes":    info.success_count,
                    "attempts":     info.recovery_attempts,
                    "last_error":   info.last_error[:80] if info.last_error else "",
                }
                for name, info in self._components.items()
            }

    def healthy_components(self) -> list[str]:
        with self._lock:
            return [n for n, i in self._components.items() if i.status == ComponentStatus.HEALTHY]

    def dead_components(self) -> list[str]:
        with self._lock:
            return [n for n, i in self._components.items() if i.status == ComponentStatus.DEAD]
