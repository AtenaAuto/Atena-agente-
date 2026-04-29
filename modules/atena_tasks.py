#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

         TASK MANAGER v2.1  Python                                  
  Sistema de gerenciamento de tarefas polimorfo com retry automtico  
                                                                     
  Melhorias nesta verso:                                            
    Persistncia SQLite (tarefas sobrevivem reinicializaes)       
    Worker em background que processa a fila continuamente          
    Execuo condicional baseada em dependncias                    
    Mtricas avanadas (CPU, memria, I/O) via psutil               
    Cancelamento/graceful shutdown                                  
    Jitter no backoff para evitar tempestade de retry               
    Logging estruturado por tarefa                                  

"""

import os
import secrets
import asyncio
import logging
import json
import time
import random
import sqlite3
import traceback
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable, Any, Tuple
from abc import ABC, abstractmethod
from pathlib import Path
import psutil
import aiosqlite

logger = logging.getLogger("atena.task_manager")

# 
# ENUMS E TIPOS
# 

class TaskType(str, Enum):
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"


TASK_ID_PREFIXES: Dict[TaskType, str] = {
    TaskType.LOCAL_BASH: "b",
    TaskType.LOCAL_AGENT: "a",
    TaskType.REMOTE_AGENT: "r",
    TaskType.IN_PROCESS_TEAMMATE: "t",
    TaskType.LOCAL_WORKFLOW: "w",
    TaskType.MONITOR_MCP: "m",
    TaskType.DREAM: "d",
}

TASK_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def generate_task_id(task_type: TaskType) -> str:
    prefix = TASK_ID_PREFIXES.get(task_type, "x")
    random_bytes = secrets.token_bytes(8)
    random_part = "".join(TASK_ID_ALPHABET[b % 36] for b in random_bytes)
    return f"{prefix}{random_part}"


def is_terminal_status(status: TaskStatus) -> bool:
    return status in (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.KILLED,
        TaskStatus.TIMEOUT,
    )


def get_task_output_path(task_id: str) -> Path:
    task_dir = Path("./atena_evolution/tasks")
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir / f"{task_id}.log"


# 
# DATACLASSES
# 

@dataclass
class TaskMetrics:
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    threads: int = 0
    disk_io_mb: float = 0.0
    peak_memory_mb: float = 0.0


@dataclass
class TaskStateBase:
    id: str
    type: TaskType
    status: TaskStatus
    description: str
    timeout: int = 30000  # ms
    priority: int = 5

    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_paused_ms: float = 0.0

    retry_count: int = 0
    max_retries: int = 3
    retry_after: Optional[float] = None
    last_error: Optional[str] = None
    error_stack: Optional[str] = None

    output_file: str = field(default_factory=str)
    output_offset: int = 0

    tool_use_id: Optional[str] = None
    notified: bool = False

    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    metrics: Optional[TaskMetrics] = None
    peak_memory_mb: float = 0.0

    def __post_init__(self):
        if not self.output_file:
            self.output_file = str(get_task_output_path(self.id))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        if self.metrics:
            data["metrics"] = asdict(self.metrics)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStateBase":
        data = data.copy()
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        if "metrics" in data and data["metrics"]:
            data["metrics"] = TaskMetrics(**data["metrics"])
        return cls(**data)


# 
# PERSISTNCIA SQLITE (assncrona)
# 

class TaskDB:
    def __init__(self, db_path: Path = Path("./atena_evolution/tasks.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None

    async def init(self):
        self._conn = await aiosqlite.connect(str(self.db_path))
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT,
                timeout INTEGER,
                priority INTEGER,
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
                tool_use_id TEXT,
                notified INTEGER,
                depends_on TEXT,
                dependents TEXT,
                metrics TEXT,
                peak_memory_mb REAL
            )
        """)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def save_task(self, task: TaskStateBase):
        depends_on = json.dumps(task.depends_on)
        dependents = json.dumps(task.dependents)
        metrics = json.dumps(asdict(task.metrics)) if task.metrics else None

        await self._conn.execute("""
            INSERT OR REPLACE INTO tasks (
                id, type, status, description, timeout, priority,
                start_time, end_time, total_paused_ms, retry_count, max_retries,
                retry_after, last_error, error_stack, output_file, output_offset,
                tool_use_id, notified, depends_on, dependents, metrics, peak_memory_mb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id, task.type.value, task.status.value, task.description,
            task.timeout, task.priority, task.start_time, task.end_time,
            task.total_paused_ms, task.retry_count, task.max_retries,
            task.retry_after, task.last_error, task.error_stack, task.output_file,
            task.output_offset, task.tool_use_id, 1 if task.notified else 0,
            depends_on, dependents, metrics, task.peak_memory_mb
        ))
        await self._conn.commit()

    async def load_task(self, task_id: str) -> Optional[TaskStateBase]:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        cols = [desc[0] for desc in cursor.description]
        data = dict(zip(cols, row))
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        data["depends_on"] = json.loads(data["depends_on"]) if data["depends_on"] else []
        data["dependents"] = json.loads(data["dependents"]) if data["dependents"] else []
        if data["metrics"]:
            data["metrics"] = TaskMetrics(**json.loads(data["metrics"]))
        return TaskStateBase(**data)

    async def load_all_pending(self) -> List[TaskStateBase]:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE status IN ('pending', 'retrying')"
        )
        rows = await cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        tasks = []
        for row in rows:
            data = dict(zip(cols, row))
            data["type"] = TaskType(data["type"])
            data["status"] = TaskStatus(data["status"])
            data["depends_on"] = json.loads(data["depends_on"]) if data["depends_on"] else []
            data["dependents"] = json.loads(data["dependents"]) if data["dependents"] else []
            if data["metrics"]:
                data["metrics"] = TaskMetrics(**json.loads(data["metrics"]))
            tasks.append(TaskStateBase(**data))
        return tasks

    async def delete_task(self, task_id: str):
        await self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await self._conn.commit()

    async def cleanup_old(self, keep_days: int = 7):
        cutoff = time.time() - keep_days * 86400
        await self._conn.execute(
            "DELETE FROM tasks WHERE end_time < ? AND status IN ('completed', 'failed', 'killed', 'timeout')",
            (cutoff,)
        )
        await self._conn.commit()


# 
# ABSTRACT TASK CLASS
# 

class Task(ABC):
    def __init__(self, name: str, task_type: TaskType):
        self.name = name
        self.type = task_type

    @abstractmethod
    async def spawn(self, task_id: str, context: "TaskContext") -> None:
        pass

    @abstractmethod
    async def kill(self, task_id: str, app_state: Dict) -> None:
        pass

    async def pause(self, task_id: str, app_state: Dict) -> None:
        logger.info(f"[{self.name}] Pausando tarefa {task_id}")

    async def resume(self, task_id: str, app_state: Dict) -> None:
        logger.info(f"[{self.name}] Retomando tarefa {task_id}")

    async def get_metrics(self, task_id: str) -> TaskMetrics:
        return TaskMetrics()


# 
# TASK CONTEXT
# 

@dataclass
class TaskContext:
    cancel_event: asyncio.Event
    get_app_state: Callable[[], Dict]
    set_app_state: Callable[[Callable], None]


# 
# TASK QUEUE (prioridade + dependncias)
# 

class TaskQueue:
    def __init__(self):
        self._tasks: Dict[str, TaskStateBase] = {}
        self._lock = asyncio.Lock()
        self._ready = asyncio.Queue()

    async def enqueue(self, task: TaskStateBase) -> None:
        async with self._lock:
            self._tasks[task.id] = task
        # Se no depende de ningum, coloca na fila de prontos
        if not task.depends_on or self._all_deps_completed(task):
            await self._ready.put(task.id)

    def _all_deps_completed(self, task: TaskStateBase) -> bool:
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    async def get_ready(self) -> Optional[str]:
        try:
            return await asyncio.wait_for(self._ready.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> None:
        async with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            # Se a tarefa foi completada, notifica dependentes
            if task.status == TaskStatus.COMPLETED:
                for dep_id in task.dependents:
                    dep = self._tasks.get(dep_id)
                    if dep and self._all_deps_completed(dep):
                        await self._ready.put(dep_id)

    async def remove_task(self, task_id: str) -> None:
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def get_all(self) -> List[TaskStateBase]:
        async with self._lock:
            return list(self._tasks.values())

    async def get_by_id(self, task_id: str) -> Optional[TaskStateBase]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def cleanup(self):
        async with self._lock:
            for task_id, task in list(self._tasks.items()):
                if is_terminal_status(task.status):
                    del self._tasks[task_id]


# 
# TASK EXECUTOR (com retry e jitter)
# 

class TaskExecutor:
    def __init__(self, queue: TaskQueue):
        self.queue = queue

    async def execute_with_retry(
        self,
        task: TaskStateBase,
        task_impl: Task,
        context: TaskContext,
        db: TaskDB,
    ) -> None:
        # Atualiza status
        await self._update_status(task.id, TaskStatus.RUNNING, db)

        while task.retry_count <= task.max_retries:
            try:
                logger.info(f"[Executor]  Executando {task.id}")
                await asyncio.wait_for(
                    task_impl.spawn(task.id, context),
                    timeout=task.timeout / 1000.0
                )
                # Sucesso
                await self._update_status(task.id, TaskStatus.COMPLETED, db)
                logger.info(f"[Executor]  {task.id} completada")
                return

            except asyncio.TimeoutError:
                task.retry_count += 1
                task.last_error = "Task timeout"
                logger.warning(f"[Executor]  Timeout {task.id} (tentativa {task.retry_count})")

                if task.retry_count <= task.max_retries:
                    await self._schedule_retry(task, db)
                else:
                    await self._update_status(task.id, TaskStatus.TIMEOUT, db)

            except Exception as e:
                task.retry_count += 1
                task.last_error = str(e)
                task.error_stack = traceback.format_exc()
                logger.error(f"[Executor]  Erro {task.id}: {e}")

                if task.retry_count <= task.max_retries:
                    await self._schedule_retry(task, db)
                else:
                    await self._update_status(task.id, TaskStatus.FAILED, db)
                    raise

    async def _schedule_retry(self, task: TaskStateBase, db: TaskDB) -> None:
        # Backoff exponencial com jitter (1s, 2s, 4s, ... mx 30s)
        base_delay = 1.0 * (2 ** (task.retry_count - 1))
        delay = min(base_delay, 30.0)
        # Jitter de 10%
        delay = delay * random.uniform(0.9, 1.1)

        retry_after = time.time() + delay
        await self._update_status(
            task.id,
            TaskStatus.RETRYING,
            db,
            extra={"retry_after": retry_after}
        )
        logger.info(
            f"[Executor]  Retry {task.retry_count}/{task.max_retries} "
            f"para {task.id} em {delay:.1f}s"
        )
        await asyncio.sleep(delay)

    async def _update_status(
        self,
        task_id: str,
        status: TaskStatus,
        db: TaskDB,
        extra: Optional[Dict] = None
    ) -> None:
        updates = {"status": status}
        if extra:
            updates.update(extra)
        if status == TaskStatus.COMPLETED or status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
            updates["end_time"] = time.time()
        await self.queue.update_task(task_id, updates)
        task = await self.queue.get_by_id(task_id)
        if task:
            await db.save_task(task)


# 
# TASK MANAGER (orquestrador principal)
# 

class TaskManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db = TaskDB(db_path or Path("./atena_evolution/tasks.db"))
        self.queue = TaskQueue()
        self.executor = TaskExecutor(self.queue)
        self.tasks_impl: Dict[TaskType, Task] = {}
        self._app_state: Dict = {}
        self._runner_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._shutdown_lock = asyncio.Lock()
        logger.info("[TaskManager] Inicializado")

    async def start(self):
        """Inicia o manager, carrega tarefas pendentes do DB e inicia o worker."""
        await self.db.init()
        # Recupera tarefas pendentes do banco
        pending_tasks = await self.db.load_all_pending()
        for task in pending_tasks:
            await self.queue.enqueue(task)
        self._runner_task = asyncio.create_task(self._run_worker())
        logger.info("[TaskManager] Worker iniciado")

    async def _run_worker(self):
        """Loop principal que processa a fila de tarefas prontas."""
        while not self._stop_event.is_set():
            task_id = await self.queue.get_ready()
            if task_id is None:
                await asyncio.sleep(0.5)
                continue

            task = await self.queue.get_by_id(task_id)
            if not task:
                continue

            # Verifica se  hora do retry
            if task.status == TaskStatus.RETRYING and task.retry_after:
                if time.time() < task.retry_after:
                    # Ainda no  hora, re-coloca na fila mais tarde
                    asyncio.create_task(self._delay_requeue(task_id, task.retry_after - time.time()))
                    continue

            impl = self.tasks_impl.get(task.type)
            if not impl:
                logger.error(f"[TaskManager] Sem implementao para {task.type}")
                await self._fail_task(task, "No task implementation")
                continue

            context = TaskContext(
                cancel_event=asyncio.Event(),
                get_app_state=lambda: self._app_state,
                set_app_state=self._set_app_state,
            )
            try:
                await self.executor.execute_with_retry(task, impl, context, self.db)
            except Exception as e:
                logger.error(f"[TaskManager] Falha final em {task.id}: {e}")
            finally:
                # Atualiza mtricas finais
                await self._update_task_metrics(task.id, impl)

    async def _delay_requeue(self, task_id: str, delay: float):
        await asyncio.sleep(max(0, delay))
        # Se a tarefa ainda existe e est retry, coloca de volta na fila
        task = await self.queue.get_by_id(task_id)
        if task and task.status == TaskStatus.RETRYING:
            await self.queue._ready.put(task_id)

    async def _fail_task(self, task: TaskStateBase, reason: str):
        await self.queue.update_task(task.id, {
            "status": TaskStatus.FAILED,
            "last_error": reason,
            "end_time": time.time()
        })
        await self.db.save_task(task)

    async def _update_task_metrics(self, task_id: str, impl: Task):
        try:
            metrics = await impl.get_metrics(task_id)
            await self.queue.update_task(task_id, {"metrics": metrics})
            task = await self.queue.get_by_id(task_id)
            if task:
                await self.db.save_task(task)
        except Exception:
            pass

    def _set_app_state(self, updater: Callable) -> None:
        self._app_state = updater(self._app_state)

    async def create_task(
        self,
        task_type: TaskType,
        description: str,
        priority: int = 5,
        timeout: int = 30000,
        max_retries: int = 3,
        tool_use_id: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
    ) -> str:
        """Cria e enfileira uma tarefa."""
        task_id = generate_task_id(task_type)
        task = TaskStateBase(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            description=description,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            tool_use_id=tool_use_id,
            depends_on=depends_on or [],
        )
        await self.db.save_task(task)
        await self.queue.enqueue(task)
        logger.info(f"[TaskManager]  Tarefa criada: {task_id} ({task_type.value})")
        return task_id

    async def kill_task(self, task_id: str) -> None:
        """Interrompe uma tarefa em execuo."""
        task = await self.queue.get_by_id(task_id)
        if not task:
            return
        impl = self.tasks_impl.get(task.type)
        if impl:
            try:
                await impl.kill(task_id, self._app_state)
            except Exception as e:
                logger.error(f"[TaskManager] Erro ao matar {task_id}: {e}")
        await self.queue.update_task(task_id, {
            "status": TaskStatus.KILLED,
            "end_time": time.time()
        })
        await self.db.save_task(task)

    async def pause_task(self, task_id: str) -> None:
        task = await self.queue.get_by_id(task_id)
        if not task:
            return
        impl = self.tasks_impl.get(task.type)
        if impl:
            await impl.pause(task_id, self._app_state)
            await self.queue.update_task(task_id, {"status": TaskStatus.PAUSED})
            await self.db.save_task(task)

    async def resume_task(self, task_id: str) -> None:
        task = await self.queue.get_by_id(task_id)
        if not task:
            return
        impl = self.tasks_impl.get(task.type)
        if impl:
            await impl.resume(task_id, self._app_state)
            await self.queue.update_task(task_id, {"status": TaskStatus.PENDING})
            await self.queue.enqueue(task)  # Re-coloca na fila
            await self.db.save_task(task)

    async def get_task_info(self, task_id: str) -> Optional[Dict]:
        task = await self.queue.get_by_id(task_id)
        return task.to_dict() if task else None

    async def get_all_tasks(self) -> List[Dict]:
        tasks = await self.queue.get_all()
        return [t.to_dict() for t in tasks]

    async def get_tasks_by_status(self, status: TaskStatus) -> List[Dict]:
        tasks = await self.queue.get_all()
        return [t.to_dict() for t in tasks if t.status == status]

    async def stop(self):
        """Graceful shutdown."""
        async with self._shutdown_lock:
            if self._stop_event.is_set():
                return
            self._stop_event.set()
            if self._runner_task:
                self._runner_task.cancel()
                try:
                    await self._runner_task
                except asyncio.CancelledError:
                    pass
            await self.db.close()
            logger.info("[TaskManager] Encerrado")

    def register_task_impl(self, task_impl: Task) -> None:
        self.tasks_impl[task_impl.type] = task_impl
        logger.info(f"[TaskManager] Registrado: {task_impl.name}")

    def print_status(self):
        import asyncio
        tasks = asyncio.run(self.queue.get_all())
        print("\n" + "" * 60)
        print("   TASK MANAGER  STATUS")
        print("" * 60)
        print(f"  Total de tarefas: {len(tasks)}")
        for status in TaskStatus:
            count = sum(1 for t in tasks if t.status == status)
            if count > 0:
                print(f"    {status.value:.<20} {count:>3d}")
        print("" * 60 + "\n")


# 
# EXEMPLO DE IMPLEMENTAO DE TAREFA
# 

class LocalBashTask(Task):
    def __init__(self):
        super().__init__("LocalBashTask", TaskType.LOCAL_BASH)

    async def spawn(self, task_id: str, context: TaskContext) -> None:
        # Simula trabalho
        await asyncio.sleep(2)
        # Poderia escrever no arquivo de sada
        output_file = get_task_output_path(task_id)
        with open(output_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} - Executado\n")
        logger.info(f"[LocalBash] {task_id} executado")

    async def kill(self, task_id: str, app_state: Dict) -> None:
        logger.info(f"[LocalBash] Matando {task_id}")


# 
# EXEMPLO DE USO
# 

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    manager = TaskManager()
    manager.register_task_impl(LocalBashTask())
    await manager.start()

    # Cria duas tarefas independentes
    task1 = await manager.create_task(
        TaskType.LOCAL_BASH,
        "Executar testes",
        priority=8,
        timeout=5000,
        max_retries=2,
    )
    task2 = await manager.create_task(
        TaskType.LOCAL_BASH,
        "Compilar cdigo",
        priority=5,
        timeout=10000,
    )

    # Aguarda um pouco para ver progresso
    await asyncio.sleep(5)

    # Consulta tarefas
    all_tasks = await manager.get_all_tasks()
    print("\n--- Tarefas aps execuo ---")
    for t in all_tasks:
        print(f"{t['id']}: {t['status']}")

    manager.print_status()
    await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
