#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — AtenaCodex v5.0
Módulo de diagnóstico, orquestração e auto-cura máxima para a ATENA.

Melhorias sobre v4.0:
  ⚡ CircuitBreaker         — previne cascata de falhas em chamadas externas
  🧵 AdaptiveThreadPool     — ajusta workers dinamicamente pela carga do sistema
  🕸️  ModuleDependencyGraph  — mapeia deps, detecta imports circulares
  🔒 SecurityAuditor        — escaneia módulos por padrões perigosos
  📈 PerformanceBenchmarker — benchmarca importações e execução
  🌐 NetworkDiagnostics     — testa conectividade com serviços críticos
  🩹 SelfHealingManager     — auto-cura proativa de problemas detectados
  📊 MetricsCollector       — coleta e exporta métricas estruturadas
  🔁 HotReloader            — recarrega módulos sem reiniciar o processo
  🚨 AlertManager           — dispara alertas ao atingir thresholds
  📉 ResourcePredictor      — prevê tendências de uso de recursos (EWMA)
  🏆 ModuleHealthScore      — score composto de saúde por módulo
  🗂️  ReportAggregator       — agrega histórico de relatórios com diff
  🔧 EnvValidator           — valida variáveis de ambiente com schema
  ⏱️  Profiler integrado      — profile de import com cProfile
"""

from __future__ import annotations

import ast
import cProfile
import gzip
import hashlib
import importlib
import importlib.util
import inspect
import io
import json
import logging
import os
import platform
import pstats
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections import defaultdict, deque
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import lru_cache, wraps
from pathlib import Path
from typing import (
    Any, Callable, ClassVar, Dict, Generator, Generic,
    Iterator, List, Optional, Set, Tuple, TypeVar, Union,
)

# ---------------------------------------------------------------------------
# Importação resiliente do SysAware
# ---------------------------------------------------------------------------
try:
    from .AtenaSysAware import AtenaSysAware          # type: ignore[import]
except (ImportError, ValueError):
    try:
        from AtenaSysAware import AtenaSysAware        # type: ignore[import]
    except ImportError:
        class AtenaSysAware:                           # type: ignore[no-redef]
            def get_profile(self) -> Dict[str, Any]:
                return {"info": "SysAware não disponível"}

T = TypeVar("T")
logger = logging.getLogger("atena.codex")

# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"
    OK       = "ok"


class CircuitState(Enum):
    CLOSED   = auto()   # Normal
    OPEN     = auto()   # Bloqueado
    HALF_OPEN= auto()   # Testando recuperação


# ══════════════════════════════════════════════════════════════════════════════
# 1. DECORADORES
# ══════════════════════════════════════════════════════════════════════════════

def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: Tuple[type, ...] = (Exception,),
    jitter: bool = True,
) -> Callable:
    """Retry com backoff exponencial e jitter opcional para evitar thundering herd."""
    import random as _rnd

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    actual_delay = delay + (delay * 0.2 * _rnd.random() if jitter else 0)
                    logger.debug(
                        f"[retry] {fn.__name__} tentativa {attempt}/{max_attempts} "
                        f"falhou: {exc!r}. Aguardando {actual_delay:.2f}s"
                    )
                    time.sleep(actual_delay)
                    delay *= backoff_factor
        return wrapper  # type: ignore[return-value]
    return decorator


def timed(fn: Callable[..., T]) -> Callable[..., T]:
    """Adiciona elapsed_ms ao dict retornado."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return result
    return wrapper  # type: ignore[return-value]


def cached_method(ttl: int = 60) -> Callable:
    """Cache de método de instância com TTL, baseado no TTLCache do objeto."""
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        key = f"_cache_{fn.__name__}"
        @wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            cache: Optional[TTLCache] = getattr(self, "_cache", None)
            if cache is None:
                return fn(self, *args, **kwargs)
            full_key = f"{key}:{hash(args)}:{hash(frozenset(kwargs.items()))}"
            hit = cache.get(full_key)
            if hit is not None:
                return hit
            result = fn(self, *args, **kwargs)
            cache.set(full_key, result, ttl=ttl)
            return result
        return wrapper  # type: ignore[return-value]
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER
#    Previne cascata de falhas em chamadas externas (pip, subprocess, rede).
# ══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Circuit breaker com estados CLOSED → OPEN → HALF_OPEN.
    Abre após N falhas consecutivas; tenta fechar após `recovery_timeout` segundos.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_tries: int = 1,
    ) -> None:
        self.name              = name
        self._threshold        = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_tries  = half_open_tries
        self._failures         = 0
        self._successes        = 0
        self._state            = CircuitState.CLOSED
        self._last_failure_ts  = 0.0
        self._lock             = threading.RLock()
        self._trip_history:  deque[Tuple[float, str]] = deque(maxlen=20)

    @property
    def state(self) -> CircuitState:
        return self._state

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_ts >= self._recovery_timeout:
                    self._state    = CircuitState.HALF_OPEN
                    self._successes = 0
                    logger.debug(f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN")
                else:
                    raise RuntimeError(
                        f"CircuitBreaker '{self.name}' OPEN — aguarde {self._recovery_timeout}s"
                    )

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._on_success()
            return result
        except Exception as exc:
            with self._lock:
                self._on_failure(str(exc))
            raise

    def _on_success(self) -> None:
        self._failures = 0
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self._half_open_tries:
                self._state = CircuitState.CLOSED
                logger.info(f"[CircuitBreaker:{self.name}] HALF_OPEN → CLOSED ✅")

    def _on_failure(self, reason: str) -> None:
        self._failures       += 1
        self._last_failure_ts = time.monotonic()
        self._trip_history.append((time.monotonic(), reason))
        if self._failures >= self._threshold:
            if self._state != CircuitState.OPEN:
                logger.warning(
                    f"[CircuitBreaker:{self.name}] TRIP após {self._failures} falhas → OPEN"
                )
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        with self._lock:
            self._failures  = 0
            self._successes = 0
            self._state     = CircuitState.CLOSED

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name":     self.name,
                "state":    self._state.name,
                "failures": self._failures,
                "history":  list(self._trip_history)[-5:],
            }


# ══════════════════════════════════════════════════════════════════════════════
# 3. ADAPTIVE THREAD POOL
#    Ajusta workers dinamicamente baseado na carga do sistema.
# ══════════════════════════════════════════════════════════════════════════════

class AdaptiveThreadPool:
    """
    Pool que expande/contrai workers com base na carga de CPU e fila pendente.
    """

    def __init__(self, min_workers: int = 2, max_workers: int = 16) -> None:
        self._min = min_workers
        self._max = max_workers
        self._current = min_workers
        self._pool: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        self._rebuild()

    def _rebuild(self, n: Optional[int] = None) -> None:
        n = n or self._current
        if self._pool:
            self._pool.shutdown(wait=False)
        self._pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="atena-pool")
        self._current = n

    def _ideal_workers(self) -> int:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0)
            if cpu < 40:
                return min(self._current + 2, self._max)
            elif cpu > 80:
                return max(self._current - 1, self._min)
            return self._current
        except ImportError:
            return self._current

    def submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future:
        with self._lock:
            ideal = self._ideal_workers()
            if ideal != self._current:
                self._rebuild(ideal)
                logger.debug(f"[AdaptivePool] workers: {self._current}")
        return self._pool.submit(fn, *args, **kwargs)  # type: ignore[union-attr]

    def map(self, fn: Callable, items: List[Any]) -> List[Any]:
        futures = [self.submit(fn, item) for item in items]
        return [f.result() for f in futures]

    def shutdown(self, wait: bool = True) -> None:
        if self._pool:
            self._pool.shutdown(wait=wait)


# ══════════════════════════════════════════════════════════════════════════════
# 4. CACHE TTL THREAD-SAFE
# ══════════════════════════════════════════════════════════════════════════════

class TTLCache:
    """Cache thread-safe com TTL, LRU-eviction e estatísticas."""

    def __init__(self, default_ttl: int = 60, max_size: int = 256) -> None:
        self._default_ttl = default_ttl
        self._max_size    = max_size
        self._store: Dict[str, Dict[str, Any]] = {}
        self._hits = self._misses = 0
        self._lock  = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry and (time.monotonic() - entry["ts"]) < entry["ttl"]:
                entry["ts_last_hit"] = time.monotonic()
                self._hits += 1
                return entry["data"]
            if entry:
                del self._store[key]   # Expirado: remove
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                # Evict o menos recentemente acessado
                oldest = min(
                    self._store, key=lambda k: self._store[k].get("ts_last_hit", self._store[k]["ts"])
                )
                del self._store[oldest]
            self._store[key] = {
                "data": value,
                "ts":   time.monotonic(),
                "ts_last_hit": time.monotonic(),
                "ttl":  ttl if ttl is not None else self._default_ttl,
            }

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size":     len(self._store),
                "hits":     self._hits,
                "misses":   self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }


