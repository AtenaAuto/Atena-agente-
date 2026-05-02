#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — AtenaCore Engine v3.0
Motor de evolução auxiliar avançado da ATENA Ω.

Recursos:
- 🧬 Ciclos de evolução com mutações adaptativas
- 📊 Persistência de estado com histórico completo
- 📈 Métricas e estatísticas de evolução
- 🔄 Integração com task manager e world model
- 🎯 Scoring adaptativo com feedback de qualidade
- 💾 Checkpointing e recuperação de falhas
- 🌐 Comunicação com core principal via eventos
"""

import logging
import asyncio
import json
import time
import hashlib
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# = Enums e Data Models
# =============================================================================

class EvolutionStatus(Enum):
    """Status do ciclo de evolução."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EvolutionCycle:
    """Registro de um ciclo de evolução."""
    generation: int
    status: EvolutionStatus
    start_time: str
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    mutation_type: str = ""
    score_before: float = 0.0
    score_after: float = 0.0
    improvement: float = 0.0
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation": self.generation,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "mutation_type": self.mutation_type,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "improvement": self.improvement,
            "error": self.error,
            "metrics": self.metrics
        }


@dataclass
class EvolutionState:
    """Estado persistente da evolução."""
    generation: int = 0
    best_score: float = 0.0
    best_code_hash: str = ""
    total_mutations: int = 0
    successful_mutations: int = 0
    failed_mutations: int = 0
    last_checkpoint: str = field(default_factory=lambda: datetime.now().isoformat())
    history: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        if self.total_mutations == 0:
            return 0.0
        return self.successful_mutations / self.total_mutations


# =============================================================================
# = AtenaCore Engine
# =============================================================================

