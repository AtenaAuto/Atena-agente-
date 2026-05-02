#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Base Actuators Framework v3.0
Sistema base para atuadores de sistema com logging avançado, rastreamento e extensibilidade.

Recursos:
- 📊 Logging estruturado com contexto
- 🎯 Rastreamento de ações com decorators
- 🔒 Sanitização automática de dados sensíveis
- 📈 Métricas de performance por ação
- 🔄 Sistema de hooks para extensão
- 💾 Persistência opcional do histórico
- 🛡️ Tratamento robusto de exceções
"""

import logging
import time
import functools
import json
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, List, Tuple, Union
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from enum import Enum
import traceback
from dataclasses import dataclass, field

logger = logging.getLogger("atena.actuators")


# =============================================================================
= Enums e Data Models
# =============================================================================

class ActionStatus(Enum):
    """Status de execução de uma ação."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ActionSeverity(Enum):
    """Severidade da ação para logging."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ActionRecord:
    """Registro de uma ação executada."""
    name: str
    status: ActionStatus
    duration_ms: float
    timestamp: str
    actuator: str
    params: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    severity: ActionSeverity = ActionSeverity.INFO
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "name": self.name,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "actuator": self.actuator,
            "params": self._sanitize_params(self.params),
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "severity": self.severity.value,
            "tags": self.tags,
            "metadata": self.metadata
        }
    
    @staticmethod
    def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove dados sensíveis dos parâmetros."""
        sensitive_keys = {"password", "token", "secret", "api_key", "auth"}
        safe = {}
        for k, v in params.items():
            if k in sensitive_keys:
                safe[k] = "***REDACTED***"
            elif isinstance(v, dict):
                safe[k] = ActionRecord._sanitize_params(v)
            else:
                safe[k] = v
        return safe


# =============================================================================
= Action Tracker Decorator
# =============================================================================

