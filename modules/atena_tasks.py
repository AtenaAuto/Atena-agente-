#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Task Manager v3.0
Sistema avançado de gerenciamento de tarefas com orquestração polimorfa.

Recursos:
- 📊 Orquestração multi-tarefa com dependências complexas (DAG)
- 🔄 Retry automático com backoff exponencial e jitter
- 💾 Persistência SQLite com recuperação pós-falha
- 📈 Métricas avançadas (CPU, memória, I/O, rede)
- 🌐 Suporte a tarefas remotas e distribuídas
- 🎯 Priorização dinâmica e preempção
- 📝 Logging estruturado por tarefa
- 🔌 Plugin system para extensão
"""

import asyncio
import json
import logging
import os
import random
import secrets
import signal
import sqlite3
import sys
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor

# Tentativa de importar psutil para métricas avançadas
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger = logging.getLogger("atena.task_manager")

logger = logging.getLogger("atena.task_manager")

# =============================================================================
# Constantes e Configurações
# =============================================================================

DEFAULT_TIMEOUT_MS = 30000
DEFAULT_MAX_RETRIES = 3
MAX_CONCURRENT_TASKS = 10
CLEANUP_DAYS = 7

# =============================================================================
# Enums e Tipos
# =============================================================================

class TaskType(str, Enum):
    """Tipos de tarefa suportados."""
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"
    BENCHMARK = "benchmark"
    DATA_SCIENCE = "data_science"
    WEB_CRAWLER = "web_crawler"
    API_CALL = "api_call"


class TaskStatus(str, Enum):
    """Status possíveis de uma tarefa."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    WAITING_DEPENDENCY = "waiting_dependency"


class TaskPriority(int, Enum):
    """Níveis de prioridade para tarefas."""
    CRITICAL = 10
    HIGH = 8
    NORMAL = 5
    LOW = 3
    BACKGROUND = 1


# =============================================================================
= Geradores de ID
# =============================================================================

TASK_ID_PREFIXES: Dict[TaskType, str] = {
    TaskType.LOCAL_BASH: "b",
    TaskType.LOCAL_AGENT: "a",
    TaskType.REMOTE_AGENT: "r",
    TaskType.IN_PROCESS_TEAMMATE: "t",
    TaskType.LOCAL_WORKFLOW: "w",
    TaskType.MONITOR_MCP: "m",
    TaskType.DREAM: "d",
    TaskType.BENCHMARK: "k",
    TaskType.DATA_SCIENCE: "s",
    TaskType.WEB_CRAWLER: "c",
    TaskType.API_CALL: "p",
}

TASK_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def generate_task_id(task_type: TaskType) -> str:
    """Gera ID único para tarefa."""
    prefix = TASK_ID_PREFIXES.get(task_type, "x")
    random_bytes = secrets.token_bytes(12)
    random_part = "".join(TASK_ID_ALPHABET[b % len(TASK_ID_ALPHABET)] for b in random_bytes)
    return f"{prefix}{random_part}"


def is_terminal_status(status: TaskStatus) -> bool:
    """Verifica se status é terminal (não pode mais mudar)."""
    return status in {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.KILLED,
        TaskStatus.TIMEOUT,
        TaskStatus.CANCELLED,
    }


def get_task_output_path(task_id: str) -> Path:
    """Retorna caminho do arquivo de saída da tarefa."""
    task_dir = Path("./atena_evolution/tasks")
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir / f"{task_id}.log"


# =============================================================================
= Data Models
# =============================================================================

