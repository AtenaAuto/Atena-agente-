#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modules/atena_engine.py — Motor de evolução auxiliar da ATENA Ω
Stub de integração com o core de evolução (main.py).

NOTA: Este arquivo foi corrigido pois o original importava 'task_manager'
      que não existe no repositório, causando ImportError.
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AtenaCore:
    """Motor de evolução auxiliar — integra com o core principal (main.py)."""

    def __init__(self):
        self.state_file = Path("./atena_evolution/engine_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        loaded = self._load_state()
        self.generation: int = int(loaded.get("generation", 0))
        self.best_score: float = float(loaded.get("best_score", 0.0))
        self._results: list = []
        logger.info(
            "[AtenaCore] Estado carregado | generation=%s best_score=%.4f",
            self.generation,
            self.best_score,
        )

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[AtenaCore] Falha ao carregar estado persistido: %s", exc)
            return {}

    def _save_state(self) -> None:
        payload = {
            "generation": self.generation,
            "best_score": self.best_score,
        }
        self.state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def evolve_one_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo de evolução."""
        self.generation += 1
        logger.info(f"[AtenaCore] Iniciando ciclo de evolução #{self.generation}")
        try:
            # Stub: o ciclo real é executado pelo main.py
            await asyncio.sleep(0)
            result = {
                "success": True,
                "generation": self.generation,
                "score": self.best_score,
            }
            self._results.append(result)
            self._save_state()
            logger.info(f"[AtenaCore] ✅ Ciclo #{self.generation} concluído")
            return result
        except Exception as e:
            logger.error(f"[AtenaCore] Erro no ciclo #{self.generation}: {e}")
            return {"success": False, "generation": self.generation, "error": str(e)}

    async def run_autonomous(self, generations: int = 10) -> None:
        """Executa múltiplas gerações de evolução."""
        logger.info(f"[AtenaCore] Iniciando {generations} gerações autônomas")
        for _ in range(generations):
            result = await self.evolve_one_cycle()
            if not result.get("success"):
                logger.warning(f"[AtenaCore] Geração {self.generation} falhou, continuando...")
        self.print_status()

    def print_status(self) -> None:
        """Exibe o status atual do motor."""
        total = len(self._results)
        ok = sum(1 for r in self._results if r.get("success"))
        message = (
            f"[AtenaCore] Status: {ok}/{total} ciclos bem-sucedidos | "
            f"Geração atual: {self.generation} | "
            f"Melhor score: {self.best_score:.4f}"
        )
        print(message)
        logger.info(message)