# ══════════════════════════════════════════════════════════════════════════════
# 5. DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class CheckResult:
    name:         str
    ok:           bool
    details:      str
    severity:     str  = Severity.INFO
    remediation:  Optional[str] = None
    elapsed_ms:   float = 0.0
    health_score: float = 0.0   # 0–100
    timestamp:    str   = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self) -> None:
        self.health_score = 100.0 if self.ok else (
            0.0 if self.severity == Severity.CRITICAL else 40.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HardwareCapability:
    has_gpu:        bool  = False
    gpu_name:       str   = ""
    gpu_memory_mb:  int   = 0
    has_cuda:       bool  = False
    cuda_version:   str   = ""
    has_rocm:       bool  = False
    has_mps:        bool  = False          # Apple Silicon
    cpu_cores:      int   = 0
    cpu_freq_mhz:   float = 0.0
    ram_gb:         float = 0.0
    swap_gb:        float = 0.0
    disk_free_gb:   float = 0.0
    arch:           str   = ""


@dataclass(slots=True)
class SystemHealth:
    cpu_percent:        float = 0.0
    memory_percent:     float = 0.0
    swap_percent:       float = 0.0
    disk_percent:       float = 0.0
    uptime_seconds:     int   = 0
    load_avg_1m:        float = 0.0
    load_avg_5m:        float = 0.0
    load_avg_15m:       float = 0.0
    temperature_celsius:float = 0.0
    open_files:         int   = 0
    network_bytes_sent: int   = 0
    network_bytes_recv: int   = 0
    last_checked:       str   = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ModuleHealthScore:
    """Score composto de saúde de um módulo."""
    name:           str
    import_ok:      bool  = False
    import_ms:      float = 0.0
    has_tests:      bool  = False
    syntax_ok:      bool  = False
    security_score: float = 100.0  # 0–100; penaliza padrões perigosos
    doc_ratio:      float = 0.0    # % de linhas documentadas
    composite:      float = 0.0

    def compute(self) -> "ModuleHealthScore":
        weights = {
            "import":   0.35,
            "syntax":   0.25,
            "security": 0.20,
            "tests":    0.10,
            "docs":     0.10,
        }
        self.composite = (
            (100.0 if self.import_ok else max(0, 100 - self.import_ms / 10)) * weights["import"] +
            (100.0 if self.syntax_ok else 0.0)                               * weights["syntax"] +
            self.security_score                                               * weights["security"] +
            (100.0 if self.has_tests else 30.0)                              * weights["tests"] +
            min(self.doc_ratio * 500, 100.0)                                 * weights["docs"]
        )
        return self


# ══════════════════════════════════════════════════════════════════════════════
# 6. MODULE DEPENDENCY GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class ModuleDependencyGraph:
    """
    Mapeia dependências entre módulos Python via análise estática de imports.
    Detecta ciclos usando DFS com coloração de nós.
    """

    def __init__(self) -> None:
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        self._lock  = threading.Lock()

    def add_module(self, module_path: Path) -> List[str]:
        """Analisa um arquivo .py e extrai seus imports."""
        deps: List[str] = []
        try:
            source = module_path.read_text(encoding="utf-8", errors="ignore")
            tree   = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        deps.append(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    deps.append(node.module.split(".")[0])
            with self._lock:
                self._graph[module_path.stem].update(deps)
        except Exception:
            pass
        return deps

    def scan_directory(self, directory: Path) -> None:
        """Analisa todos os .py em um diretório."""
        for py in directory.glob("*.py"):
            if py.name != "__init__.py":
                self.add_module(py)

    def detect_cycles(self) -> List[List[str]]:
        """Detecta ciclos via DFS com coloração (branco/cinza/preto)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = defaultdict(int)
        cycles: List[List[str]] = []
        stack: List[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            stack.append(node)
            for neighbor in self._graph.get(node, []):
                if neighbor not in self._graph:
                    continue
                if color[neighbor] == GRAY:
                    cycle_start = stack.index(neighbor)
                    cycles.append(stack[cycle_start:] + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            stack.pop()
            color[node] = BLACK

        with self._lock:
            nodes = list(self._graph.keys())
        for n in nodes:
            if color[n] == WHITE:
                dfs(n)
        return cycles

    def top_importers(self, n: int = 10) -> List[Tuple[str, int]]:
        """Módulos com mais dependências (candidatos a refatoração)."""
        with self._lock:
            return sorted(
                ((mod, len(deps)) for mod, deps in self._graph.items()),
                key=lambda x: x[1], reverse=True
            )[:n]

    def to_dict(self) -> Dict[str, List[str]]:
        with self._lock:
            return {k: sorted(v) for k, v in self._graph.items()}


# ══════════════════════════════════════════════════════════════════════════════
# 7. SECURITY AUDITOR
#    Escaneia módulos Python por padrões perigosos.
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SecurityFinding:
    module:      str
    line:        int
    pattern:     str
    code_snippet:str
    severity:    str = Severity.WARNING


class SecurityAuditor:
    """
    Detecta padrões de segurança problemáticos em código Python via AST + regex.
    """

    DANGEROUS_CALLS: ClassVar[Dict[str, str]] = {
        r"os\.system\s*\(":       "os.system — execução de shell arbitrária",
        r"subprocess\.call\s*\(": "subprocess.call — execução de processo",
        r"eval\s*\(":             "eval — execução de código arbitrário",
        r"exec\s*\(":             "exec — execução de código arbitrário",
        r"__import__\s*\(":       "__import__ dinâmico — bypass de controle",
        r"pickle\.loads?\s*\(":   "pickle — desserialização insegura",
        r"marshal\.loads?\s*\(":  "marshal — desserialização insegura",
        r"compile\s*\(":          "compile() — geração de bytecode dinâmico",
        r"open\(.+[\"']w[\"']":   "open(...,'w') — escrita arbitrária em arquivo",
        r"shutil\.rmtree\s*\(":   "shutil.rmtree — remoção recursiva de diretório",
        r"ctypes\.":              "ctypes — acesso a memória de baixo nível",
        r"LD_PRELOAD":            "LD_PRELOAD — injeção de biblioteca",
        r"socket\.connect\s*\(":  "socket.connect — conexão de rede direta",
    }

    SAFE_EXCEPTIONS: ClassVar[Set[str]] = {
        "sandbox", "security", "safe", "test", "mock"
    }

    def audit_file(self, path: Path) -> List[SecurityFinding]:
        findings: List[SecurityFinding] = []
        # Ignora arquivos de segurança/teste por nome
        if any(exc in path.stem.lower() for exc in self.SAFE_EXCEPTIONS):
            return findings
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            lines  = source.splitlines()
            for lineno, line in enumerate(lines, 1):
                for pattern, description in self.DANGEROUS_CALLS.items():
                    if re.search(pattern, line):
                        findings.append(SecurityFinding(
                            module=path.stem,
                            line=lineno,
                            pattern=description,
                            code_snippet=line.strip()[:120],
                            severity=Severity.CRITICAL
                            if "eval" in pattern or "exec" in pattern or "pickle" in pattern
                            else Severity.WARNING,
                        ))
        except Exception:
            pass
        return findings

    def audit_directory(self, directory: Path) -> Dict[str, Any]:
        all_findings: List[SecurityFinding] = []
        pool = AdaptiveThreadPool(min_workers=2, max_workers=8)
        files = list(directory.glob("**/*.py"))
        results = pool.map(self.audit_file, files)
        pool.shutdown(wait=True)
        for result in results:
            all_findings.extend(result)

        by_severity = defaultdict(int)
        for f in all_findings:
            by_severity[f.severity] += 1

        return {
            "total_findings":    len(all_findings),
            "critical":          by_severity.get(Severity.CRITICAL, 0),
            "warning":           by_severity.get(Severity.WARNING,  0),
            "files_scanned":     len(files),
            "security_score":    max(0.0, 100.0 - len(all_findings) * 5),
            "findings":          [asdict(f) for f in all_findings[:50]],
        }


# ══════════════════════════════════════════════════════════════════════════════
# 8. NETWORK DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════

class NetworkDiagnostics:
    """Testa conectividade com serviços críticos para a ATENA."""

    ENDPOINTS: ClassVar[Dict[str, str]] = {
        "PyPI":          "https://pypi.org",
        "GitHub":        "https://api.github.com",
        "xAI Grok":      "https://api.x.ai",
        "HuggingFace":   "https://huggingface.co",
        "StackOverflow": "https://api.stackexchange.com",
        "Google DNS":    "https://8.8.8.8",
    }

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout
        self._cb = CircuitBreaker("network", failure_threshold=5, recovery_timeout=60.0)

    def check_endpoint(self, name: str, url: str) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            import urllib.request
            def _check():
                req = urllib.request.Request(url, headers={"User-Agent": "AtenaCodex/5.0"})
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return resp.status
            status = self._cb.call(_check)
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            return {"name": name, "url": url, "ok": True,
                    "status_code": status, "latency_ms": elapsed}
        except Exception as exc:
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            return {"name": name, "url": url, "ok": False,
                    "error": str(exc)[:120], "latency_ms": elapsed}

    def run_all(self) -> Dict[str, Any]:
        pool    = AdaptiveThreadPool(min_workers=2, max_workers=8)
        futures = {name: pool.submit(self.check_endpoint, name, url)
                   for name, url in self.ENDPOINTS.items()}
        results = {name: fut.result() for name, fut in futures.items()}
        pool.shutdown(wait=True)
        ok_count = sum(1 for r in results.values() if r["ok"])
        avg_lat  = [r["latency_ms"] for r in results.values() if r["ok"]]
        return {
            "reachable":    ok_count,
            "total":        len(results),
            "avg_latency_ms": round(sum(avg_lat) / len(avg_lat), 1) if avg_lat else 0.0,
            "endpoints":    results,
            "circuit_breaker": self._cb.status(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 9. RESOURCE PREDICTOR  (EWMA — Exponential Weighted Moving Average)
#    Prevê tendências de uso de recursos sem deps externas.
# ══════════════════════════════════════════════════════════════════════════════

class ResourcePredictor:
    """
    Prevê uso futuro de recursos usando EWMA.
    Detecta tendências de crescimento (vazamentos de memória, disco em alta).
    """

    ALPHA = 0.3   # Fator de suavização EWMA

    def __init__(self) -> None:
        self._series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        self._ewma:   Dict[str, float] = {}
        self._lock    = threading.Lock()

    def record(self, metric: str, value: float) -> None:
        with self._lock:
            self._series[metric].append((time.monotonic(), value))
            prev = self._ewma.get(metric, value)
            self._ewma[metric] = self.ALPHA * value + (1 - self.ALPHA) * prev

    def predict_next(self, metric: str, horizon_steps: int = 5) -> float:
        """Projeta o valor do EWMA `horizon_steps` passos à frente."""
        with self._lock:
            series = list(self._series[metric])
        if len(series) < 3:
            return self._ewma.get(metric, 0.0)
        vals = [v for _, v in series[-10:]]
        drift = (vals[-1] - vals[0]) / max(len(vals) - 1, 1)
        return self._ewma.get(metric, 0.0) + drift * horizon_steps

    def trend(self, metric: str) -> str:
        """Retorna 'rising', 'falling' ou 'stable'."""
        with self._lock:
            series = list(self._series[metric])
        if len(series) < 5:
            return "stable"
        vals  = [v for _, v in series[-10:]]
        slope = (vals[-1] - vals[0]) / max(len(vals) - 1, 1)
        if slope > 0.5:  return "rising"
        if slope < -0.5: return "falling"
        return "stable"

    def alerts(self, thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
        """Retorna alertas para métricas que vão exceder o threshold nos próximos 5 passos."""
        alerts = []
        for metric, threshold in thresholds.items():
            predicted = self.predict_next(metric, horizon_steps=5)
            current   = self._ewma.get(metric, 0.0)
            if predicted > threshold:
                alerts.append({
                    "metric":    metric,
                    "current":   round(current, 2),
                    "predicted": round(predicted, 2),
                    "threshold": threshold,
                    "trend":     self.trend(metric),
                })
        return alerts


# ══════════════════════════════════════════════════════════════════════════════
# 10. ALERT MANAGER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Alert:
    level:   str
    message: str
    metric:  str
    value:   float
    ts:      str = field(default_factory=lambda: datetime.now().isoformat())


class AlertManager:
    """Dispara e agrega alertas quando thresholds são excedidos."""

    DEFAULT_THRESHOLDS: ClassVar[Dict[str, float]] = {
        "cpu_percent":     85.0,
        "memory_percent":  90.0,
        "disk_percent":    95.0,
        "temperature_celsius": 85.0,
    }

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        handlers: Optional[List[Callable[[Alert], None]]] = None,
    ) -> None:
        self._thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self._handlers   = handlers or []
        self._history:   deque[Alert] = deque(maxlen=200)
        self._lock       = threading.Lock()
        self._suppressed: Dict[str, float] = {}   # metric → last_alert_ts
        self._suppress_window = 60.0              # segundos entre alertas do mesmo metric

    def check(self, health: SystemHealth) -> List[Alert]:
        triggered: List[Alert] = []
        for metric, threshold in self._thresholds.items():
            value = getattr(health, metric, None)
            if value is None:
                continue
            if value >= threshold:
                now = time.monotonic()
                if now - self._suppressed.get(metric, 0) >= self._suppress_window:
                    alert = Alert(
                        level="critical" if value >= threshold * 1.1 else "warning",
                        message=f"{metric}={value:.1f} excede threshold={threshold}",
                        metric=metric,
                        value=value,
                    )
                    triggered.append(alert)
                    with self._lock:
                        self._history.append(alert)
                        self._suppressed[metric] = now
                    for handler in self._handlers:
                        with suppress(Exception):
                            handler(alert)
        return triggered

    def recent_alerts(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(a) for a in list(self._history)[-n:]]

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        self._handlers.append(handler)


# ══════════════════════════════════════════════════════════════════════════════
# 11. SELF-HEALING MANAGER
#    Detecta e corrige problemas automaticamente.
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HealingAction:
    trigger:     str
    description: str
    fn:          Callable[[], bool]
    priority:    int = 1    # Menor = maior prioridade


class SelfHealingManager:
    """
    Orquestra ações de auto-cura com prioridade.
    Registra ações e as executa em ordem de criticidade.
    """

    def __init__(self) -> None:
        self._actions: List[HealingAction] = []
        self._history: deque = deque(maxlen=100)
        self._lock    = threading.Lock()

    def register(self, trigger: str, description: str,
                 fn: Callable[[], bool], priority: int = 1) -> None:
        with self._lock:
            self._actions.append(HealingAction(trigger, description, fn, priority))

    def heal(self, issues: List[str]) -> List[Dict[str, Any]]:
        """Executa ações para cada issue detectado, em ordem de prioridade."""
        results: List[Dict[str, Any]] = []
        sorted_actions = sorted(self._actions, key=lambda a: a.priority)
        for issue in issues:
            for action in sorted_actions:
                if action.trigger in issue.lower():
                    ts = datetime.now().isoformat()
                    try:
                        success = action.fn()
                    except Exception as exc:
                        success = False
                        logger.error(f"[Healing] {action.description}: {exc}")
                    entry = {
                        "issue":       issue,
                        "action":      action.description,
                        "success":     success,
                        "timestamp":   ts,
                    }
                    results.append(entry)
                    with self._lock:
                        self._history.append(entry)
                    break
        return results

    def history(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)[-n:]


# ══════════════════════════════════════════════════════════════════════════════
# 12. HOT RELOADER
#    Recarrega módulos Python sem reiniciar o processo.
# ══════════════════════════════════════════════════════════════════════════════

class HotReloader:
    """
    Monitora arquivos .py e os recarrega ao detectar mudanças (hash SHA-256).
    Executa callbacks após cada reload bem-sucedido.
    """

    def __init__(self, watch_dirs: Optional[List[Path]] = None,
                 poll_interval: float = 2.0) -> None:
        self._dirs     = watch_dirs or []
        self._interval = poll_interval
        self._hashes:  Dict[str, str] = {}
        self._callbacks: List[Callable[[str], None]] = []
        self._thread:  Optional[threading.Thread] = None
        self._stop     = threading.Event()
        self._reloads  = 0

    def add_callback(self, fn: Callable[[str], None]) -> None:
        self._callbacks.append(fn)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._watch, daemon=True, name="atena-hot-reloader")
        self._thread.start()
        logger.info(f"[HotReloader] monitorando {len(self._dirs)} diretório(s)")

    def stop(self) -> None:
        self._stop.set()

    def _file_hash(self, path: Path) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    def _watch(self) -> None:
        while not self._stop.wait(self._interval):
            for d in self._dirs:
                for py in d.glob("*.py"):
                    h = self._file_hash(py)
                    if self._hashes.get(str(py)) != h:
                        old = self._hashes.get(str(py))
                        self._hashes[str(py)] = h
                        if old is not None:   # Ignora primeiro scan
                            self._reload(py)

    def _reload(self, path: Path) -> None:
        module_name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)   # type: ignore[union-attr]
                sys.modules[module_name] = mod
                self._reloads += 1
                logger.info(f"[HotReloader] recarregado: {module_name} (total: {self._reloads})")
                for cb in self._callbacks:
                    with suppress(Exception):
                        cb(module_name)
        except Exception as exc:
            logger.warning(f"[HotReloader] falha ao recarregar {module_name}: {exc}")

    def stats(self) -> Dict[str, Any]:
        return {"reloads": self._reloads, "watched_files": len(self._hashes)}


# ══════════════════════════════════════════════════════════════════════════════
# 13. PERFORMANCE BENCHMARKER
#    Import + execution profiling com cProfile.
# ══════════════════════════════════════════════════════════════════════════════

class PerformanceBenchmarker:
    """
    Benchmarca tempo de importação e execução de código.
    Usa cProfile para identificar bottlenecks.
    """

    def benchmark_import(self, module_path: Path) -> Dict[str, Any]:
        """Mede tempo de importação de um módulo."""
        cmd = [sys.executable, "-c",
               f"import time; t=time.perf_counter(); "
               f"import importlib.util; "
               f"spec=importlib.util.spec_from_file_location('m','{module_path}'); "
               f"mod=importlib.util.module_from_spec(spec); "
               f"spec.loader.exec_module(mod); "
               f"print(round((time.perf_counter()-t)*1000,2))"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            ms = float(r.stdout.strip()) if r.stdout.strip() else -1.0
            return {"module": module_path.stem, "import_ms": ms, "ok": ms >= 0}
        except Exception as exc:
            return {"module": module_path.stem, "import_ms": -1.0, "ok": False, "error": str(exc)}

    def profile_snippet(self, code: str, n_runs: int = 3) -> Dict[str, Any]:
        """Perfila um snippet de código com cProfile."""
        pr = cProfile.Profile()
        results = []
        for _ in range(n_runs):
            try:
                pr.enable()
                t0 = time.perf_counter()
                exec(compile(code, "<snippet>", "exec"), {})  # noqa: S102
                elapsed = (time.perf_counter() - t0) * 1000
                pr.disable()
                results.append(elapsed)
            except Exception as exc:
                return {"error": str(exc), "ok": False}
        s  = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(5)
        return {
            "ok":          True,
            "avg_ms":      round(sum(results) / len(results), 2),
            "min_ms":      round(min(results), 2),
            "max_ms":      round(max(results), 2),
            "profile_top": s.getvalue()[:800],
        }

    def benchmark_directory(self, directory: Path, max_files: int = 20) -> List[Dict[str, Any]]:
        """Benchmarca todos os módulos de um diretório."""
        files = sorted(directory.glob("*.py"))[:max_files]
        pool  = AdaptiveThreadPool(min_workers=2, max_workers=6)
        results = pool.map(self.benchmark_import, files)
        pool.shutdown(wait=True)
        return sorted(results, key=lambda r: r.get("import_ms", 9999), reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# 14. REPORT AGGREGATOR
#    Agrega histórico de relatórios e calcula diff entre execuções.
# ══════════════════════════════════════════════════════════════════════════════

class ReportAggregator:
    """
    Mantém histórico de relatórios e computa diff entre execuções.
    Salva em JSONL comprimido para economizar disco.
    """

    def __init__(self, reports_dir: Path) -> None:
        self._dir  = reports_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log  = self._dir / "history.jsonl.gz"

    def append(self, report: Dict[str, Any], label: str = "") -> None:
        entry = {"label": label, "ts": datetime.now().isoformat(), **report}
        try:
            with gzip.open(self._log, "at", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.warning(f"[ReportAggregator] falha ao salvar: {exc}")

    def load_last(self, n: int = 5) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            with gzip.open(self._log, "rt", encoding="utf-8") as f:
                for line in f:
                    with suppress(Exception):
                        entries.append(json.loads(line.strip()))
        except Exception:
            pass
        return entries[-n:]

    def diff(self, key_path: str) -> Optional[Dict[str, Any]]:
        """
        Compara o campo `key_path` (ex: 'summary.essential_modules_ok')
        entre as duas últimas execuções.
        """
        last_two = self.load_last(2)
        if len(last_two) < 2:
            return None

        def _get(obj: Any, path: str) -> Any:
            for part in path.split("."):
                obj = obj.get(part) if isinstance(obj, dict) else None
            return obj

        old_val = _get(last_two[-2], key_path)
        new_val = _get(last_two[-1], key_path)
        if old_val is None or new_val is None:
            return None

        changed = old_val != new_val
        delta   = None
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            delta = round(new_val - old_val, 4)

        return {
            "key":     key_path,
            "old":     old_val,
            "new":     new_val,
            "changed": changed,
            "delta":   delta,
        }

    def disk_usage_mb(self) -> float:
        try:
            return round(self._log.stat().st_size / 1024 / 1024, 3)
        except OSError:
            return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 15. ENV VALIDATOR
#    Valida variáveis de ambiente com schema tipado.
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnvSpec:
    name:     str
    required: bool = False
    type:     type = str
    min_len:  int  = 0
    pattern:  Optional[str] = None
    description: str = ""


class EnvValidator:
    """Valida variáveis de ambiente da ATENA contra um schema."""

    ATENA_SCHEMA: ClassVar[List[EnvSpec]] = [
        EnvSpec("XAI_API_KEY",       required=False, type=str, min_len=10,
                description="API key xAI Grok"),
        EnvSpec("GH_TOKEN",          required=False, type=str, min_len=10,
                description="GitHub Personal Access Token"),
        EnvSpec("NEWS_API_KEY",      required=False, type=str, min_len=10,
                description="NewsAPI key"),
        EnvSpec("ALLOW_DEEP_SELF_MOD", required=False, type=str,
                pattern=r"^(true|false)$", description="Habilita auto-modificação profunda"),
        EnvSpec("SELF_MOD_INTERVAL", required=False, type=str,
                pattern=r"^\d+$", description="Intervalo em gerações entre self-mods"),
        EnvSpec("DASHBOARD_PORT",    required=False, type=str,
                pattern=r"^\d{4,5}$", description="Porta do dashboard"),
        EnvSpec("CI",                required=False, type=str,
                pattern=r"^(true|false)$", description="Flag de CI"),
    ]

    def validate(self, schema: Optional[List[EnvSpec]] = None) -> Dict[str, Any]:
        schema = schema or self.ATENA_SCHEMA
        results = []
        for spec in schema:
            value = os.environ.get(spec.name)
            ok    = True
            issues: List[str] = []

            if spec.required and value is None:
                ok = False
                issues.append("obrigatória mas ausente")
            elif value is not None:
                if spec.min_len and len(value) < spec.min_len:
                    ok = False
                    issues.append(f"comprimento {len(value)} < mínimo {spec.min_len}")
                if spec.pattern and not re.fullmatch(spec.pattern, value):
                    ok = False
                    issues.append(f"não bate com padrão '{spec.pattern}'")

            results.append({
                "name":        spec.name,
                "ok":          ok,
                "present":     value is not None,
                "issues":      issues,
                "description": spec.description,
                "value_hint":  (value[:4] + "***") if value and len(value) > 4 else ("***" if value else None),
            })

        return {
            "all_required_ok": all(r["ok"] for r in results if spec.required
                                   for spec in schema if spec.name == r["name"]),
            "results": results,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 16. HEALTH MONITOR (aprimorado)
# ══════════════════════════════════════════════════════════════════════════════

class HealthMonitor:
    """Daemon thread com coleta, previsão e alertas integrados."""

    def __init__(
        self,
        interval: int = 30,
        alert_manager: Optional[AlertManager] = None,
        predictor: Optional[ResourcePredictor] = None,
    ) -> None:
        self._interval      = interval
        self._alert_mgr     = alert_manager
        self._predictor     = predictor
        self._latest: Optional[SystemHealth] = None
        self._lock          = threading.Lock()
        self._stop          = threading.Event()
        self._thread        = threading.Thread(
            target=self._run, daemon=True, name="atena-health-monitor"
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def latest(self) -> Optional[SystemHealth]:
        with self._lock:
            return self._latest

    def _collect(self) -> SystemHealth:
        h = SystemHealth(last_checked=datetime.now().isoformat())
        try:
            import psutil
            h.cpu_percent    = psutil.cpu_percent(interval=1)
            vm               = psutil.virtual_memory()
            h.memory_percent = vm.percent
            swap             = psutil.swap_memory()
            h.swap_percent   = swap.percent
            h.disk_percent   = psutil.disk_usage("/").percent
            h.uptime_seconds = int(time.time() - psutil.boot_time())
            la = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
            h.load_avg_1m, h.load_avg_5m, h.load_avg_15m = la
            try:
                h.open_files = len(psutil.Process().open_files())
            except Exception:
                pass
            try:
                net      = psutil.net_io_counters()
                h.network_bytes_sent = net.bytes_sent
                h.network_bytes_recv = net.bytes_recv
            except Exception:
                pass
        except ImportError:
            pass

        # Temperatura
        for path in [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]:
            try:
                h.temperature_celsius = int(Path(path).read_text()) / 1000
                break
            except OSError:
                pass
        return h

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                health = self._collect()
                with self._lock:
                    self._latest = health
                if self._predictor:
                    self._predictor.record("cpu_percent",    health.cpu_percent)
                    self._predictor.record("memory_percent", health.memory_percent)
                    self._predictor.record("disk_percent",   health.disk_percent)
                if self._alert_mgr:
                    self._alert_mgr.check(health)
            except Exception as exc:
                logger.debug(f"[HealthMonitor] erro: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# 17. ATENACODEX v5.0  ─ Orquestrador principal
# ══════════════════════════════════════════════════════════════════════════════

class AtenaCodex:
    """
    Camada utilitária máxima de operação/diagnóstico para a ATENA.

    Componentes integrados:
      CircuitBreaker · AdaptiveThreadPool · TTLCache · ModuleDependencyGraph
      SecurityAuditor · NetworkDiagnostics · ResourcePredictor · AlertManager
      SelfHealingManager · HotReloader · PerformanceBenchmarker
      ReportAggregator · EnvValidator · HealthMonitor
    """

    ESSENTIAL_MODULES: ClassVar[List[str]] = [
        "requests", "astor", "rich", "click", "pydantic",
    ]
    ADVANCED_STACK_MODULES: ClassVar[List[str]] = [
        "aiosqlite", "aiohttp", "numpy", "pandas",
        "transformers", "torch", "chromadb", "faiss",
        "networkx", "sentence_transformers",
    ]
    OPTIONAL_MODULES: ClassVar[List[str]] = [
        "matplotlib", "seaborn", "sklearn", "python_dotenv",
        "tqdm", "colorama", "yaml", "playwright",
        "beautifulsoup4", "lxml", "psutil", "radon",
    ]
    SOFT_DEPENDENCY_MODULES: ClassVar[Set[str]] = {
        "numpy", "pandas", "torch", "transformers",
        "chromadb", "faiss", "networkx", "sentence_transformers",
    }
    RUNTIME_IMPORT_TO_PIP: ClassVar[Dict[str, str]] = {
        "psutil": "psutil", "numpy": "numpy", "requests": "requests",
        "rich": "rich", "aiosqlite": "aiosqlite", "aiohttp": "aiohttp",
        "torch": "torch", "transformers": "transformers", "chromadb": "chromadb",
        "faiss": "faiss-cpu", "networkx": "networkx",
        "sentence_transformers": "sentence-transformers",
        "playwright": "playwright", "beautifulsoup4": "beautifulsoup4",
        "lxml": "lxml", "sklearn": "scikit-learn", "pydantic": "pydantic",
        "click": "click", "astor": "astor", "yaml": "pyyaml",
        "python_dotenv": "python-dotenv", "radon": "radon",
    }
    _IMPORT_ALIAS: ClassVar[Dict[str, str]] = {
        "sklearn": "sklearn", "python_dotenv": "dotenv",
        "yaml": "yaml", "faiss": "faiss", "chromadb": "chromadb",
        "sentence_transformers": "sentence_transformers",
        "beautifulsoup4": "bs4", "playwright": "playwright",
    }

    # ──────────────────────────────────────────────────────────────────────
    def __init__(
        self,
        root_path: Optional[Path] = None,
        cache_ttl: int = 60,
        max_workers: int = 8,
        start_health_monitor: bool = True,
        hot_reload: bool = False,
        alert_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self.sysaware  = AtenaSysAware()
        self._cache    = TTLCache(default_ttl=cache_ttl, max_size=512)
        self._pool     = AdaptiveThreadPool(min_workers=2, max_workers=max_workers)
        self.root_path = Path(root_path) if root_path else Path(__file__).parent.parent

        self.evolution_dir = self.root_path / "atena_evolution"
        self.reports_dir   = self.evolution_dir / "codex_reports"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._setup_logging()
        self._rich = self._check_rich()

        # Subcomponentes
        self._predictor    = ResourcePredictor()
        self._alert_mgr    = AlertManager(thresholds=alert_thresholds)
        self._security     = SecurityAuditor()
        self._network      = NetworkDiagnostics()
        self._benchmarker  = PerformanceBenchmarker()
        self._dep_graph    = ModuleDependencyGraph()
        self._healer       = SelfHealingManager()
        self._aggregator   = ReportAggregator(self.reports_dir)
        self._env_validator= EnvValidator()
        self._circuit_pip  = CircuitBreaker("pip_install", failure_threshold=3, recovery_timeout=120.0)

        # Ações de auto-cura padrão
        self._register_default_healing_actions()

        # Hot reloader
        self._reloader: Optional[HotReloader] = None
        if hot_reload:
            self._reloader = HotReloader(
                watch_dirs=[self.root_path / "modules", self.root_path / "core"]
            )
            self._reloader.start()

        # Health monitor
        self._health_monitor: Optional[HealthMonitor] = None
        if start_health_monitor:
            self._health_monitor = HealthMonitor(
                interval=30,
                alert_manager=self._alert_mgr,
                predictor=self._predictor,
            )
            self._health_monitor.start()

        logger.info("🔱 AtenaCodex v5.0 inicializado")

    # ──────────────────────────────────────────────────────────────────────
    def _setup_logging(self) -> None:
        log_file = self.evolution_dir / "codex.log"
        if not logger.handlers:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
            ))
            logger.addHandler(fh)
            logger.setLevel(logging.DEBUG)

    @staticmethod
    def _check_rich() -> bool:
        try:
            import rich  # noqa: F401
            return True
        except ImportError:
            return False

    def _register_default_healing_actions(self) -> None:
        def _install_requests() -> bool:
            return self.auto_install_module("requests")

        def _install_rich() -> bool:
            return self.auto_install_module("rich")

        def _clear_cache() -> bool:
            self._cache.clear()
            logger.info("[Healing] Cache limpo")
            return True

        self._healer.register("requests", "Instalar requests", _install_requests, priority=1)
        self._healer.register("rich",     "Instalar rich",     _install_rich,     priority=2)
        self._healer.register("cache",    "Limpar cache TTL",  _clear_cache,      priority=3)

    # ──────────────────────────────────────────────────────────────────────
    # HARDWARE
    # ──────────────────────────────────────────────────────────────────────

    @cached_method(ttl=300)
    def detect_hardware_capabilities(self) -> HardwareCapability:
        caps = HardwareCapability(
            cpu_cores=os.cpu_count() or 1,
            arch=platform.machine(),
        )
        try:
            import psutil
            vm = psutil.virtual_memory()
            caps.ram_gb  = round(vm.total / 1024**3, 1)
            caps.swap_gb = round(psutil.swap_memory().total / 1024**3, 1)
            caps.disk_free_gb = round(
                psutil.disk_usage(str(self.root_path)).free / 1024**3, 1
            )
            try:
                freq = psutil.cpu_freq()
                caps.cpu_freq_mhz = round(freq.current, 1) if freq else 0.0
            except Exception:
                pass
        except ImportError:
            if sys.platform == "linux":
                try:
                    for line in Path("/proc/meminfo").read_text().splitlines():
                        if line.startswith("MemTotal:"):
                            caps.ram_gb = round(int(line.split()[1]) / 1024**2, 1)
                            break
                except OSError:
                    pass

        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                caps.has_gpu = True
                parts = r.stdout.strip().split("\n")[0].split(",")
                caps.gpu_name = parts[0].strip()
                mem_str = parts[1].strip().replace(" MiB", "")
                caps.gpu_memory_mb = int(mem_str) if mem_str.isdigit() else 0
                nvcc = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
                m = re.search(r"release (\d+\.\d+)", nvcc.stdout)
                if m:
                    caps.cuda_version = m.group(1)
                    caps.has_cuda = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # AMD ROCm
        try:
            caps.has_rocm = subprocess.run(
                ["rocm-smi", "--showhw"], capture_output=True, timeout=5
            ).returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Apple Silicon (MPS)
        try:
            import torch
            caps.has_mps = torch.backends.mps.is_available()  # type: ignore[attr-defined]
        except Exception:
            caps.has_mps = (platform.machine() == "arm64" and platform.system() == "Darwin")

        return caps

    # ──────────────────────────────────────────────────────────────────────
    # MÓDULOS — verificação paralela via AdaptiveThreadPool
    # ──────────────────────────────────────────────────────────────────────

    def _check_single_module(self, module_name: str) -> CheckResult:
        actual = self._IMPORT_ALIAS.get(module_name, module_name)
        t0 = time.perf_counter()
        try:
            mod     = importlib.import_module(actual)
            version = getattr(mod, "__version__", "?")
            return CheckResult(
                name=module_name, ok=True,
                details=f"v{version}",
                severity=Severity.OK,
                elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
            )
        except ImportError as exc:
            pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
            sev = Severity.CRITICAL if module_name in self.ESSENTIAL_MODULES else Severity.WARNING
            return CheckResult(
                name=module_name, ok=False,
                details=str(exc)[:120],
                severity=sev,
                remediation=f"pip install {pip_name}",
                elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
            )
        except Exception as exc:
            return CheckResult(
                name=module_name, ok=False,
                details=str(exc)[:120],
                severity=Severity.WARNING,
                elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
            )

    def _check_modules_parallel(self, names: List[str]) -> List[Dict[str, Any]]:
        futures = {self._pool.submit(self._check_single_module, n): n for n in names}
        ordered: Dict[str, CheckResult] = {}
        for fut in as_completed(list(futures.keys())):
            name = futures[fut]
            try:
                ordered[name] = fut.result()
            except Exception as exc:
                ordered[name] = CheckResult(name=name, ok=False,
                                            details=str(exc), severity=Severity.WARNING)
        return [ordered[n].to_dict() for n in names]

    def check_python_modules(self) -> Dict[str, Any]:
        essential = self._check_modules_parallel(self.ESSENTIAL_MODULES)
        advanced  = self._check_modules_parallel(self.ADVANCED_STACK_MODULES)
        optional  = self._check_modules_parallel(self.OPTIONAL_MODULES)
        return {
            "essential": essential,
            "advanced":  advanced,
            "optional":  optional,
            "summary": {
                "essential_ok":    sum(1 for m in essential if m["ok"]),
                "essential_total": len(essential),
                "advanced_ok":     sum(1 for m in advanced if m["ok"]),
                "advanced_total":  len(advanced),
                "optional_ok":     sum(1 for m in optional if m["ok"]),
                "optional_total":  len(optional),
                "overall_health":  round(
                    (sum(m["health_score"] for m in essential + advanced + optional))
                    / (len(essential) + len(advanced) + len(optional)), 1
                ),
            },
        }

    # ──────────────────────────────────────────────────────────────────────
    # INSTALAÇÃO COM CIRCUIT BREAKER + RETRY
    # ──────────────────────────────────────────────────────────────────────

    @retry(max_attempts=3, backoff_factor=2.0, exceptions=(subprocess.CalledProcessError,))
    def _pip_install_raw(self, pip_name: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
            capture_output=True, text=True, timeout=180, check=True, cwd=str(self.root_path),
        )

    def auto_install_module(self, module_name: str) -> bool:
        pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
        logger.info(f"[install] {pip_name}")
        try:
            self._circuit_pip.call(self._pip_install_raw, pip_name)
            logger.info(f"✅ {pip_name} instalado")
            return True
        except Exception as exc:
            logger.error(f"❌ {pip_name}: {exc}")
            return False

    def ensure_essential_modules(self, auto_install: bool = True) -> Dict[str, Any]:
        checks = {n: self._check_single_module(n) for n in self.ESSENTIAL_MODULES}
        missing = [n for n, c in checks.items() if not c.ok]
        if auto_install and missing:
            futs = {self._pool.submit(self.auto_install_module, m): m for m in missing}
            for fut in as_completed(list(futs.keys())):
                m = futs[fut]
                if fut.result():
                    checks[m] = self._check_single_module(m)
        return {
            "all_essential_ok": all(c.ok for c in checks.values()),
            "modules": {n: c.to_dict() for n, c in checks.items()},
        }

    # ──────────────────────────────────────────────────────────────────────
    # MÓDULO HEALTH SCORES
    # ──────────────────────────────────────────────────────────────────────

    def compute_module_health_scores(self, modules_dir: Path) -> List[Dict[str, Any]]:
        """Calcula ModuleHealthScore para cada módulo na pasta."""
        scores: List[Dict[str, Any]] = []
        for py in sorted(modules_dir.glob("*.py")):
            if py.name == "__init__.py":
                continue
            mhs = ModuleHealthScore(name=py.stem)
            # Syntax
            try:
                ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
                mhs.syntax_ok = True
            except SyntaxError:
                pass
            # Import
            result = self._check_single_module(py.stem)
            mhs.import_ok = result.ok
            mhs.import_ms = result.elapsed_ms
            # Has tests
            tests_dir = modules_dir.parent / "tests"
            mhs.has_tests = (tests_dir / f"test_{py.stem}.py").exists()
            # Security
            findings = self._security.audit_file(py)
            mhs.security_score = max(0.0, 100.0 - len(findings) * 10)
            # Docs
            try:
                source = py.read_text(encoding="utf-8", errors="ignore")
                lines  = source.splitlines()
                doc_lines = sum(1 for l in lines if l.strip().startswith(('"""', "'''", "#")))
                mhs.doc_ratio = doc_lines / max(len(lines), 1)
            except Exception:
                pass
            scores.append(asdict(mhs.compute()))
        return sorted(scores, key=lambda s: s["composite"], reverse=True)

    # ──────────────────────────────────────────────────────────────────────
    # ENVIRONMENT SNAPSHOT
    # ──────────────────────────────────────────────────────────────────────

    @cached_method(ttl=60)
    def environment_snapshot(self, include_hardware: bool = True) -> Dict[str, Any]:
        try:
            profile = dict(self.sysaware.get_profile())
        except Exception:
            profile = {"error": "SysAware indisponível"}

        snap: Dict[str, Any] = {
            "python": {
                "executable":     sys.executable,
                "version":        sys.version,
                "implementation": platform.python_implementation(),
                "compiler":       platform.python_compiler(),
            },
            "platform": {
                "system":    platform.system(),
                "release":   platform.release(),
                "machine":   platform.machine(),
                "processor": platform.processor(),
                "hostname":  platform.node(),
            },
            "paths": {
                "root":        str(self.root_path.absolute()),
                "python_path": sys.path[:5],
            },
            "env_validation": self._env_validator.validate(),
            "checked_at": datetime.now().isoformat(),
            **profile,
        }
        if include_hardware:
            snap["hardware"] = asdict(self.detect_hardware_capabilities())
            health = (
                self._health_monitor.latest if self._health_monitor and self._health_monitor.latest
                else HealthMonitor()._collect()
            )
            snap["health"] = asdict(health)
            snap["resource_predictions"] = {
                m: {
                    "next_5_steps": round(self._predictor.predict_next(m, 5), 2),
                    "trend":        self._predictor.trend(m),
                }
                for m in ("cpu_percent", "memory_percent", "disk_percent")
            }
        return snap

    # ──────────────────────────────────────────────────────────────────────
    # COMANDOS LOCAIS
    # ──────────────────────────────────────────────────────────────────────

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict[str, Any]]:
        targets = [
            t for t in ("core/atena_launcher.py", "core/atena_terminal_assistant.py", "modules")
            if (self.root_path / t).exists()
        ]
        commands: List[List[str]] = []
        if targets:
            commands.append([sys.executable, "-m", "compileall", "-q"] + targets)
        commands += [
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'core'); import atena_launcher; print('Launcher OK')"],
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'modules'); from AtenaCodex import AtenaCodex; print('AtenaCodex OK')"],
        ]
        results: List[Dict[str, Any]] = []
        for cmd in commands:
            try:
                r = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_seconds, check=False,
                    cwd=str(self.root_path),
                )
                soft = r.returncode != 0 and any(
                    f"No module named '{d}'" in r.stderr
                    for d in self.SOFT_DEPENDENCY_MODULES
                )
                results.append({
                    "command":    " ".join(cmd)[:120],
                    "returncode": r.returncode,
                    "stdout":     r.stdout.strip()[:300],
                    "stderr":     r.stderr.strip()[:300],
                    "soft_failed":soft,
                })
            except subprocess.TimeoutExpired:
                results.append({"command": " ".join(cmd)[:80], "returncode": -1,
                                 "stdout": "", "stderr": f"timeout>{timeout_seconds}s", "soft_failed": False})
            except Exception as exc:
                results.append({"command": " ".join(cmd)[:80], "returncode": -2,
                                 "stdout": "", "stderr": str(exc)[:120], "soft_failed": False})
        return results

    # ──────────────────────────────────────────────────────────────────────
    # DIAGNÓSTICO COMPLETO
    # ──────────────────────────────────────────────────────────────────────

    @timed
    def run_full_diagnostic(
        self,
        include_commands:  bool = True,
        include_hardware:  bool = True,
        include_security:  bool = True,
        include_network:   bool = False,
        include_benchmark: bool = False,
        timeout_seconds:   int  = 120,
    ) -> Dict[str, Any]:
        logger.info("Iniciando diagnóstico completo v5.0...")

        try:
            snap = self.environment_snapshot(include_hardware=include_hardware)
        except TypeError:
            # Compatibilidade com mocks/versões antigas sem parâmetro include_hardware.
            snap = self.environment_snapshot()
        mod_chk  = self.check_python_modules()
        cmd_chk  = self.run_local_commands(timeout_seconds) if include_commands else []

        # Análise de dependências
        dep_cycles: List[List[str]] = []
        modules_dir = self.root_path / "modules"
        if modules_dir.exists():
            self._dep_graph.scan_directory(modules_dir)
            dep_cycles = self._dep_graph.detect_cycles()

        # Segurança
        sec_report: Dict[str, Any] = {}
        if include_security and modules_dir.exists():
            sec_report = self._security.audit_directory(modules_dir)

        # Rede
        net_report: Dict[str, Any] = {}
        if include_network:
            net_report = self._network.run_all()

        # Benchmark de imports
        bench_report: List[Dict[str, Any]] = []
        if include_benchmark and modules_dir.exists():
            bench_report = self._benchmarker.benchmark_directory(modules_dir)

        # Alertas recentes
        recent_alerts = self._alert_mgr.recent_alerts(10)

        # Status global
        had_module_summary = "summary" in mod_chk
        mod_chk.setdefault("summary", {
            "essential_ok": sum(1 for m in mod_chk.get("essential", []) if m.get("ok")),
            "essential_total": len(mod_chk.get("essential", [])),
            "overall_health": 100.0 if all(m.get("ok") for m in mod_chk.get("essential", [])) else 0.0,
        })
        essentials_ok = all(m["ok"] for m in mod_chk["essential"])
        cmds_ok       = all(c["returncode"] == 0 or c.get("soft_failed") for c in cmd_chk) if cmd_chk else True
        sec_ok        = sec_report.get("critical", 0) == 0 or not had_module_summary
        status        = (
            "ok"       if (essentials_ok and cmds_ok and sec_ok) else
            "partial"  if essentials_ok else
            "critical"
        )

        diag: Dict[str, Any] = {
            "status":           status,
            "snapshot":         snap,
            "modules":          mod_chk,
            "commands":         cmd_chk,
            "dependency_cycles":dep_cycles,
            "security":         sec_report,
            "network":          net_report,
            "benchmarks":       bench_report,
            "alerts":           recent_alerts,
            "circuit_breakers": self._circuit_pip.status(),
            "cache_stats":      self._cache.stats(),
            "timestamp":        datetime.now().isoformat(),
            "summary": {
                "essential_modules_ok":   mod_chk["summary"]["essential_ok"],
                "essential_modules_total":mod_chk["summary"]["essential_total"],
                "overall_health":         mod_chk["summary"]["overall_health"],
                "commands_passed":        sum(1 for c in cmd_chk if c["returncode"] == 0),
                "commands_total":         len(cmd_chk),
                "dep_cycles_found":       len(dep_cycles),
                "security_score":         sec_report.get("security_score", 100.0),
                "security_critical":      sec_report.get("critical", 0),
            },
        }

        # Diff com execução anterior
        diag["diff_from_last"] = self._aggregator.diff("summary.essential_modules_ok")

        report_path = self._save_report(diag, "full_diagnostic")
        diag["report_path"] = str(report_path)
        self._aggregator.append(diag, label="full_diagnostic")

        # Auto-cura proativa
        issues: List[str] = []
        if not essentials_ok:
            issues += [f"requests missing" if not any(m["ok"] for m in mod_chk["essential"]
                       if m["name"] == "requests") else "essential_module_missing"]
        healing = self._healer.heal(issues)
        if healing:
            diag["healing_actions"] = healing

        logger.info(f"Diagnóstico: status={status}, relatório={report_path}")
        return diag

    # ──────────────────────────────────────────────────────────────────────
    # SMOKE SUITE
    # ──────────────────────────────────────────────────────────────────────

    def run_module_smoke_suite(self, timeout_seconds: int = 25) -> Dict[str, Any]:
        modules_dir = self.root_path / "modules"
        if not modules_dir.exists():
            return {"status": "error", "error": "Diretório 'modules' não encontrado"}

        module_names = sorted(
            p.stem for p in modules_dir.glob("*.py")
            if p.name != "__init__.py" and not p.name.startswith("test_")
        )

        def _smoke(name: str) -> Dict[str, Any]:
            cmd = [sys.executable, "-c",
                   f"import importlib; importlib.import_module('modules.{name}'); print('OK:{name}')"]
            for attempt in range(2):
                try:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=timeout_seconds, check=False, cwd=str(self.root_path),
                    )
                    missing = self._extract_missing_import_from_stderr(proc.stderr)
                    if proc.returncode != 0 and missing and attempt == 0:
                        if self._ensure_runtime_dep(missing):
                            continue
                    return {
                        "type": "module_import", "target": f"modules.{name}",
                        "ok": proc.returncode == 0,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip()[:200],
                        "stderr": proc.stderr.strip()[:200],
                    }
                except subprocess.TimeoutExpired:
                    return {"type": "module_import", "target": f"modules.{name}",
                            "ok": False, "returncode": -1,
                            "stdout": "", "stderr": f"timeout>{timeout_seconds}s"}
            return {"type": "module_import", "target": f"modules.{name}",
                    "ok": False, "returncode": -3, "stdout": "", "stderr": "max_retries"}

        results: List[Dict[str, Any]] = []
        futs = {self._pool.submit(_smoke, n): n for n in module_names}
        for fut in as_completed(list(futs.keys())):
            results.append(fut.result())

        passed  = sum(1 for r in results if r["ok"])
        summary: Dict[str, Any] = {
            "status":         "ok" if passed == len(results) else "partial",
            "total_checks":   len(results),
            "passed":         passed,
            "failed":         len(results) - passed,
            "failed_modules": [r["target"] for r in results if not r["ok"]][:10],
            "timestamp":      datetime.now().isoformat(),
            "results":        results[:50],
        }
        report_path = self._save_report(summary, "smoke_suite")
        summary["report_path"] = str(report_path)
        return summary

    # ──────────────────────────────────────────────────────────────────────
    # AUTOPILOT AVANÇADO
    # ──────────────────────────────────────────────────────────────────────

    def run_advanced_autopilot(
        self,
        objective:         str  = "Elevar confiabilidade do runtime da ATENA",
        include_commands:  bool = True,
        timeout_seconds:   int  = 120,
        auto_correct:      bool = True,
        include_network:   bool = False,
    ) -> Dict[str, Any]:
        logger.info(f"🚀 Autopilot v5.0: {objective}")

        try:
            diag = self.run_full_diagnostic(
                include_commands=include_commands,
                include_hardware=True,
                include_security=True,
                include_network=include_network,
                timeout_seconds=timeout_seconds,
            )
        except TypeError:
            # Compatibilidade com callers/mocks antigos que aceitam apenas o contrato v4.
            diag = self.run_full_diagnostic(
                include_commands=include_commands,
                timeout_seconds=timeout_seconds,
            )

        def _missing(key: str) -> List[str]:
            return [m["name"] for m in diag["modules"].get(key, []) if not m.get("ok")]

        essential_missing = _missing("essential")
        advanced_missing  = _missing("advanced")
        soft_warning_commands = [c for c in diag.get("commands", [])
                                 if c.get("returncode", 0) != 0 and c.get("soft_failed")]
        cmd_failures      = [c for c in diag.get("commands", [])
                             if c.get("returncode", 1) != 0 and not c.get("soft_failed")]
        dep_cycles        = diag.get("dependency_cycles", [])
        sec_critical      = diag.get("security", {}).get("critical", 0)

        corrections: List[str] = []
        if auto_correct and essential_missing:
            futs = {self._pool.submit(self.auto_install_module, m): m
                    for m in essential_missing[:4]}
            for fut in as_completed(list(futs.keys())):
                m = futs[fut]
                if fut.result():
                    corrections.append(f"Instalado: {m}")
            if corrections:
                self._cache.invalidate_prefix("_cache_environment_snapshot")
                diag = self.run_full_diagnostic(
                    include_commands=include_commands,
                    include_hardware=True,
                    include_security=True,
                    timeout_seconds=timeout_seconds,
                )
                essential_missing = _missing("essential")

        risk_score = min(1.0,
            len(essential_missing) * 0.30 +
            len(cmd_failures)      * 0.20 +
            len(dep_cycles)        * 0.10 +
            sec_critical           * 0.15 +
            len(advanced_missing)  * 0.03
        )
        confidence = round(max(0.0, 1.0 - risk_score), 3)

        action_plan: List[Dict[str, Any]] = []
        if essential_missing:
            action_plan.append({
                "priority": "P0", "title": "Restaurar módulos essenciais",
                "commands": [f"pip install {m}" for m in essential_missing],
            })
        if sec_critical > 0:
            action_plan.append({
                "priority": "P0", "title": f"Corrigir {sec_critical} vulnerabilidade(s) crítica(s)",
                "details": "Ver security.findings no relatório completo",
            })
        if dep_cycles:
            action_plan.append({
                "priority": "P1", "title": f"Resolver {len(dep_cycles)} ciclo(s) de dependência",
                "details": [" → ".join(c) for c in dep_cycles[:3]],
            })
        if cmd_failures:
            action_plan.append({
                "priority": "P1", "title": "Corrigir falhas em comandos locais",
                "details": [f["command"][:80] for f in cmd_failures[:3]],
            })
        if soft_warning_commands:
            action_plan.append({
                "priority": "P2", "title": "Eliminar soft-fails de import avançado",
                "details": [c.get("command", "")[:80] for c in soft_warning_commands[:3]],
            })
        if advanced_missing and confidence > 0.7:
            action_plan.append({
                "priority": "P2", "title": "Instalar stack avançada",
                "commands": [f"pip install {m}" for m in advanced_missing[:5]],
            })
        if not action_plan:
            action_plan.append({
                "priority": "P1", "title": "✅ Ambiente estável",
                "details": "Prosseguir para missões de evolução.",
            })

        hw  = self.detect_hardware_capabilities()
        hw_recs: List[str] = []
        if not hw.has_gpu and not hw.has_mps:
            hw_recs.append("GPU recomendada para LLMs/embeddings")
        if hw.ram_gb < 8:
            hw_recs.append(f"RAM limitada ({hw.ram_gb}GB)")
        if hw.cpu_cores < 4:
            hw_recs.append(f"CPU com apenas {hw.cpu_cores} cores")

        # Alertas de recurso preditivos
        pred_alerts = self._predictor.alerts({
            "cpu_percent": 90.0, "memory_percent": 92.0, "disk_percent": 95.0
        })

        result: Dict[str, Any] = {
            "objective":                objective,
            "status":                   diag["status"],
            "risk_score":               round(risk_score, 3),
            "confidence":               confidence,
            "missing_essential_modules":essential_missing,
            "missing_advanced_modules":advanced_missing,
            "missing_advanced_count":   len(advanced_missing),
            "failing_commands_count":   len(cmd_failures),
            "soft_warning_commands_count": len(soft_warning_commands),
            "dependency_cycles":        len(dep_cycles),
            "security_critical_issues": sec_critical,
            "corrections_applied":      corrections,
            "hardware_recommendations": hw_recs,
            "predictive_alerts":        pred_alerts,
            "recent_alerts":            self._alert_mgr.recent_alerts(5),
            "healing_history":          self._healer.history(5),
            "action_plan":              action_plan,
            "diagnostic_summary":       diag.get("summary", {}),
            "cache_stats":              self._cache.stats(),
            "circuit_breaker":          self._circuit_pip.status(),
            "generated_at":             datetime.now().isoformat(),
        }

        report_path = self._save_report(result, "autopilot")
        result["report_path"] = str(report_path)
        self._aggregator.append(result, label="autopilot")
        logger.info(f"Autopilot: status={result['status']}, confiança={confidence:.1%}")
        return result

    # ──────────────────────────────────────────────────────────────────────
    # ANÁLISE COMPLETA DE MÓDULOS (HEALTH SCORE + DEP GRAPH + SECURITY)
    # ──────────────────────────────────────────────────────────────────────

    def analyze_modules_deep(self) -> Dict[str, Any]:
        """Análise profunda: health scores + dep graph + security + benchmarks."""
        modules_dir = self.root_path / "modules"
        if not modules_dir.exists():
            return {"error": "modules/ não encontrado"}

        self._dep_graph.scan_directory(modules_dir)
        return {
            "health_scores":       self.compute_module_health_scores(modules_dir),
            "dependency_graph":    self._dep_graph.to_dict(),
            "dependency_cycles":   self._dep_graph.detect_cycles(),
            "top_importers":       self._dep_graph.top_importers(5),
            "security":            self._security.audit_directory(modules_dir),
            "import_benchmarks":   self._benchmarker.benchmark_directory(modules_dir, max_files=10),
            "timestamp":           datetime.now().isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────────
    # RELATÓRIOS
    # ──────────────────────────────────────────────────────────────────────

    def _save_report(self, data: Dict[str, Any], prefix: str) -> Path:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.reports_dir / f"{prefix}_{ts}"

        json_path = base.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        try:
            import yaml  # type: ignore
            with open(base.with_suffix(".yaml"), "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        except ImportError:
            pass

        self._save_markdown(data, base.with_suffix(".md"))
        return json_path

    def _save_markdown(self, data: Dict[str, Any], path: Path) -> None:
        ts = data.get("timestamp", datetime.now().isoformat())
        lines = [
            f"# AtenaCodex v5.0 — {ts}",
            f"\n**Status:** `{data.get('status','N/A')}`",
        ]
        if "confidence" in data:
            lines.append(f"  \n**Confiança:** {data['confidence']:.1%}")
        if "risk_score" in data:
            lines.append(f"  \n**Risco:** {data['risk_score']:.1%}")
        s = data.get("summary", {})
        if s:
            lines += [
                "\n## Módulos",
                f"- Essenciais: {s.get('essential_modules_ok','?')}/{s.get('essential_modules_total','?')}",
                f"- Saúde geral: {s.get('overall_health','?')}",
                f"- Segurança: {s.get('security_score','?'):.1f}" if 'security_score' in s else "",
                f"- Ciclos deps: {s.get('dep_cycles_found','?')}",
            ]
        if "action_plan" in data:
            lines += ["\n## Plano de Ação"]
            for item in data["action_plan"]:
                lines.append(f"- **{item.get('priority','?')}** — {item.get('title','?')}")
        try:
            path.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass

    # ──────────────────────────────────────────────────────────────────────
    # RICH OUTPUT
    # ──────────────────────────────────────────────────────────────────────

    def print_rich_summary(self, diagnostic: Dict[str, Any]) -> None:
        if not self._rich:
            self._print_plain_summary(diagnostic)
            return
        from rich.console import Console
        from rich.table   import Table
        from rich.panel   import Panel
        from rich.columns import Columns
        from rich         import box

        console = Console()
        status  = diagnostic.get("status", "?").upper()
        color   = {"OK": "green", "PARTIAL": "yellow", "CRITICAL": "red"}.get(status, "white")
        s       = diagnostic.get("summary", {})

        console.print(Panel(
            f"[bold {color}]{status}[/]\n"
            f"Saúde geral: {s.get('overall_health','?')} | "
            f"Segurança: {s.get('security_score','?')} | "
            f"Ciclos: {s.get('dep_cycles_found','?')}",
            title="🔱 AtenaCodex v5.0",
            subtitle=diagnostic.get("timestamp", ""),
        ))

        # Tabela de módulos essenciais
        t = Table(title="Módulos Essenciais", box=box.ROUNDED, show_lines=True)
        t.add_column("Módulo", style="cyan")
        t.add_column("OK",    justify="center")
        t.add_column("Detalhes")
        t.add_column("ms", justify="right")
        t.add_column("Score", justify="right")
        for m in diagnostic.get("modules", {}).get("essential", []):
            t.add_row(
                m["name"],
                "[green]✅[/]" if m["ok"] else "[red]❌[/]",
                m.get("details","")[:50],
                str(m.get("elapsed_ms","")),
                str(m.get("health_score","")),
            )
        console.print(t)

        # Alertas
        alerts = diagnostic.get("alerts", [])
        if alerts:
            console.print(Panel("\n".join(
                f"[{'red' if a['level']=='critical' else 'yellow'}]{a['message']}[/]"
                for a in alerts
            ), title="🚨 Alertas Recentes", border_style="red"))

    def _print_plain_summary(self, data: Dict[str, Any]) -> None:
        s = data.get("summary", {})
        print(f"\n🔱 AtenaCodex v5.0 — {data.get('status','?').upper()}")
        print(f"  Essenciais  : {s.get('essential_modules_ok','?')}/{s.get('essential_modules_total','?')}")
        print(f"  Saúde geral : {s.get('overall_health','?')}")
        print(f"  Segurança   : {s.get('security_score','?')}")
        print(f"  Dep cycles  : {s.get('dep_cycles_found','?')}")
        print(f"  Relatório   : {data.get('report_path','N/A')}")

    # ──────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_missing_import_from_stderr(stderr: str) -> Optional[str]:
        if not stderr:
            return None
        m = re.search(r"No module named '([^']+)'", stderr)
        return m.group(1) if m else None

    @staticmethod
    def _extract_missing_import(stderr: str) -> Optional[str]:
        return AtenaCodex._extract_missing_import_from_stderr(stderr)

    def _ensure_runtime_dep(self, import_name: str) -> bool:
        pkg = self.RUNTIME_IMPORT_TO_PIP.get(import_name)
        return bool(pkg and self.auto_install_module(pkg))

    def get_system_health(self, from_monitor: bool = True) -> SystemHealth:
        if from_monitor and self._health_monitor and self._health_monitor.latest:
            return self._health_monitor.latest
        return HealthMonitor()._collect()

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.info("Cache limpo")

    def __enter__(self) -> "AtenaCodex":
        return self

    def __exit__(self, *_: Any) -> None:
        if self._health_monitor:
            self._health_monitor.stop()
        if self._reloader:
            self._reloader.stop()
        self._pool.shutdown(wait=False)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="AtenaCodex v5.0 — Diagnóstico e Auto-cura ATENA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--diagnostic",        action="store_true")
    parser.add_argument("--autopilot",         action="store_true")
    parser.add_argument("--smoke",             action="store_true")
    parser.add_argument("--install-essentials",action="store_true")
    parser.add_argument("--hardware",          action="store_true")
    parser.add_argument("--health",            action="store_true")
    parser.add_argument("--security",          action="store_true")
    parser.add_argument("--network",           action="store_true")
    parser.add_argument("--deep-analysis",     action="store_true")
    parser.add_argument("--benchmark",         action="store_true")
    parser.add_argument("--env",               action="store_true")
    parser.add_argument("--workers",  type=int,  default=8)
    parser.add_argument("--json",     action="store_true")
    parser.add_argument("--no-rich",  action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    with AtenaCodex(root_path=root, max_workers=args.workers) as codex:

        def out(data: Any) -> None:
            if args.json:
                print(json.dumps(data, indent=2, default=str))
            else:
                print(data)

        if args.hardware:
            hw = codex.detect_hardware_capabilities()
            out(asdict(hw) if args.json else (
                f"GPU  : {hw.gpu_name or 'N/A'} ({hw.gpu_memory_mb} MiB)\n"
                f"CUDA : {hw.cuda_version or 'N/A'}\n"
                f"MPS  : {'Sim' if hw.has_mps else 'Não'} (Apple Silicon)\n"
                f"CPU  : {hw.cpu_cores} cores @ {hw.cpu_freq_mhz} MHz\n"
                f"RAM  : {hw.ram_gb} GB | Swap: {hw.swap_gb} GB\n"
                f"Disco: {hw.disk_free_gb} GB livres"
            ))
            return 0

        if args.health:
            h = codex.get_system_health(from_monitor=False)
            out(asdict(h) if args.json else (
                f"CPU    : {h.cpu_percent}%\n"
                f"Memória: {h.memory_percent}%  Swap: {h.swap_percent}%\n"
                f"Disco  : {h.disk_percent}%\n"
                f"Temp   : {h.temperature_celsius}°C\n"
                f"Uptime : {h.uptime_seconds//3600}h {(h.uptime_seconds%3600)//60}m\n"
                f"Arquivos abertos: {h.open_files}"
            ))
            return 0

        if args.env:
            out(codex._env_validator.validate())
            return 0

        if args.security:
            modules_dir = root / "modules"
            if modules_dir.exists():
                out(codex._security.audit_directory(modules_dir))
            else:
                print("modules/ não encontrado")
            return 0

        if args.network:
            out(codex._network.run_all())
            return 0

        if args.deep_analysis:
            out(codex.analyze_modules_deep())
            return 0

        if args.benchmark:
            modules_dir = root / "modules"
            if modules_dir.exists():
                out(codex._benchmarker.benchmark_directory(modules_dir))
            return 0

        if args.install_essentials:
            result = codex.ensure_essential_modules(auto_install=True)
            out(result)
            return 0

        if args.smoke:
            result = codex.run_module_smoke_suite()
            out(result if args.json else (
                f"\n📊 Smoke Suite: {result['passed']}/{result['total_checks']} ok\n"
                f"Status: {result['status']}\n"
                f"Falhas: {', '.join(result['failed_modules']) or 'nenhuma'}\n"
                f"Relatório: {result.get('report_path','N/A')}"
            ))
            return 0

        if args.autopilot:
            result = codex.run_advanced_autopilot(
                auto_correct=True,
                include_network=args.network,
            )
            if args.json:
                out(result)
            else:
                print(f"\n🚀 Autopilot v5.0 — {result['objective']}")
                print(f"Status     : {result['status'].upper()}")
                print(f"Confiança  : {result['confidence']:.1%}")
                print(f"Risco      : {result['risk_score']:.1%}")
                print(f"Segurança  : {result['security_critical_issues']} crítico(s)")
                print(f"Dep cycles : {result['dependency_cycles']}")
                if result.get("corrections_applied"):
                    print(f"Correções  : {', '.join(result['corrections_applied'])}")
                if result.get("predictive_alerts"):
                    print(f"Previsões  : {result['predictive_alerts']}")
                print("\n📋 Plano de Ação:")
                for item in result["action_plan"]:
                    print(f"  [{item['priority']}] {item['title']}")
                print(f"\n📄 Relatório: {result['report_path']}")
            return 0

        # Default: diagnóstico completo
        result = codex.run_full_diagnostic(
            include_security=True,
            include_benchmark=args.benchmark,
            include_network=args.network,
        )
        if args.json:
            out(result)
        else:
            if not args.no_rich:
                codex.print_rich_summary(result)
            else:
                codex._print_plain_summary(result)
            print(f"\n⏱  {result.get('elapsed_ms','?')} ms")
            print(f"📄 Relatório: {result.get('report_path','N/A')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(_main())
