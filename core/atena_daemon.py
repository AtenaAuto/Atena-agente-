#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Daemon de Persistência (v2)
Inicializa todos os sistemas integrados antes de subir o processo principal.
"""
import os
import signal
import subprocess
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DAEMON] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("atena_daemon.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("atena.daemon")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _boot_subsystems() -> None:
    """Inicializa subsistemas na ordem correta antes de subir o processo."""

    # 1. Event bus
    try:
        from core.atena_event_bus import get_event_bus
        bus = get_event_bus()
        logger.info("✅ EventBus inicializado")
    except Exception as e:
        logger.warning("EventBus falhou: %s", e)

    # 2. Rate limiter + deduplicador de URLs
    try:
        from core.atena_rate_limiter import install_on_internet_challenge
        install_on_internet_challenge()
        logger.info("✅ RateLimiter + Deduplicador instalados")
    except Exception as e:
        logger.warning("RateLimiter falhou: %s", e)

    # 3. Self-healing — registra componentes críticos
    try:
        from core.atena_self_healing import SelfHealingSystem
        healing = SelfHealingSystem()
        healing.register_component("llm_router",     module_path="core.atena_llm_router")
        healing.register_component("code_module",    module_path="modules.atena_code_module")
        healing.register_component("internet",       module_path="core.internet_challenge")
        healing.register_component("graph_memory",   module_path="modules.graph_memory",
                                   db_path=str(ROOT / "atena_evolution/knowledge/graph_memory.db"))
        logger.info("✅ SelfHealingSystem inicializado (%d componentes)", 4)
    except Exception as e:
        logger.warning("SelfHealing falhou: %s", e)

    # 4. Rollback manager — purge de snapshots antigos
    try:
        from core.atena_smart_rollback import SmartRollbackManager
        rb = SmartRollbackManager()
        removed = rb.purge_old(keep=10)
        logger.info("✅ SmartRollback inicializado (purge: %d snapshots antigos)", removed)
    except Exception as e:
        logger.warning("SmartRollback falhou: %s", e)

    # 5. Meta-learner — roda análise inicial
    try:
        from core.atena_meta_learner import SelfReflectiveMetaLearner
        meta = SelfReflectiveMetaLearner()
        pattern = meta.analyze_logs()
        logger.info(
            "✅ MetaLearner: %d ciclos analisados | trend=%s | avg_fitness=%.1f",
            pattern.sampled_cycles, pattern.fitness_trend, pattern.avg_fitness,
        )
    except Exception as e:
        logger.warning("MetaLearner falhou: %s", e)

    # 6. Response cache — purge de entradas expiradas
    try:
        from core.atena_response_cache import get_global_cache
        cache = get_global_cache()
        removed = cache.purge_expired()
        logger.info("✅ ResponseCache inicializado (purge: %d expiradas)", removed)
    except Exception as e:
        logger.warning("ResponseCache falhou: %s", e)

    logger.info("🚀 Todos os subsistemas prontos")


class AtenaDaemon:
    """
    Daemon que:
    1. Inicializa subsistemas integrados
    2. Sobe o processo principal
    3. Monitora e reinicia em caso de falha
    4. Persiste logs de execução
    """

    def __init__(self, script_path: str = "main.py") -> None:
        self.script_path = script_path
        self.process = None
        self.running = True
        self._restart_count = 0
        self._max_restarts  = int(os.getenv("ATENA_DAEMON_MAX_RESTARTS", "10"))
        self._restart_delay = float(os.getenv("ATENA_DAEMON_RESTART_DELAY_S", "10.0"))

        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT,  self.stop)

    def start(self) -> None:
        logger.info("🚀 Iniciando ATENA Ω em modo persistente...")
        _boot_subsystems()

        while self.running:
            if self._restart_count >= self._max_restarts:
                logger.critical(
                    "💀 Limite de reinícios atingido (%d). Encerrando daemon.",
                    self._max_restarts,
                )
                break

            try:
                log_path = ROOT / "atena_execution.log"
                with open(log_path, "a") as log_file:
                    self.process = subprocess.Popen(
                        [sys.executable, self.script_path],
                        stdout=log_file,
                        stderr=log_file,
                        preexec_fn=os.setsid,
                    )

                logger.info("✅ Processo ATENA iniciado (PID: %d | reinício #%d)",
                            self.process.pid, self._restart_count)

                while self.process.poll() is None:
                    if not self.running:
                        break
                    time.sleep(5)

                if self.running:
                    exit_code = self.process.returncode
                    self._restart_count += 1
                    logger.warning(
                        "⚠️ ATENA encerrou (código=%d, reinício #%d/%d). Aguardando %.0fs...",
                        exit_code, self._restart_count, self._max_restarts, self._restart_delay,
                    )
                    time.sleep(self._restart_delay)

            except Exception as e:
                logger.error("❌ Erro crítico no Daemon: %s", e)
                self._restart_count += 1
                time.sleep(self._restart_delay * 3)

    def stop(self, signum=None, frame=None) -> None:
        logger.info("🛑 Encerrando Daemon...")
        self.running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        sys.exit(0)


if __name__ == "__main__":
    os.chdir(ROOT)
    daemon = AtenaDaemon()
    daemon.start()