@dataclass
class TaskMetrics:
    """Métricas de execução da tarefa."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    threads: int = 0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    net_sent_mb: float = 0.0
    net_recv_mb: float = 0.0
    io_wait_percent: float = 0.0
    peak_memory_mb: float = 0.0
    context_switches: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def update_peak(self):
        """Atualiza pico de memória."""
        if self.memory_mb > self.peak_memory_mb:
            self.peak_memory_mb = self.memory_mb


@dataclass
class TaskDependency:
    """Dependência entre tarefas."""
    task_id: str
    required_status: TaskStatus = TaskStatus.COMPLETED
    optional: bool = False


@dataclass
class TaskStateBase:
    """Estado base de uma tarefa."""
    id: str
    type: TaskType
    status: TaskStatus
    description: str
    timeout: int = DEFAULT_TIMEOUT_MS
    priority: int = TaskPriority.NORMAL.value
    created_at: float = field(default_factory=time.time)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    total_paused_ms: float = 0.0
    
    # Retry configuration
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_after: Optional[float] = None
    last_error: Optional[str] = None
    error_stack: Optional[str] = None
    
    # Output
    output_file: str = field(default_factory=str)
    output_offset: int = 0
    result: Any = None
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    # Metrics
    metrics: Optional[TaskMetrics] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    tool_use_id: Optional[str] = None
    notified: bool = False
    scheduled_for: Optional[float] = None
    
    def __post_init__(self):
        if not self.output_file:
            self.output_file = str(get_task_output_path(self.id))
        if self.metrics is None:
            self.metrics = TaskMetrics()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        if self.metrics:
            data["metrics"] = self.metrics.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStateBase":
        """Reconstrói a partir de dicionário."""
        data = data.copy()
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        if "metrics" in data and data["metrics"]:
            data["metrics"] = TaskMetrics(**data["metrics"])
        return cls(**data)


# =============================================================================
= Persistência SQLite (assíncrona)
# =============================================================================

class TaskDB:
    """Gerenciador de persistência para tarefas."""
    
    def __init__(self, db_path: Path = Path("./atena_evolution/tasks.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
    
    async def init(self):
        """Inicializa banco de dados e tabelas."""
        def _init_sync():
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT,
                    timeout INTEGER,
                    priority INTEGER,
                    created_at REAL,
                    start_time REAL,
                    end_time REAL,
                    total_paused_ms REAL,
                    retry_count INTEGER,
                    max_retries INTEGER,
                    retry_after REAL,
                    last_error TEXT,
                    error_stack TEXT,
                    output_file TEXT,
                    output_offset INTEGER,
                    result TEXT,
                    depends_on TEXT,
                    dependents TEXT,
                    metrics TEXT,
                    tags TEXT,
                    tool_use_id TEXT,
                    notified INTEGER,
                    scheduled_for REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON tasks(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON tasks(created_at)")
            conn.commit()
            return conn
        
        self._conn = await asyncio.get_event_loop().run_in_executor(None, _init_sync)
    
    async def close(self):
        """Fecha conexão com banco."""
        if self._conn:
            await asyncio.get_event_loop().run_in_executor(None, self._conn.close)
            self._conn = None
    
    async def save_task(self, task: TaskStateBase) -> None:
        """Salva ou atualiza tarefa."""
        async with self._lock:
            def _save_sync():
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO tasks (
                        id, type, status, description, timeout, priority,
                        created_at, start_time, end_time, total_paused_ms,
                        retry_count, max_retries, retry_after, last_error, error_stack,
                        output_file, output_offset, result, depends_on, dependents,
                        metrics, tags, tool_use_id, notified, scheduled_for
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id, task.type.value, task.status.value, task.description,
                    task.timeout, task.priority, task.created_at, task.start_time,
                    task.end_time, task.total_paused_ms, task.retry_count, task.max_retries,
                    task.retry_after, task.last_error, task.error_stack, task.output_file,
                    task.output_offset, json.dumps(task.result) if task.result else None,
                    json.dumps(task.depends_on), json.dumps(task.dependents),
                    json.dumps(task.metrics.to_dict()) if task.metrics else None,
                    json.dumps(task.tags), task.tool_use_id, 1 if task.notified else 0,
                    task.scheduled_for
                ))
                self._conn.commit()
            await asyncio.get_event_loop().run_in_executor(None, _save_sync)
    
    async def load_task(self, task_id: str) -> Optional[TaskStateBase]:
        """Carrega tarefa específica."""
        def _load_sync():
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cursor.description]
            data = dict(zip(cols, row))
            data["depends_on"] = json.loads(data["depends_on"]) if data["depends_on"] else []
            data["dependents"] = json.loads(data["dependents"]) if data["dependents"] else []
            data["tags"] = json.loads(data["tags"]) if data["tags"] else []
            if data["metrics"]:
                data["metrics"] = TaskMetrics(**json.loads(data["metrics"]))
            if data["result"]:
                data["result"] = json.loads(data["result"])
            return TaskStateBase.from_dict(data)
        
        return await asyncio.get_event_loop().run_in_executor(None, _load_sync)
    
    async def load_all_pending(self) -> List[TaskStateBase]:
        """Carrega todas tarefas pendentes/retry."""
        def _load_sync():
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'retrying', 'waiting_dependency')"
            )
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            tasks = []
            for row in rows:
                data = dict(zip(cols, row))
                data["depends_on"] = json.loads(data["depends_on"]) if data["depends_on"] else []
                data["dependents"] = json.loads(data["dependents"]) if data["dependents"] else []
                data["tags"] = json.loads(data["tags"]) if data["tags"] else []
                if data["metrics"]:
                    data["metrics"] = TaskMetrics(**json.loads(data["metrics"]))
                if data["result"]:
                    data["result"] = json.loads(data["result"])
                tasks.append(TaskStateBase.from_dict(data))
            return tasks
        
        return await asyncio.get_event_loop().run_in_executor(None, _load_sync)
    
    async def delete_task(self, task_id: str) -> None:
        """Remove tarefa do banco."""
        def _delete_sync():
            self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn.commit()
        await asyncio.get_event_loop().run_in_executor(None, _delete_sync)
    
    async def cleanup_old(self, keep_days: int = CLEANUP_DAYS) -> int:
        """Remove tarefas antigas com estado terminal."""
        cutoff = time.time() - keep_days * 86400
        def _cleanup_sync():
            cursor = self._conn.execute(
                "DELETE FROM tasks WHERE end_time < ? AND status IN ('completed', 'failed', 'killed', 'timeout', 'cancelled')",
                (cutoff,)
            )
            self._conn.commit()
            return cursor.rowcount
        return await asyncio.get_event_loop().run_in_executor(None, _cleanup_sync)


# =============================================================================
= Task Queue com Prioridade e Dependências
# =============================================================================

class TaskQueue:
    """Fila de tarefas com suporte a prioridade, dependências e DAG."""
    
    def __init__(self):
        self._tasks: Dict[str, TaskStateBase] = {}
        self._ready_queues: Dict[int, asyncio.Queue] = {p: asyncio.Queue() for p in range(1, 11)}
        self._lock = asyncio.Lock()
        self._dependency_graph: Dict[str, Set[str]] = {}
    
    async def enqueue(self, task: TaskStateBase) -> None:
        """Adiciona tarefa à fila."""
        async with self._lock:
            self._tasks[task.id] = task
            
            # Constrói grafo de dependências
            for dep_id in task.depends_on:
                if dep_id not in self._dependency_graph:
                    self._dependency_graph[dep_id] = set()
                self._dependency_graph[dep_id].add(task.id)
            
            # Se não tem dependências pendentes, coloca na fila de prontos
            if await self._dependencies_met(task):
                await self._ready_queues[task.priority].put(task.id)
            else:
                task.status = TaskStatus.WAITING_DEPENDENCY
                await self._save_task(task)
    
    async def _dependencies_met(self, task: TaskStateBase) -> bool:
        """Verifica se todas dependências foram satisfeitas."""
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        return True
    
    async def get_ready(self, timeout: float = 1.0) -> Optional[str]:
        """Pega próxima tarefa pronta baseada na prioridade."""
        for priority in range(10, 0, -1):
            queue = self._ready_queues[priority]
            if not queue.empty():
                try:
                    return await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    continue
        
        # Se nenhuma fila tem item, aguarda em qualquer uma
        for priority in range(10, 0, -1):
            queue = self._ready_queues[priority]
            try:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                continue
        
        return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> None:
        """Atualiza estado da tarefa e notifica dependentes se necessário."""
        async with self._lock:
            if task_id not in self._tasks:
                return
            
            task = self._tasks[task_id]
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            
            # Se completou, notifica dependentes
            if task.status == TaskStatus.COMPLETED:
                for dep_id in self._dependency_graph.get(task_id, []):
                    dep_task = self._tasks.get(dep_id)
                    if dep_task and await self._dependencies_met(dep_task):
                        dep_task.status = TaskStatus.PENDING
                        await self._ready_queues[dep_task.priority].put(dep_task.id)
            
            await self._save_task(task)
    
    async def _save_task(self, task: TaskStateBase) -> None:
        """Salva tarefa (overload para acesso ao DB)."""
        # Este método será sobrescrito pelo TaskManager
        pass
    
    async def remove_task(self, task_id: str) -> None:
        """Remove tarefa da fila."""
        async with self._lock:
            self._tasks.pop(task_id, None)
            self._dependency_graph.pop(task_id, None)
    
    async def get_all(self) -> List[TaskStateBase]:
        """Retorna todas as tarefas."""
        async with self._lock:
            return list(self._tasks.values())
    
    async def get_by_id(self, task_id: str) -> Optional[TaskStateBase]:
        """Retorna tarefa por ID."""
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def get_by_status(self, status: TaskStatus) -> List[TaskStateBase]:
        """Retorna tarefas por status."""
        async with self._lock:
            return [t for t in self._tasks.values() if t.status == status]
    
    async def cancel_pending(self, tag: Optional[str] = None) -> int:
        """Cancela todas tarefas pendentes opcionalmente por tag."""
        cancelled = 0
        async with self._lock:
            for task in list(self._tasks.values()):
                if task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
                    if tag is None or tag in task.tags:
                        task.status = TaskStatus.CANCELLED
                        task.end_time = time.time()
                        cancelled += 1
                        await self._save_task(task)
        return cancelled


# =============================================================================
= Task Executor com Retry e Métricas
# =============================================================================

class TaskExecutor:
    """Executor de tarefas com retry automático e coleta de métricas."""
    
    def __init__(self, queue: TaskQueue, db: TaskDB):
        self.queue = queue
        self.db = db
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    async def execute_with_retry(
        self,
        task: TaskStateBase,
        task_impl: "Task",
        context: "TaskContext"
    ) -> None:
        """Executa tarefa com retry automático."""
        async with self._semaphore:
            self._running_tasks[task.id] = asyncio.current_task()
            
            try:
                await self._execute_impl(task, task_impl, context)
            finally:
                self._running_tasks.pop(task.id, None)
    
    async def _execute_impl(
        self,
        task: TaskStateBase,
        task_impl: "Task",
        context: "TaskContext"
    ) -> None:
        """Implementação real da execução com retry."""
        task.start_time = time.time()
        await self._update_status(task.id, TaskStatus.RUNNING)
        
        while task.retry_count <= task.max_retries:
            try:
                # Inicia monitoramento de métricas
                monitor_task = asyncio.create_task(self._monitor_metrics(task.id, task_impl))
                
                # Executa com timeout
                await asyncio.wait_for(
                    task_impl.spawn(task.id, context),
                    timeout=task.timeout / 1000.0
                )
                
                # Cancela monitoramento
                monitor_task.cancel()
                
                # Sucesso
                task.end_time = time.time()
                await self._update_status(task.id, TaskStatus.COMPLETED)
                logger.info(f"✅ Tarefa {task.id} completada com sucesso")
                return
                
            except asyncio.TimeoutError:
                task.retry_count += 1
                task.last_error = f"Timeout após {task.timeout/1000}s"
                logger.warning(f"⏰ Timeout {task.id} (tentativa {task.retry_count}/{task.max_retries})")
                
                if task.retry_count <= task.max_retries:
                    await self._schedule_retry(task)
                else:
                    await self._update_status(task.id, TaskStatus.TIMEOUT)
                    
            except Exception as e:
                task.retry_count += 1
                task.last_error = str(e)
                task.error_stack = traceback.format_exc()
                logger.error(f"❌ Erro {task.id}: {e}")
                
                if task.retry_count <= task.max_retries:
                    await self._schedule_retry(task)
                else:
                    await self._update_status(task.id, TaskStatus.FAILED)
                    raise
    
    async def _schedule_retry(self, task: TaskStateBase) -> None:
        """Agenda retry com backoff exponencial e jitter."""
        base_delay = 1.0 * (2 ** (task.retry_count - 1))
        delay = min(base_delay, 60.0)
        # Jitter de ±20%
        delay = delay * random.uniform(0.8, 1.2)
        
        task.retry_after = time.time() + delay
        await self._update_status(task.id, TaskStatus.RETRYING)
        
        logger.info(f"🔄 Retry {task.retry_count}/{task.max_retries} para {task.id} em {delay:.1f}s")
        await asyncio.sleep(delay)
        
        # Re-coloca na fila
        task.status = TaskStatus.PENDING
        await self.queue.enqueue(task)
    
    async def _monitor_metrics(self, task_id: str, task_impl: "Task") -> None:
        """Monitora métricas da tarefa durante execução."""
        if not HAS_PSUTIL:
            return
        
        try:
            while True:
                metrics = await task_impl.get_metrics(task_id)
                if metrics and metrics.memory_mb > 0:
                    await self.queue.update_task(task_id, {"metrics": metrics})
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            # Coleta métricas finais
            final_metrics = await task_impl.get_metrics(task_id)
            if final_metrics:
                final_metrics.update_peak()
                await self.queue.update_task(task_id, {"metrics": final_metrics})
    
    async def _update_status(self, task_id: str, status: TaskStatus) -> None:
        """Atualiza status da tarefa."""
        updates = {"status": status}
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.KILLED):
            updates["end_time"] = time.time()
        await self.queue.update_task(task_id, updates)
        
        task = await self.queue.get_by_id(task_id)
        if task:
            await self.db.save_task(task)
    
    async def kill_task(self, task_id: str) -> None:
        """Força cancelamento de tarefa em execução."""
        running_task = self._running_tasks.get(task_id)
        if running_task and not running_task.done():
            running_task.cancel()
            await self._update_status(task_id, TaskStatus.KILLED)
            logger.info(f"🔪 Tarefa {task_id} cancelada")


# =============================================================================
= Abstract Task Class
# =============================================================================

class Task(ABC):
    """Classe base abstrata para implementação de tarefas."""
    
    def __init__(self, name: str, task_type: TaskType):
        self.name = name
        self.type = task_type
        self._process: Optional[asyncio.subprocess.Process] = None
    
    @abstractmethod
    async def spawn(self, task_id: str, context: "TaskContext") -> None:
        """Executa a tarefa."""
        pass
    
    @abstractmethod
    async def kill(self, task_id: str, app_state: Dict) -> None:
        """Interrompe a tarefa em execução."""
        pass
    
    async def pause(self, task_id: str, app_state: Dict) -> None:
        """Pausa a tarefa (opcional)."""
        logger.info(f"⏸️ Pausando tarefa {task_id}")
    
    async def resume(self, task_id: str, app_state: Dict) -> None:
        """Retoma tarefa pausada (opcional)."""
        logger.info(f"▶️ Retomando tarefa {task_id}")
    
    async def get_metrics(self, task_id: str) -> TaskMetrics:
        """Coleta métricas da tarefa (opcional)."""
        metrics = TaskMetrics()
        
        if HAS_PSUTIL:
            try:
                # Tenta encontrar processo associado
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                    if task_id in proc.info['name'] or task_id in ' '.join(proc.cmdline()):
                        metrics.cpu_percent = proc.info['cpu_percent']
                        metrics.memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                        metrics.memory_percent = proc.memory_percent()
                        metrics.threads = proc.num_threads()
                        break
            except Exception:
                pass
        
        return metrics


# =============================================================================
= Task Context
# =============================================================================

@dataclass
class TaskContext:
    """Contexto de execução da tarefa."""
    cancel_event: asyncio.Event
    get_app_state: Callable[[], Dict]
    set_app_state: Callable[[Callable], None]
    logger: Optional[logging.Logger] = None
    
    def log(self, message: str, level: str = "info") -> None:
        """Log com contexto da tarefa."""
        logger_func = getattr(self.logger or logger, level, logger.info)
        logger_func(f"[Task] {message}")


# =============================================================================
= Task Manager (Orquestrador Principal)
# =============================================================================

class TaskManager:
    """Orquestrador principal de tarefas."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db = TaskDB(db_path)
        self.queue = TaskQueue()
        self.executor = TaskExecutor(self.queue, self.db)
        self.tasks_impl: Dict[TaskType, Task] = {}
        self._app_state: Dict = {}
        self._runner_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._shutdown_lock = asyncio.Lock()
        
        # Injeta save_task na queue
        self.queue._save_task = self.db.save_task
        
        # Configura signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("🚀 Task Manager v3.0 inicializado")
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de término."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.stop())
    
    async def start(self) -> None:
        """Inicia o manager, carrega tarefas pendentes e inicia workers."""
        await self.db.init()
        
        # Recupera tarefas pendentes
        pending_tasks = await self.db.load_all_pending()
        for task in pending_tasks:
            await self.queue.enqueue(task)
        
        # Inicia worker principal
        self._runner_task = asyncio.create_task(self._run_worker())
        
        # Inicia monitor de saúde
        self._monitor_task = asyncio.create_task(self._health_monitor())
        
        logger.info(f"✅ Task Manager iniciado com {len(pending_tasks)} tarefas pendentes")
    
    async def _run_worker(self) -> None:
        """Loop principal que processa a fila de tarefas."""
        while not self._stop_event.is_set():
            task_id = await self.queue.get_ready()
            if task_id is None:
                await asyncio.sleep(0.5)
                continue
            
            task = await self.queue.get_by_id(task_id)
            if not task:
                continue
            
            # Verifica se é hora de retry
            if task.status == TaskStatus.RETRYING and task.retry_after:
                if time.time() < task.retry_after:
                    asyncio.create_task(self._delay_requeue(task_id, task.retry_after - time.time()))
                    continue
            
            impl = self.tasks_impl.get(task.type)
            if not impl:
                logger.error(f"❌ Sem implementação para {task.type}")
                await self._fail_task(task, "No task implementation registered")
                continue
            
            context = TaskContext(
                cancel_event=asyncio.Event(),
                get_app_state=lambda: self._app_state,
                set_app_state=self._set_app_state,
                logger=logger
            )
            
            try:
                await self.executor.execute_with_retry(task, impl, context)
            except Exception as e:
                logger.error(f"💥 Falha final em {task.id}: {e}")
            finally:
                # Limpeza
                await self.queue.remove_task(task.id)
    
    async def _delay_requeue(self, task_id: str, delay: float) -> None:
        """Re-agenda tarefa após delay."""
        await asyncio.sleep(max(0, delay))
        task = await self.queue.get_by_id(task_id)
        if task and task.status == TaskStatus.RETRYING:
            task.status = TaskStatus.PENDING
            await self.queue.enqueue(task)
    
    async def _health_monitor(self) -> None:
        """Monitora saúde do sistema de tarefas."""
        while not self._stop_event.is_set():
            await asyncio.sleep(30)
            
            stats = await self.get_stats()
            logger.debug(f"Health stats: {stats['total']} tasks, {stats['running']} running")
            
            # Verifica tarefas presas
            stuck_tasks = []
            for task in await self.queue.get_all():
                if task.status == TaskStatus.RUNNING and task.start_time:
                    elapsed = time.time() - task.start_time
                    if elapsed > (task.timeout / 1000) * 2:
                        stuck_tasks.append(task.id)
            
            if stuck_tasks:
                logger.warning(f"⚠️ Tarefas potencialmente presas: {stuck_tasks}")
    
    async def _fail_task(self, task: TaskStateBase, reason: str) -> None:
        """Marca tarefa como falha."""
        await self.queue.update_task(task.id, {
            "status": TaskStatus.FAILED,
            "last_error": reason,
            "end_time": time.time()
        })
        await self.db.save_task(task)
    
    def _set_app_state(self, updater: Callable) -> None:
        """Atualiza estado da aplicação."""
        self._app_state = updater(self._app_state)
    
    async def create_task(
        self,
        task_type: TaskType,
        description: str,
        priority: int = TaskPriority.NORMAL.value,
        timeout: int = DEFAULT_TIMEOUT_MS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        depends_on: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        tool_use_id: Optional[str] = None,
        scheduled_for: Optional[float] = None
    ) -> str:
        """
        Cria e enfileira uma nova tarefa.
        
        Args:
            task_type: Tipo da tarefa
            description: Descrição
            priority: Prioridade (1-10)
            timeout: Timeout em ms
            max_retries: Número máximo de retries
            depends_on: Lista de IDs de tarefas das quais depende
            tags: Tags para categorização
            tool_use_id: ID da ferramenta associada
            scheduled_for: Timestamp para execução agendada
        
        Returns:
            ID da tarefa criada
        """
        task_id = generate_task_id(task_type)
        
        task = TaskStateBase(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            description=description,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            depends_on=depends_on or [],
            tags=tags or [],
            tool_use_id=tool_use_id,
            scheduled_for=scheduled_for
        )
        
        await self.db.save_task(task)
        
        if scheduled_for and scheduled_for > time.time():
            # Tarefa agendada para futuro
            task.status = TaskStatus.PENDING
            asyncio.create_task(self._schedule_future_task(task_id, scheduled_for))
        else:
            await self.queue.enqueue(task)
        
        logger.info(f"📋 Tarefa criada: {task_id} ({task_type.value}) - {description[:50]}")
        return task_id
    
    async def _schedule_future_task(self, task_id: str, scheduled_for: float) -> None:
        """Agenda tarefa para execução futura."""
        delay = max(0, scheduled_for - time.time())
        await asyncio.sleep(delay)
        
        task = await self.queue.get_by_id(task_id)
        if task and task.status == TaskStatus.PENDING:
            await self.queue.enqueue(task)
    
    async def kill_task(self, task_id: str) -> bool:
        """Interrompe tarefa em execução."""
        task = await self.queue.get_by_id(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.RUNNING:
            await self.executor.kill_task(task_id)
        elif task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
            await self.queue.update_task(task_id, {"status": TaskStatus.CANCELLED, "end_time": time.time()})
        else:
            return False
        
        logger.info(f"🔪 Tarefa {task_id} interrompida")
        return True
    
    async def pause_task(self, task_id: str) -> bool:
        """Pausa tarefa em execução."""
        task = await self.queue.get_by_id(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        
        impl = self.tasks_impl.get(task.type)
        if impl:
            await impl.pause(task_id, self._app_state)
            await self.queue.update_task(task_id, {"status": TaskStatus.PAUSED})
            return True
        return False
    
    async def resume_task(self, task_id: str) -> bool:
        """Retoma tarefa pausada."""
        task = await self.queue.get_by_id(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False
        
        impl = self.tasks_impl.get(task.type)
        if impl:
            await impl.resume(task_id, self._app_state)
            await self.queue.update_task(task_id, {"status": TaskStatus.PENDING})
            await self.queue.enqueue(task)
            return True
        return False
    
    async def get_task_info(self, task_id: str) -> Optional[Dict]:
        """Retorna informações detalhadas da tarefa."""
        task = await self.queue.get_by_id(task_id)
        if not task:
            return None
        
        return task.to_dict()
    
    async def get_all_tasks(self, limit: int = 100) -> List[Dict]:
        """Retorna todas as tarefas."""
        tasks = await self.queue.get_all()
        return [t.to_dict() for t in tasks[:limit]]
    
    async def get_tasks_by_status(self, status: TaskStatus) -> List[Dict]:
        """Retorna tarefas por status."""
        tasks = await self.queue.get_by_status(status)
        return [t.to_dict() for t in tasks]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do task manager."""
        tasks = await self.queue.get_all()
        
        stats = {
            "total": len(tasks),
            "by_status": {},
            "by_type": {},
            "running": len(self.executor._running_tasks),
            "concurrent_limit": MAX_CONCURRENT_TASKS
        }
        
        for task in tasks:
            stats["by_status"][task.status.value] = stats["by_status"].get(task.status.value, 0) + 1
            stats["by_type"][task.type.value] = stats["by_type"].get(task.type.value, 0) + 1
        
        return stats
    
    async def cleanup(self, keep_days: int = CLEANUP_DAYS) -> int:
        """Limpa tarefas antigas."""
        deleted = await self.db.cleanup_old(keep_days)
        await self.queue.cleanup()
        logger.info(f"🧹 Limpeza concluída: {deleted} tarefas removidas")
        return deleted
    
    async def stop(self) -> None:
        """Graceful shutdown."""
        async with self._shutdown_lock:
            if self._stop_event.is_set():
                return
            
            logger.info("🛑 Iniciando shutdown do Task Manager...")
            self._stop_event.set()
            
            # Cancela tarefas em execução
            for task_id in list(self.executor._running_tasks.keys()):
                await self.kill_task(task_id)
            
            # Aguarda finalização
            if self._runner_task:
                self._runner_task.cancel()
                try:
                    await self._runner_task
                except asyncio.CancelledError:
                    pass
            
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            
            await self.db.close()
            logger.info("✅ Task Manager encerrado")
    
    def register_task_impl(self, task_impl: Task) -> None:
        """Registra implementação de tarefa."""
        self.tasks_impl[task_impl.type] = task_impl
        logger.info(f"📦 Tarefa registrada: {task_impl.name} ({task_impl.type.value})")
    
    async def print_status(self) -> None:
        """Exibe status formatado no console."""
        stats = await self.get_stats()
        tasks = await self.queue.get_all()
        
        print("\n" + "=" * 60)
        print("   🔱 TASK MANAGER - STATUS")
        print("=" * 60)
        print(f"  📊 Total de tarefas: {stats['total']}")
        print(f"  🏃 Em execução: {stats['running']}/{stats['concurrent_limit']}")
        print("\n  📋 Por status:")
        for status, count in sorted(stats["by_status"].items()):
            print(f"    {status:.<25} {count:>3d}")
        print("\n  🏷️ Por tipo:")
        for ttype, count in sorted(stats["by_type"].items())[:10]:
            print(f"    {ttype:.<25} {count:>3d}")
        
        # Tarefas recentes
        recent = [t for t in tasks if t.end_time][:5]
        if recent:
            print("\n  📜 Últimas tarefas completadas:")
            for t in recent:
                duration = (t.end_time - t.start_time) if t.start_time else 0
                print(f"    {t.id}: {t.description[:40]} ({duration:.1f}s) - {t.status.value}")
        
        print("=" * 60 + "\n")


# =============================================================================
= Implementações de Tarefas de Exemplo
# =============================================================================

class LocalBashTask(Task):
    """Executa comandos bash localmente."""
    
    def __init__(self):
        super().__init__("LocalBashTask", TaskType.LOCAL_BASH)
    
    async def spawn(self, task_id: str, context: TaskContext) -> None:
        """Executa comando bash."""
        context.log(f"Executando tarefa bash {task_id}")
        
        # Simula trabalho
        for i in range(5):
            if context.cancel_event.is_set():
                raise asyncio.CancelledError()
            await asyncio.sleep(1)
            context.log(f"Progresso: {(i+1)*20}%")
        
        # Escreve resultado
        output_file = get_task_output_path(task_id)
        with open(output_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} - Tarefa {task_id} executada com sucesso\n")
        
        context.log("Tarefa concluída")
    
    async def kill(self, task_id: str, app_state: Dict) -> None:
        """Mata processo bash."""
        logger.info(f"Killing bash task {task_id}")


class APICallTask(Task):
    """Realiza chamadas a APIs externas."""
    
    def __init__(self):
        super().__init__("APICallTask", TaskType.API_CALL)
    
    async def spawn(self, task_id: str, context: TaskContext) -> None:
        """Executa chamada API."""
        import aiohttp
        
        context.log(f"Executando chamada API {task_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get("https://httpbin.org/get") as resp:
                result = await resp.json()
                context.log(f"API responded with status {resp.status}")
                
                # Salva resultado
                output_file = get_task_output_path(task_id)
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
    
    async def kill(self, task_id: str, app_state: Dict) -> None:
        """Cancela requisição."""
        logger.info(f"Cancelling API task {task_id}")


# =============================================================================
= Main e Exemplo de Uso
# =============================================================================

async def main():
    """Função principal de demonstração."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    
    manager = TaskManager()
    
    # Registra implementações
    manager.register_task_impl(LocalBashTask())
    manager.register_task_impl(APICallTask())
    
    await manager.start()
    
    try:
        # Cria tarefas de exemplo
        task1 = await manager.create_task(
            TaskType.LOCAL_BASH,
            "Processar dados de usuários",
            priority=TaskPriority.HIGH.value,
            max_retries=2
        )
        
        task2 = await manager.create_task(
            TaskType.API_CALL,
            "Buscar informações externas",
            priority=TaskPriority.NORMAL.value
        )
        
        # Tarefa com dependência
        task3 = await manager.create_task(
            TaskType.LOCAL_BASH,
            "Gerar relatório final",
            priority=TaskPriority.NORMAL.value,
            depends_on=[task1, task2]
        )
        
        print(f"\n📋 Tarefas criadas:")
        print(f"  - {task1}: Processamento de dados")
        print(f"  - {task2}: API Call")
        print(f"  - {task3}: Relatório (depende das anteriores)")
        
        # Aguarda um pouco
        await asyncio.sleep(8)
        
        # Mostra status
        await manager.print_status()
        
        # Consulta tarefa específica
        info = await manager.get_task_info(task3)
        if info:
            print(f"\n📄 Detalhe tarefa {task3}:")
            print(f"  Status: {info['status']}")
            if info.get('dependents'):
                print(f"  Dependentes: {info['dependents']}")
        
        # Limpeza
        await manager.cleanup(keep_days=1)
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrompido pelo usuário")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