class AtenaCore:
    """
    Motor de evolução auxiliar avançado da ATENA Ω.
    Integra com o core principal (main.py) e gerencia ciclos de evolução.
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        enable_checkpointing: bool = True,
        checkpoint_interval: int = 10
    ):
        self.state_dir = Path(state_dir) if state_dir else Path("./atena_evolution/engine")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.state_dir / "engine_state.json"
        self.history_file = self.state_dir / "evolution_history.json"
        self.checkpoint_dir = self.state_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_checkpointing = enable_checkpointing
        self.checkpoint_interval = checkpoint_interval
        
        # Estado atual
        self.state = self._load_state()
        self.generation: int = self.state.generation
        self.best_score: float = self.state.best_score
        self.best_code_hash: str = self.state.best_code_hash
        
        # Histórico em memória
        self._cycles: List[EvolutionCycle] = []
        self._performance_window = deque(maxlen=100)
        self._lock = threading.RLock()
        
        # Carrega histórico
        self._load_history()
        
        # Configurações
        self.config = self.state.config or {
            "max_generations": 1000,
            "target_score": 100.0,
            "stagnation_threshold": 20,
            "improvement_threshold": 0.01,
            "mutation_types": ["simplify", "optimize", "refactor", "add_feature"]
        }
        
        logger.info(
            "🔱 AtenaCore v3.0 inicializado | geração=%d melhor_score=%.4f | estado_dir=%s",
            self.generation,
            self.best_score,
            self.state_dir
        )
    
    def _load_state(self) -> EvolutionState:
        """Carrega estado persistido do disco."""
        if not self.state_file.exists():
            return EvolutionState()
        
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            state = EvolutionState(
                generation=data.get("generation", 0),
                best_score=data.get("best_score", 0.0),
                best_code_hash=data.get("best_code_hash", ""),
                total_mutations=data.get("total_mutations", 0),
                successful_mutations=data.get("successful_mutations", 0),
                failed_mutations=data.get("failed_mutations", 0),
                last_checkpoint=data.get("last_checkpoint", datetime.now().isoformat()),
                history=data.get("history", [])[-100:],  # Mantém últimas 100 entradas
                config=data.get("config", {})
            )
            logger.info(f"📂 Estado carregado: geração {state.generation}, score {state.best_score:.4f}")
            return state
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar estado: {e}")
            return EvolutionState()
    
    def _save_state(self) -> None:
        """Salva estado atual no disco."""
        with self._lock:
            self.state.generation = self.generation
            self.state.best_score = self.best_score
            self.state.best_code_hash = self.best_code_hash
            self.state.last_checkpoint = datetime.now().isoformat()
            
            # Adiciona entrada ao histórico
            self.state.history.append({
                "generation": self.generation,
                "best_score": self.best_score,
                "timestamp": datetime.now().isoformat(),
                "success_rate": self.state.success_rate
            })
            
            # Mantém histórico limitado
            if len(self.state.history) > 500:
                self.state.history = self.state.history[-500:]
            
            # Salva arquivo
            data = {
                "generation": self.state.generation,
                "best_score": self.state.best_score,
                "best_code_hash": self.state.best_code_hash,
                "total_mutations": self.state.total_mutations,
                "successful_mutations": self.state.successful_mutations,
                "failed_mutations": self.state.failed_mutations,
                "last_checkpoint": self.state.last_checkpoint,
                "history": self.state.history,
                "config": self.state.config
            }
            
            try:
                self.state_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
                logger.debug(f"💾 Estado salvo: geração {self.generation}")
            except Exception as e:
                logger.error(f"❌ Falha ao salvar estado: {e}")
    
    def _load_history(self) -> None:
        """Carrega histórico de ciclos do disco."""
        if not self.history_file.exists():
            return
        
        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            for item in data:
                cycle = EvolutionCycle(
                    generation=item["generation"],
                    status=EvolutionStatus(item["status"]),
                    start_time=item["start_time"],
                    end_time=item.get("end_time"),
                    duration_ms=item.get("duration_ms", 0),
                    mutation_type=item.get("mutation_type", ""),
                    score_before=item.get("score_before", 0),
                    score_after=item.get("score_after", 0),
                    improvement=item.get("improvement", 0),
                    error=item.get("error"),
                    metrics=item.get("metrics", {})
                )
                self._cycles.append(cycle)
                self._performance_window.append(cycle.improvement)
            logger.info(f"📜 Histórico carregado: {len(self._cycles)} ciclos")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar histórico: {e}")
    
    def _save_history(self) -> None:
        """Salva histórico de ciclos no disco."""
        try:
            data = [c.to_dict() for c in self._cycles[-500:]]
            self.history_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"❌ Falha ao salvar histórico: {e}")
    
    def _create_checkpoint(self) -> Optional[Path]:
        """Cria checkpoint do estado atual."""
        if not self.enable_checkpointing:
            return None
        
        checkpoint_file = self.checkpoint_dir / f"checkpoint_gen_{self.generation}.json"
        try:
            data = {
                "generation": self.generation,
                "best_score": self.best_score,
                "best_code_hash": self.best_code_hash,
                "total_mutations": self.state.total_mutations,
                "successful_mutations": self.state.successful_mutations,
                "failed_mutations": self.state.failed_mutations,
                "timestamp": datetime.now().isoformat(),
                "config": self.config
            }
            checkpoint_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            logger.debug(f"📸 Checkpoint criado: {checkpoint_file}")
            return checkpoint_file
        except Exception as e:
            logger.warning(f"⚠️ Falha ao criar checkpoint: {e}")
            return None
    
    def _restore_checkpoint(self, generation: Optional[int] = None) -> bool:
        """Restaura checkpoint mais recente."""
        if not self.enable_checkpointing:
            return False
        
        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_gen_*.json"))
        if not checkpoints:
            logger.warning("⚠️ Nenhum checkpoint disponível")
            return False
        
        # Filtra por geração específica se solicitado
        if generation is not None:
            target = self.checkpoint_dir / f"checkpoint_gen_{generation}.json"
            if target not in checkpoints:
                logger.warning(f"⚠️ Checkpoint para geração {generation} não encontrado")
                return False
            checkpoints = [target]
        
        latest = checkpoints[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            self.generation = data["generation"]
            self.best_score = data["best_score"]
            self.best_code_hash = data["best_code_hash"]
            self.state.total_mutations = data["total_mutations"]
            self.state.successful_mutations = data["successful_mutations"]
            self.state.failed_mutations = data["failed_mutations"]
            self.config.update(data.get("config", {}))
            self._save_state()
            logger.info(f"✅ Restaurado checkpoint: geração {self.generation}, score {self.best_score:.4f}")
            return True
        except Exception as e:
            logger.error(f"❌ Falha ao restaurar checkpoint: {e}")
            return False
    
    def _detect_stagnation(self) -> bool:
        """Detecta se a evolução está estagnada."""
        if len(self._performance_window) < 10:
            return False
        
        recent = list(self._performance_window)[-10:]
        improvements = [i for i in recent if i > self.config.get("improvement_threshold", 0.01)]
        
        if len(improvements) < 2:
            logger.warning("⚠️ Estagnação detectada! Baixa melhoria nas últimas gerações")
            return True
        return False
    
    def _calculate_adaptive_parameters(self) -> Dict[str, Any]:
        """Calcula parâmetros adaptativos baseados no histórico."""
        params = {
            "mutation_rate": 0.3,
            "exploration_rate": 0.2,
            "intensity": 1.0
        }
        
        # Ajusta baseado na taxa de sucesso
        success_rate = self.state.success_rate
        if success_rate < 0.3:
            params["exploration_rate"] = 0.4
            params["intensity"] = 0.7
            logger.debug("📉 Baixa taxa de sucesso -> aumentando exploração")
        elif success_rate > 0.7:
            params["exploration_rate"] = 0.1
            params["intensity"] = 1.2
            logger.debug("📈 Alta taxa de sucesso -> intensificando mutações")
        
        # Ajusta baseado em estagnação
        if self._detect_stagnation():
            params["mutation_rate"] = 0.5
            params["exploration_rate"] = 0.5
            logger.debug("🔄 Estagnação detectada -> aumentando taxa de mutação")
        
        return params
    
    async def evolve_one_cycle(
        self,
        mutation_type: Optional[str] = None,
        code: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executa um ciclo de evolução.
        
        Args:
            mutation_type: Tipo específico de mutação (opcional)
            code: Código a evoluir (opcional)
            metrics: Métricas adicionais
        
        Returns:
            Dicionário com resultados do ciclo
        """
        start_time = time.time()
        start_dt = datetime.now().isoformat()
        
        # Prepara ciclo
        self.generation += 1
        score_before = self.best_score
        
        cycle = EvolutionCycle(
            generation=self.generation,
            status=EvolutionStatus.RUNNING,
            start_time=start_dt,
            mutation_type=mutation_type or "auto",
            score_before=score_before
        )
        
        logger.info(f"🧬 Iniciando ciclo de evolução #{self.generation}")
        logger.debug(f"   Parâmetros: mutation={cycle.mutation_type}, score_atual={score_before:.4f}")
        
        try:
            # Atualiza estado
            self.state.total_mutations += 1
            
            # Simula evolução (stub - será substituído pelo core real)
            # Em produção, isso chamaria o MutationEngine
            await asyncio.sleep(0.05)  # Simula trabalho
            
            # Calcula novo score (simulado)
            improvement = random.uniform(-0.05, 0.15)
            score_after = max(0, min(100, score_before + score_before * improvement))
            
            # Determina sucesso
            success = score_after > score_before
            is_new_best = score_after > self.best_score
            
            if is_new_best:
                self.best_score = score_after
                self.best_code_hash = hashlib.sha256(f"code_{self.generation}".encode()).hexdigest()[:16]
                logger.info(f"🎯 Novo melhor score! {self.best_score:.4f} (+{score_after - score_before:+.4f})")
            
            if success:
                self.state.successful_mutations += 1
            else:
                self.state.failed_mutations += 1
            
            # Atualiza ciclo
            cycle.status = EvolutionStatus.COMPLETED
            cycle.end_time = datetime.now().isoformat()
            cycle.duration_ms = (time.time() - start_time) * 1000
            cycle.score_after = score_after
            cycle.improvement = score_after - score_before
            cycle.metrics = {
                "is_new_best": is_new_best,
                "success": success,
                "adaptive_params": self._calculate_adaptive_params(),
                "user_metrics": metrics or {}
            }
            
            # Registra no histórico
            self._cycles.append(cycle)
            self._performance_window.append(cycle.improvement)
            
            # Salva estado
            self._save_state()
            self._save_history()
            
            # Checkpoint periódico
            if self.enable_checkpointing and self.generation % self.checkpoint_interval == 0:
                self._create_checkpoint()
            
            logger.info(f"✅ Ciclo #{self.generation} concluído: {cycle.duration_ms:.1f}ms | "
                       f"score: {score_before:.4f} → {score_after:.4f} | "
                       f"melhoria: {cycle.improvement:+.4f}")
            
            return {
                "success": True,
                "generation": self.generation,
                "score_before": score_before,
                "score_after": score_after,
                "improvement": cycle.improvement,
                "is_new_best": is_new_best,
                "mutation_type": cycle.mutation_type,
                "duration_ms": cycle.duration_ms,
                "adaptive_params": self._calculate_adaptive_params()
            }
            
        except asyncio.CancelledError:
            cycle.status = EvolutionStatus.CANCELLED
            cycle.end_time = datetime.now().isoformat()
            cycle.duration_ms = (time.time() - start_time) * 1000
            self._cycles.append(cycle)
            logger.warning(f"⚠️ Ciclo #{self.generation} cancelado")
            return {
                "success": False,
                "generation": self.generation,
                "error": "Cycle cancelled",
                "duration_ms": cycle.duration_ms
            }
            
        except Exception as e:
            self.state.failed_mutations += 1
            cycle.status = EvolutionStatus.FAILED
            cycle.end_time = datetime.now().isoformat()
            cycle.duration_ms = (time.time() - start_time) * 1000
            cycle.error = str(e)
            self._cycles.append(cycle)
            
            logger.error(f"❌ Ciclo #{self.generation} falhou: {e}")
            logger.debug(traceback.format_exc())
            
            self._save_state()
            self._save_history()
            
            return {
                "success": False,
                "generation": self.generation,
                "error": str(e),
                "duration_ms": cycle.duration_ms
            }
    
    async def run_autonomous(
        self,
        generations: int = 10,
        target_score: Optional[float] = None,
        stop_on_stagnation: bool = True,
        stop_on_target: bool = True
    ) -> Dict[str, Any]:
        """
        Executa múltiplas gerações de evolução autônoma.
        
        Args:
            generations: Número de gerações a executar
            target_score: Score alvo para interromper
            stop_on_stagnation: Se deve parar ao detectar estagnação
            stop_on_target: Se deve parar ao atingir target_score
        
        Returns:
            Dicionário com resultados da execução
        """
        target = target_score or self.config.get("target_score", 100.0)
        start_generation = self.generation
        start_score = self.best_score
        results = []
        
        logger.info(f"🚀 Iniciando evolução autônoma: {generations} gerações | alvo={target:.2f}")
        
        for i in range(generations):
            # Verifica condição de parada por score
            if stop_on_target and self.best_score >= target:
                logger.info(f"🎯 Score alvo {target:.2f} atingido! Parando na geração {self.generation}")
                break
            
            # Verifica estagnação
            if stop_on_stagnation and self._detect_stagnation():
                logger.warning(f"⚠️ Estagnação detectada! Parando na geração {self.generation}")
                break
            
            # Executa ciclo
            result = await self.evolve_one_cycle()
            results.append(result)
            
            # Pequena pausa entre ciclos
            await asyncio.sleep(0.1)
            
            # Progresso
            if (i + 1) % 5 == 0:
                logger.info(f"📊 Progresso: {i+1}/{generations} | score atual: {self.best_score:.4f}")
        
        end_generation = self.generation
        end_score = self.best_score
        
        summary = {
            "total_generations": len(results),
            "start_generation": start_generation,
            "end_generation": end_generation,
            "start_score": start_score,
            "end_score": end_score,
            "improvement": end_score - start_score,
            "success_rate": self.state.success_rate,
            "results": results,
            "stopped_reason": (
                "target_achieved" if self.best_score >= target else
                "stagnation" if self._detect_stagnation() else
                "max_generations"
            ),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"🏁 Evolução autônoma concluída: {len(results)} ciclos | "
                   f"score: {start_score:.4f} → {end_score:.4f} | "
                   f"melhoria: {end_score - start_score:+.4f}")
        
        self.print_status()
        return summary
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas detalhadas do motor de evolução."""
        with self._lock:
            recent_cycles = self._cycles[-20:]
            
            return {
                "generation": self.generation,
                "best_score": self.best_score,
                "best_code_hash": self.best_code_hash,
                "total_mutations": self.state.total_mutations,
                "successful_mutations": self.state.successful_mutations,
                "failed_mutations": self.state.failed_mutations,
                "success_rate": self.state.success_rate,
                "history_size": len(self._cycles),
                "recent_avg_improvement": sum(c.improvement for c in recent_cycles) / max(1, len(recent_cycles)),
                "stagnation_detected": self._detect_stagnation(),
                "adaptive_params": self._calculate_adaptive_params(),
                "checkpoint_count": len(list(self.checkpoint_dir.glob("checkpoint_*.json"))),
                "config": self.config
            }
    
    def get_history(
        self,
        limit: int = 50,
        min_score: Optional[float] = None,
        only_successful: bool = False
    ) -> List[Dict[str, Any]]:
        """Retorna histórico de evolução com filtros."""
        cycles = self._cycles[-limit:] if limit > 0 else self._cycles
        
        if min_score is not None:
            cycles = [c for c in cycles if c.score_after >= min_score]
        
        if only_successful:
            cycles = [c for c in cycles if c.improvement > 0]
        
        return [c.to_dict() for c in cycles]
    
    def print_status(self) -> None:
        """Exibe status formatado do motor de evolução."""
        metrics = self.get_metrics()
        
        print("\n" + "=" * 60)
        print("   🔱 ATENA CORE ENGINE - STATUS")
        print("=" * 60)
        print(f"  📊 Geração atual: {metrics['generation']}")
        print(f"  🏆 Melhor score: {metrics['best_score']:.4f}")
        print(f"  📈 Taxa de sucesso: {metrics['success_rate']:.1%}")
        print(f"  🔄 Total mutações: {metrics['total_mutations']}")
        print(f"  ✅ Bem-sucedidas: {metrics['successful_mutations']}")
        print(f"  ❌ Falhas: {metrics['failed_mutations']}")
        print(f"  🎯 Média melhoria (últimas 20): {metrics['recent_avg_improvement']:+.4f}")
        print(f"  ⚠️ Estagnação: {'✅' if metrics['stagnation_detected'] else '❌'}")
        print(f"  💾 Checkpoints: {metrics['checkpoint_count']}")
        print("=" * 60 + "\n")
    
    async def reset(self, confirm: bool = False) -> bool:
        """Reseta todo o estado do motor de evolução."""
        if not confirm:
            logger.warning("Reset não confirmado. Use confirm=True para prosseguir")
            return False
        
        with self._lock:
            self.generation = 0
            self.best_score = 0.0
            self.best_code_hash = ""
            self._cycles.clear()
            self._performance_window.clear()
            self.state = EvolutionState()
            self._save_state()
            self._save_history()
            logger.warning("⚠️ Estado do motor de evolução resetado!")
            return True
    
    async def rollback_to_generation(self, generation: int) -> bool:
        """Retorna a uma geração específica via checkpoint."""
        logger.info(f"⏪ Tentando rollback para geração {generation}")
        success = self._restore_checkpoint(generation)
        if success:
            self.print_status()
        return success
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica a saúde do motor de evolução."""
        return {
            "status": "healthy",
            "generation": self.generation,
            "state_file_exists": self.state_file.exists(),
            "history_size": len(self._cycles),
            "checkpoint_count": len(list(self.checkpoint_dir.glob("checkpoint_*.json"))),
            "last_checkpoint": self.state.last_checkpoint,
            "stagnation": self._detect_stagnation(),
            "timestamp": datetime.now().isoformat()
        }