def track_action(
    action_name: Optional[str] = None,
    severity: ActionSeverity = ActionSeverity.INFO,
    capture_result: bool = True,
    log_params: bool = True,
    tags: Optional[List[str]] = None
) -> Callable:
    """
    Decorator avançado que registra automaticamente a execução de métodos.

    Args:
        action_name: Nome da ação (padrão: nome do método)
        severity: Severidade para logging
        capture_result: Se deve capturar o resultado da ação
        log_params: Se deve logar os parâmetros
        tags: Tags adicionais para categorização
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            act_name = action_name or func.__name__
            start_time = time.perf_counter()
            
            # Prepara parâmetros para logging
            params = {}
            if log_params:
                # Captura args nomeados
                if hasattr(self, '_get_action_params'):
                    params = self._get_action_params(*args, **kwargs)
                else:
                    # Fallback: captura posicionais
                    if args:
                        params["args"] = [str(a)[:100] for a in args]
                    if kwargs:
                        params["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}
            
            # Executa ação
            try:
                result = func(self, *args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Registra sucesso
                self.log_action(
                    act_name,
                    status=ActionStatus.SUCCESS,
                    duration_ms=duration_ms,
                    params=params,
                    result=result if capture_result else None,
                    severity=severity,
                    tags=tags
                )
                return result
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Registra erro
                self.log_action(
                    act_name,
                    status=ActionStatus.ERROR,
                    duration_ms=duration_ms,
                    params=params,
                    error=str(e),
                    severity=ActionSeverity.ERROR,
                    tags=tags
                )
                raise
                
            except BaseException as e:
                # Captura também KeyboardInterrupt, SystemExit
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.log_action(
                    act_name,
                    status=ActionStatus.CANCELLED,
                    duration_ms=duration_ms,
                    params=params,
                    error=str(e),
                    severity=ActionSeverity.WARNING,
                    tags=tags
                )
                raise
        
        return wrapper
    return decorator


# =============================================================================
= Base Actuator Class
# =============================================================================

class BaseActuator(ABC):
    """
    Classe base abstrata para todos os atuadores da ATENA Ω.
    
    Fornece funcionalidades comuns:
        - Verificação de dependências (abstrato)
        - Logging estruturado com contexto
        - Rastreamento de ações (tempo, sucesso/erro)
        - Configuração opcional de histórico
        - Sistema de hooks para extensão
        - Métricas de performance
    """

    def __init__(
        self,
        sysaware: Optional[Any] = None,
        enable_history: bool = False,
        history_max_size: int = 1000,
        persist_history: bool = False,
        history_path: Optional[Path] = None
    ):
        """
        Inicializa o atuador.

        Args:
            sysaware: Instância de SysAware (fornece contexto adicional)
            enable_history: Se True, mantém um histórico interno das ações
            history_max_size: Tamanho máximo do histórico
            persist_history: Se True, persiste histórico em disco
            history_path: Caminho para persistência do histórico
        """
        self.sysaware = sysaware
        self.enable_history = enable_history
        self.history_max_size = history_max_size
        self.persist_history = persist_history
        self.history_path = history_path or Path(f"atena_evolution/actuators/{self.__class__.__name__}_history.json")
        
        self._action_history: List[ActionRecord] = [] if enable_history else None
        self._metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "success": 0,
            "error": 0,
            "total_duration_ms": 0,
            "avg_duration_ms": 0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0
        })
        self._lock = threading.RLock()
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Verifica dependências
        self._check_dependencies()
        
        # Carrega histórico persistente
        if self.persist_history and self.enable_history:
            self._load_history()
        
        logger.debug(f"{self.__class__.__name__} inicializado (sysaware={sysaware is not None}, history={enable_history})")
    
    @abstractmethod
    def _check_dependencies(self) -> None:
        """
        Verifica se as dependências necessárias estão disponíveis.
        
        Raises:
            ImportError: Se alguma biblioteca obrigatória não estiver instalada.
            RuntimeError: Se alguma ferramenta de sistema não for encontrada.
        """
        pass
    
    def _load_history(self) -> None:
        """Carrega histórico persistente do disco."""
        if not self.history_path or not self.history_path.exists():
            return
        
        try:
            with open(self.history_path, 'r') as f:
                data = json.load(f)
                for item in data[-self.history_max_size:]:
                    record = ActionRecord(
                        name=item['name'],
                        status=ActionStatus(item['status']),
                        duration_ms=item['duration_ms'],
                        timestamp=item['timestamp'],
                        actuator=item['actuator'],
                        params=item.get('params', {}),
                        result=item.get('result'),
                        error=item.get('error'),
                        severity=ActionSeverity(item.get('severity', 'info')),
                        tags=item.get('tags', [])
                    )
                    self._action_history.append(record)
            logger.debug(f"Histórico carregado: {len(self._action_history)} registros")
        except Exception as e:
            logger.warning(f"Erro ao carregar histórico: {e}")
    
    def _save_history(self) -> None:
        """Persiste histórico em disco."""
        if not self.persist_history or not self.enable_history or not self._action_history:
            return
        
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w') as f:
                json.dump([r.to_dict() for r in self._action_history[-self.history_max_size:]], f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar histórico: {e}")
    
    def _update_metrics(self, action_name: str, success: bool, duration_ms: float) -> None:
        """Atualiza métricas de performance."""
        with self._lock:
            metrics = self._metrics[action_name]
            metrics["count"] += 1
            if success:
                metrics["success"] += 1
            else:
                metrics["error"] += 1
            metrics["total_duration_ms"] += duration_ms
            metrics["avg_duration_ms"] = metrics["total_duration_ms"] / metrics["count"]
            metrics["min_duration_ms"] = min(metrics["min_duration_ms"], duration_ms)
            metrics["max_duration_ms"] = max(metrics["max_duration_ms"], duration_ms)
    
    def log_action(
        self,
        action: str,
        status: ActionStatus = ActionStatus.SUCCESS,
        duration_ms: float = 0.0,
        params: Optional[Dict[str, Any]] = None,
        result: Any = None,
        error: Optional[str] = None,
        severity: ActionSeverity = ActionSeverity.INFO,
        tags: Optional[List[str]] = None
    ) -> None:
        """
        Registra uma ação realizada pelo atuador com contexto estruturado.
        """
        # Atualiza métricas
        self._update_metrics(action, status == ActionStatus.SUCCESS, duration_ms)
        
        # Cria registro
        record = ActionRecord(
            name=action,
            status=status,
            duration_ms=round(duration_ms, 2),
            timestamp=datetime.now().isoformat(),
            actuator=self.__class__.__name__,
            params=params or {},
            result=result,
            error=error,
            severity=severity,
            tags=tags or []
        )
        
        # Log no logger
        log_msg = f"[{self.__class__.__name__}] {action} - {status.value} ({duration_ms:.2f}ms)"
        if error:
            log_msg += f" - {error}"
        
        log_level = {
            ActionSeverity.DEBUG: logging.DEBUG,
            ActionSeverity.INFO: logging.INFO,
            ActionSeverity.WARNING: logging.WARNING,
            ActionSeverity.ERROR: logging.ERROR,
            ActionSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.INFO)
        
        logger.log(log_level, log_msg)
        
        # Armazena histórico
        if self.enable_history and self._action_history is not None:
            with self._lock:
                self._action_history.append(record)
                if len(self._action_history) > self.history_max_size:
                    self._action_history.pop(0)
                
                # Persiste se configurado
                if self.persist_history and len(self._action_history) % 10 == 0:
                    self._save_history()
        
        # Executa hooks
        self._run_hooks(action, status, record)
    
    def _run_hooks(self, action: str, status: ActionStatus, record: ActionRecord) -> None:
        """Executa hooks registrados para a ação."""
        for hook in self._hooks.get(action, []):
            try:
                hook(record)
            except Exception as e:
                logger.warning(f"Hook falhou para {action}: {e}")
    
    def register_hook(self, action: str, hook: Callable[[ActionRecord], None]) -> None:
        """Registra um hook para ser executado após uma ação."""
        self._hooks[action].append(hook)
    
    def get_action_history(self, limit: Optional[int] = None, 
                           status: Optional[ActionStatus] = None,
                           action_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna o histórico de ações filtrado.
        
        Args:
            limit: Número máximo de ações retornadas
            status: Filtrar por status
            action_name: Filtrar por nome da ação
        """
        if not self.enable_history:
            logger.warning(f"{self.__class__.__name__}: histórico não está habilitado.")
            return []
        
        with self._lock:
            records = self._action_history.copy()
        
        # Aplica filtros
        if status:
            records = [r for r in records if r.status == status]
        if action_name:
            records = [r for r in records if r.name == action_name]
        
        # Limita
        if limit:
            records = records[-limit:]
        
        return [r.to_dict() for r in records]
    
    def get_metrics(self, action_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retorna métricas de performance.
        
        Args:
            action_name: Nome específico da ação (ou todas se None)
        """
        with self._lock:
            if action_name:
                metrics = self._metrics.get(action_name, {})
                return {
                    "action": action_name,
                    **metrics,
                    "success_rate": metrics.get("success", 0) / max(1, metrics.get("count", 0))
                }
            else:
                return {
                    action: {
                        **m,
                        "success_rate": m.get("success", 0) / max(1, m.get("count", 0))
                    }
                    for action, m in self._metrics.items()
                }
    
    def log_error(
        self,
        action: str,
        error: Exception,
        params: Optional[Dict] = None,
        severity: ActionSeverity = ActionSeverity.ERROR
    ) -> None:
        """
        Registra um erro ocorrido durante uma ação.
        """
        error_details = {
            "error_type": type(error).__name__,
            "error_msg": str(error),
            "traceback": traceback.format_exc()[:500]
        }
        if params:
            error_details.update(params)
        
        self.log_action(
            action,
            status=ActionStatus.ERROR,
            params=error_details,
            error=str(error),
            severity=severity
        )
    
    def reset_metrics(self) -> None:
        """Reseta todas as métricas."""
        with self._lock:
            self._metrics.clear()
            logger.info(f"{self.__class__.__name__}: métricas resetadas")
    
    def clear_history(self) -> None:
        """Limpa o histórico de ações."""
        if self.enable_history and self._action_history is not None:
            with self._lock:
                self._action_history.clear()
                if self.persist_history:
                    self._save_history()
            logger.info(f"{self.__class__.__name__}: histórico limpo")
    
    @track_action(severity=ActionSeverity.DEBUG)
    def execute(self, action: str, **kwargs) -> Any:
        """
        Método genérico para executar uma ação no atuador.
        
        Por padrão, levanta NotImplementedError. Subclasses podem implementar
        um dispatcher para ações comuns.
        """
        # Tenta encontrar método específico
        method_name = f"action_{action}"
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            return getattr(self, method_name)(**kwargs)
        
        raise NotImplementedError(
            f"{self.__class__.__name__} não implementa ação '{action}'"
        )
    
    def get_supported_actions(self) -> List[str]:
        """Retorna lista de ações suportadas pelo atuador."""
        actions = []
        for attr_name in dir(self):
            if attr_name.startswith("action_"):
                actions.append(attr_name[7:])
        return actions
    
    def _get_action_params(self, *args, **kwargs) -> Dict[str, Any]:
        """Hook para subclasses extraírem parâmetros de ação."""
        return {"args": args, "kwargs": kwargs}
    
    @property
    def health_status(self) -> Dict[str, Any]:
        """Retorna status de saúde do atuador."""
        return {
            "actuator": self.__class__.__name__,
            "healthy": True,
            "history_size": len(self._action_history) if self._action_history else 0,
            "metrics_count": len(self._metrics),
            "hooks_count": sum(len(h) for h in self._hooks.values()),
            "timestamp": datetime.now().isoformat()
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sysaware={self.sysaware is not None}, history={self.enable_history})"


# =============================================================================
= Exemplo de Implementação de Atuador
# =============================================================================

class ExampleActuator(BaseActuator):
    """Exemplo de implementação de um atuador concreto."""
    
    def _check_dependencies(self) -> None:
        """Verifica dependências do atuador de exemplo."""
        # Exemplo: verificar se uma biblioteca está disponível
        try:
            import time  # sempre disponível
        except ImportError:
            raise ImportError("Biblioteca time não disponível (isso nunca deve acontecer)")
    
    def action_hello(self, name: str = "World") -> str:
        """Ação de exemplo: diz olá."""
        return f"Hello, {name}!"
    
    def action_sleep(self, seconds: float = 1.0) -> None:
        """Ação de exemplo: dorme por alguns segundos."""
        time.sleep(seconds)
    
    def _get_action_params(self, *args, **kwargs) -> Dict[str, Any]:
        """Extrai parâmetros de forma mais específica."""
        # Exemplo: extrai apenas o primeiro argumento se for nome
        if args:
            return {"name": args[0]}
        return kwargs


# =============================================================================
= Demonstração
# =============================================================================

def main():
    """Demonstração do sistema base de atuadores."""
    import time
    
    # Configura logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    
    print("\n" + "=" * 60)
    print("🔱 ATENA Base Actuators Framework - Demonstração")
    print("=" * 60)
    
    # Cria atuador de exemplo
    actuator = ExampleActuator(enable_history=True, persist_history=True)
    
    # Executa ações
    print("\n📋 Executando ações...")
    
    result = actuator.execute("hello", name="ATENA")
    print(f"  Resultado: {result}")
    
    actuator.execute("sleep", seconds=0.5)
    print("  Sleep executado")
    
    # Verifica métricas
    print("\n📊 Métricas:")
    metrics = actuator.get_metrics()
    for action, m in metrics.items():
        print(f"  {action}: {m['count']} execuções, {m['success_rate']:.1%} sucesso, média {m['avg_duration_ms']:.1f}ms")
    
    # Verifica histórico
    print("\n📜 Histórico (últimas 3):")
    history = actuator.get_action_history(limit=3)
    for h in history:
        print(f"  {h['name']}: {h['status']} ({h['duration_ms']:.2f}ms) - {h['timestamp'][:19]}")
    
    # Health check
    print("\n🩺 Health Status:")
    health = actuator.health_status
    for k, v in health.items():
        print(f"  {k}: {v}")
    
    print("\n✅ Demonstração concluída!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