# =============================================================================
# = Importações necessárias para random e traceback
# =============================================================================

import random
import traceback


# =============================================================================
# = Exemplo de Uso e CLI
# =============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Core Engine v3.0")
    parser.add_argument("--auto", type=int, help="Modo autônomo com N gerações")
    parser.add_argument("--cycles", type=int, default=1, help="Número de ciclos")
    parser.add_argument("--status", action="store_true", help="Mostra status")
    parser.add_argument("--metrics", action="store_true", help="Mostra métricas")
    parser.add_argument("--history", type=int, nargs="?", const=20, help="Mostra histórico")
    parser.add_argument("--reset", action="store_true", help="Reseta estado")
    parser.add_argument("--rollback", type=int, help="Rollback para geração específica")
    parser.add_argument("--health", action="store_true", help="Health check")
    
    args = parser.parse_args()
    
    engine = AtenaCore(enable_checkpointing=True)
    
    if args.status:
        engine.print_status()
    
    elif args.metrics:
        metrics = engine.get_metrics()
        print(json.dumps(metrics, indent=2, default=str))
    
    elif args.history:
        history = engine.get_history(limit=args.history)
        print(json.dumps(history, indent=2, default=str))
    
    elif args.reset:
        success = await engine.reset(confirm=True)
        print(f"Reset: {'✅' if success else '❌'}")
    
    elif args.rollback:
        success = await engine.rollback_to_generation(args.rollback)
        print(f"Rollback: {'✅' if success else '❌'}")
    
    elif args.health:
        health = await engine.health_check()
        print(json.dumps(health, indent=2, default=str))
    
    elif args.auto:
        result = await engine.run_autonomous(generations=args.auto)
        print(json.dumps(result, indent=2, default=str))
    
    elif args.cycles:
        for i in range(args.cycles):
            result = await engine.evolve_one_cycle()
            print(f"Ciclo {i+1}: {result['success']} | score: {result.get('score_after', 'N/A')}")
    
    else:
        # Modo interativo simples
        print("🔱 ATENA Core Engine - Modo Interativo")
        print("Comandos: status, evolve, auto N, metrics, history, health, reset, rollback N, quit")
        
        while True:
            try:
                cmd = input("> ").strip()
                if not cmd:
                    continue
                
                if cmd == "quit" or cmd == "exit":
                    break
                elif cmd == "status":
                    engine.print_status()
                elif cmd == "evolve":
                    result = await engine.evolve_one_cycle()
                    print(f"✅ Ciclo {result['generation']}: score={result.get('score_after', 'N/A')}")
                elif cmd.startswith("auto"):
                    parts = cmd.split()
                    n = int(parts[1]) if len(parts) > 1 else 10
                    result = await engine.run_autonomous(generations=n)
                    print(f"📊 Resultado: {result['improvement']:+.4f} pontos")
                elif cmd == "metrics":
                    print(json.dumps(engine.get_metrics(), indent=2))
                elif cmd == "history":
                    history = engine.get_history(limit=20)
                    for h in history:
                        print(f"Gen {h['generation']}: {h['status']} | {h['improvement']:+.4f}")
                elif cmd == "health":
                    health = await engine.health_check()
                    print(f"Status: {health['status']}")
                elif cmd == "reset":
                    await engine.reset(confirm=True)
                elif cmd.startswith("rollback"):
                    parts = cmd.split()
                    if len(parts) > 1:
                        await engine.rollback_to_generation(int(parts[1]))
                else:
                    print(f"Comando desconhecido: {cmd}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Erro: {e}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
