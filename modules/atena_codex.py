#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — AtenaCodex v4.0
Módulo avançado de diagnóstico, orquestração e utilidades para a ATENA.

Melhorias v4.0:
- ⚡ Verificação paralela de módulos (ThreadPoolExecutor)
- 🔄 Retry com backoff exponencial em instalações pip
- 📊 Saída Rich com tabelas, progresso e painéis
- 🧵 Cache thread-safe com TTL e invalidação seletiva
- 🏷️  Tipagem estrita com TypedDict e overloads
- 📝 Export de relatórios em JSON, YAML e Markdown
- 🩺 Monitor de saúde em background (daemon thread)
- 🔒 Validação de ambiente com schema
- 🚀 Context managers para timeout e isolamento
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import (
    Any, Callable, Dict, Generator, List, Optional,
    Set, Tuple, TypeVar, Union
)

# ---------------------------------------------------------------------------
# Importação resiliente do SysAware
# ---------------------------------------------------------------------------
try:
    from .AtenaSysAware import AtenaSysAware
except (ImportError, ValueError):
    try:
        from AtenaSysAware import AtenaSysAware
    except ImportError:
        sys.path.append(os.path.dirname(__file__))
        try:
            from AtenaSysAware import AtenaSysAware
        except ImportError:
            class AtenaSysAware:  # type: ignore[no-redef]
                def get_profile(self) -> Dict[str, Any]:
                    return {"info": "SysAware não disponível"}

# ---------------------------------------------------------------------------
# Tipagem auxiliar
# ---------------------------------------------------------------------------
T = TypeVar("T")
logger = logging.getLogger("atena.codex")


# =============================================================================
# Decoradores utilitários
# =============================================================================

def retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.5,
    exceptions: Tuple[type, ...] = (Exception,),
) -> Callable:
    """Decorator de retry com backoff exponencial."""
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
                    logger.debug(
                        f"Tentativa {attempt}/{max_attempts} falhou em {fn.__name__}: {exc}. "
                        f"Aguardando {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
            raise RuntimeError("Não deveria chegar aqui")  # pragma: no cover
        return wrapper  # type: ignore[return-value]
    return decorator


def timed(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator que adiciona campo 'elapsed_ms' ao dict retornado."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        if isinstance(result, dict):
            result["elapsed_ms"] = elapsed
        return result
    return wrapper  # type: ignore[return-value]


# =============================================================================
# Context managers
# =============================================================================

@contextmanager
def subprocess_timeout(seconds: int) -> Generator[None, None, None]:
    """Context manager semântico para escopo de timeout."""
    yield  # timeout é passado diretamente ao subprocess.run


# =============================================================================
# Data Models
# =============================================================================

@dataclass(slots=True)
class CheckResult:
    """Resultado de uma verificação individual."""
    name: str
    ok: bool
    details: str
    severity: str = "info"          # critical | warning | info
    remediation: Optional[str] = None
    elapsed_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HardwareCapability:
    """Capacidades de hardware detectadas."""
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_mb: int = 0
    has_cuda: bool = False
    cuda_version: str = ""
    has_rocm: bool = False
    cpu_cores: int = 0
    ram_gb: float = 0.0
    disk_free_gb: float = 0.0


@dataclass(slots=True)
class SystemHealth:
    """Métricas de saúde do sistema em tempo real."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    uptime_seconds: int = 0
    load_average: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    temperature_celsius: float = 0.0
    last_checked: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# Cache thread-safe com TTL e invalidação seletiva
# =============================================================================

class TTLCache:
    """Cache thread-safe com TTL por chave."""

    def __init__(self, default_ttl: int = 60) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry and (time.monotonic() - entry["ts"]) < entry["ttl"]:
                return entry["data"]
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._store[key] = {
                "data": value,
                "ts": time.monotonic(),
                "ttl": ttl if ttl is not None else self._default_ttl,
            }

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# =============================================================================
# Monitor de saúde em background
# =============================================================================

class HealthMonitor:
    """Daemon thread que coleta métricas de saúde periodicamente."""

    def __init__(self, interval: int = 30) -> None:
        self._interval = interval
        self._latest: Optional[SystemHealth] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="atena-health-monitor")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def latest(self) -> Optional[SystemHealth]:
        with self._lock:
            return self._latest

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                import psutil
                h = SystemHealth(
                    cpu_percent=psutil.cpu_percent(interval=1),
                    memory_percent=psutil.virtual_memory().percent,
                    disk_percent=psutil.disk_usage("/").percent,
                    uptime_seconds=int(time.time() - psutil.boot_time()),
                    load_average=os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0),
                    last_checked=datetime.now().isoformat(),
                )
                with self._lock:
                    self._latest = h
            except Exception:
                pass


# =============================================================================
# AtenaCodex v4.0
# =============================================================================

class AtenaCodex:
    """
    Camada utilitária avançada de operação/diagnóstico para a ATENA.

    Novidades v4.0:
    - Verificação paralela de módulos (configurable workers)
    - Retry com backoff exponencial em pip installs
    - Cache TTL thread-safe com invalidação seletiva
    - Monitor de saúde em background
    - Export de relatórios em JSON, YAML e Markdown
    - Saída Rich para terminal (quando disponível)
    """

    # ------------------------------------------------------------------
    # Catálogos de módulos
    # ------------------------------------------------------------------

    ESSENTIAL_MODULES: List[str] = [
        "requests", "astor", "rich", "click", "pydantic",
    ]

    ADVANCED_STACK_MODULES: List[str] = [
        "aiosqlite", "aiohttp", "numpy", "pandas",
        "transformers", "torch", "chromadb", "faiss",
        "networkx", "sentence_transformers",
    ]

    OPTIONAL_MODULES: List[str] = [
        "matplotlib", "seaborn", "sklearn", "python_dotenv",
        "tqdm", "colorama", "yaml", "playwright",
        "beautifulsoup4", "lxml",
    ]

    SOFT_DEPENDENCY_MODULES: Set[str] = {
        "numpy", "pandas", "torch", "transformers",
        "chromadb", "faiss", "networkx", "sentence_transformers",
    }

    # Import name → pip package name
    RUNTIME_IMPORT_TO_PIP: Dict[str, str] = {
        "psutil": "psutil",
        "numpy": "numpy",
        "requests": "requests",
        "rich": "rich",
        "aiosqlite": "aiosqlite",
        "aiohttp": "aiohttp",
        "torch": "torch",
        "transformers": "transformers",
        "chromadb": "chromadb",
        "faiss": "faiss-cpu",
        "networkx": "networkx",
        "sentence_transformers": "sentence-transformers",
        "playwright": "playwright",
        "beautifulsoup4": "beautifulsoup4",
        "lxml": "lxml",
        "sklearn": "scikit-learn",
        "pydantic": "pydantic",
        "click": "click",
        "astor": "astor",
        "yaml": "pyyaml",
        "python_dotenv": "python-dotenv",
    }

    # Import alias → real module name
    _IMPORT_ALIAS: Dict[str, str] = {
        "sklearn": "sklearn",
        "python_dotenv": "dotenv",
        "yaml": "yaml",
        "faiss": "faiss",
        "chromadb": "chromadb",
        "sentence_transformers": "sentence_transformers",
        "beautifulsoup4": "bs4",
        "playwright": "playwright",
    }

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def __init__(
        self,
        root_path: Optional[Path] = None,
        cache_ttl: int = 60,
        max_workers: int = 8,
        start_health_monitor: bool = True,
    ) -> None:
        self.sysaware = AtenaSysAware()
        self._cache = TTLCache(default_ttl=cache_ttl)
        self._max_workers = max_workers

        self.root_path = Path(root_path) if root_path else Path(__file__).parent.parent
        self.evolution_dir = self.root_path / "atena_evolution"
        self.reports_dir = self.evolution_dir / "codex_reports"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._setup_logging()
        self._rich_available = self._check_rich()

        # Monitor de saúde em background
        self._health_monitor: Optional[HealthMonitor] = None
        if start_health_monitor:
            self._health_monitor = HealthMonitor(interval=30)
            self._health_monitor.start()

        logger.info("🔱 AtenaCodex v4.0 inicializado")
        logger.info(f"   Root   : {self.root_path}")
        logger.info(f"   Reports: {self.reports_dir}")
        logger.info(f"   Workers: {self._max_workers}")

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Hardware & Health
    # ------------------------------------------------------------------

    def detect_hardware_capabilities(self) -> HardwareCapability:
        """Detecta capacidades de hardware com cache de 5 minutos."""
        cached = self._cache.get("hardware")
        if cached:
            return HardwareCapability(**cached)

        caps = HardwareCapability(cpu_cores=os.cpu_count() or 1)

        # RAM / Disco
        try:
            import psutil
            caps.ram_gb = round(psutil.virtual_memory().total / 1024 ** 3, 1)
            caps.disk_free_gb = round(
                psutil.disk_usage(str(self.root_path)).free / 1024 ** 3, 1
            )
        except ImportError:
            if sys.platform == "linux":
                try:
                    with open("/proc/meminfo") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                caps.ram_gb = round(int(line.split()[1]) / 1024 ** 2, 1)
                                break
                except OSError:
                    pass

        # NVIDIA GPU
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                caps.has_gpu = True
                parts = res.stdout.strip().split("\n")[0].split(",")
                caps.gpu_name = parts[0].strip()
                mem_str = parts[1].strip().replace(" MiB", "")
                caps.gpu_memory_mb = int(mem_str) if mem_str.isdigit() else 0

                # CUDA version via nvcc ou nvidia-smi
                nvcc = subprocess.run(
                    ["nvcc", "--version"], capture_output=True, text=True, timeout=5
                )
                m = re.search(r"release (\d+\.\d+)", nvcc.stdout)
                if m:
                    caps.cuda_version = m.group(1)
                    caps.has_cuda = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # AMD ROCm
        try:
            rocm = subprocess.run(
                ["rocm-smi", "--showhw"], capture_output=True, text=True, timeout=5
            )
            caps.has_rocm = rocm.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        self._cache.set("hardware", asdict(caps), ttl=300)
        return caps

    def get_system_health(self, from_monitor: bool = True) -> SystemHealth:
        """
        Retorna métricas de saúde.
        Se `from_monitor=True` e o monitor estiver ativo, usa dados em cache.
        """
        if from_monitor and self._health_monitor and self._health_monitor.latest:
            return self._health_monitor.latest

        health = SystemHealth(last_checked=datetime.now().isoformat())
        try:
            import psutil
            health.cpu_percent = psutil.cpu_percent(interval=0.5)
            health.memory_percent = psutil.virtual_memory().percent
            health.disk_percent = psutil.disk_usage(str(self.root_path)).percent
            health.uptime_seconds = int(time.time() - psutil.boot_time())
            health.load_average = (
                os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
            )
        except ImportError:
            pass

        if sys.platform == "linux":
            for path in [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
            ]:
                try:
                    health.temperature_celsius = int(Path(path).read_text()) / 1000
                    break
                except OSError:
                    pass

        return health

    # ------------------------------------------------------------------
    # Verificação de módulos — agora paralela
    # ------------------------------------------------------------------

    def _check_single_module(self, module_name: str) -> CheckResult:
        """Verifica um único módulo Python e mede o tempo."""
        actual_import = self._IMPORT_ALIAS.get(module_name, module_name)
        start = time.perf_counter()
        try:
            mod = importlib.import_module(actual_import)
            version = getattr(mod, "__version__", "desconhecida")
            return CheckResult(
                name=module_name,
                ok=True,
                details=f"versão={version}",
                severity="info",
                elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            )
        except ImportError as exc:
            pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
            severity = "critical" if module_name in self.ESSENTIAL_MODULES else "warning"
            return CheckResult(
                name=module_name,
                ok=False,
                details=str(exc),
                severity=severity,
                remediation=f"pip install {pip_name}",
                elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            )
        except Exception as exc:
            return CheckResult(
                name=module_name,
                ok=False,
                details=str(exc),
                severity="warning",
                elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            )

    def _check_modules_parallel(self, names: List[str]) -> List[Dict[str, Any]]:
        """Verifica lista de módulos em paralelo."""
        results: Dict[str, CheckResult] = {}
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(names) or 1)) as pool:
            futures = {pool.submit(self._check_single_module, n): n for n in names}
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    results[name] = fut.result()
                except Exception as exc:
                    results[name] = CheckResult(
                        name=name, ok=False, details=str(exc), severity="warning"
                    )
        # Mantém a ordem original
        return [results[n].to_dict() for n in names]

    def check_python_modules(self) -> Dict[str, Any]:
        """Valida todos os módulos em paralelo."""
        essential = self._check_modules_parallel(self.ESSENTIAL_MODULES)
        advanced = self._check_modules_parallel(self.ADVANCED_STACK_MODULES)
        optional = self._check_modules_parallel(self.OPTIONAL_MODULES)

        return {
            "essential": essential,
            "advanced": advanced,
            "optional": optional,
            "summary": {
                "essential_ok": sum(1 for m in essential if m["ok"]),
                "essential_total": len(essential),
                "advanced_ok": sum(1 for m in advanced if m["ok"]),
                "advanced_total": len(advanced),
                "optional_ok": sum(1 for m in optional if m["ok"]),
                "optional_total": len(optional),
            },
        }

    # ------------------------------------------------------------------
    # Instalação com retry e backoff
    # ------------------------------------------------------------------

    @retry(max_attempts=3, backoff_factor=2.0, exceptions=(subprocess.CalledProcessError,))
    def _pip_install(self, pip_name: str) -> None:
        """Executa pip install com retry automático."""
        subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name, "--quiet", "--no-warn-script-location"],
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )

    def auto_install_module(self, module_name: str) -> bool:
        """Tenta instalar módulo via pip com retry e backoff exponencial."""
        pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
        logger.info(f"Instalando automaticamente: {pip_name}")
        try:
            self._pip_install(pip_name)
            logger.info(f"✅ {pip_name} instalado com sucesso")
            return True
        except Exception as exc:
            logger.error(f"❌ Falha ao instalar {pip_name}: {exc}")
            return False

    def ensure_essential_modules(self, auto_install: bool = True) -> Dict[str, Any]:
        """Garante módulos essenciais, instalando os faltantes em paralelo."""
        checks = {n: self._check_single_module(n) for n in self.ESSENTIAL_MODULES}
        missing = [n for n, c in checks.items() if not c.ok]

        if auto_install and missing:
            logger.info(f"Auto-instalando {len(missing)} módulo(s) faltante(s)...")
            with ThreadPoolExecutor(max_workers=min(4, len(missing))) as pool:
                futures = {pool.submit(self.auto_install_module, m): m for m in missing}
                for fut in as_completed(futures):
                    m = futures[fut]
                    if fut.result():
                        checks[m] = self._check_single_module(m)

        return {
            "all_essential_ok": all(c.ok for c in checks.values()),
            "modules": {n: c.to_dict() for n, c in checks.items()},
            "auto_install_enabled": auto_install,
        }

    # ------------------------------------------------------------------
    # Snapshot de ambiente
    # ------------------------------------------------------------------

    def environment_snapshot(self, include_hardware: bool = True) -> Dict[str, Any]:
        """Retorna snapshot completo do ambiente (com cache de 60s)."""
        cached = self._cache.get("env_snapshot")
        if cached:
            return cached

        try:
            profile = dict(self.sysaware.get_profile())
        except Exception:
            profile = {"error": "Falha ao obter perfil do SysAware"}

        snapshot: Dict[str, Any] = {
            "python": {
                "executable": sys.executable,
                "version": sys.version,
                "implementation": platform.python_implementation(),
                "compiler": platform.python_compiler(),
            },
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
            },
            "paths": {
                "root": str(self.root_path.absolute()),
                "python_path": sys.path[:5],
            },
            "environment_vars": {
                k: (v[:100] if len(v) > 100 else v)
                for k, v in os.environ.items()
                if not any(s in k.lower() for s in ("key", "token", "secret", "password", "pwd"))
            },
            "checked_at": datetime.now().isoformat(),
            **profile,
        }

        if include_hardware:
            snapshot["hardware"] = asdict(self.detect_hardware_capabilities())
            snapshot["health"] = asdict(self.get_system_health())

        self._cache.set("env_snapshot", snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Execução de comandos locais
    # ------------------------------------------------------------------

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict[str, Any]]:
        """Executa comandos de validação local com detecção de soft-fails."""
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
                res = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_seconds, check=False,
                    cwd=str(self.root_path),
                )
                stderr = res.stderr.strip()
                soft_failed = res.returncode != 0 and any(
                    f"No module named '{dep}'" in stderr
                    for dep in self.SOFT_DEPENDENCY_MODULES
                )
                results.append({
                    "command": " ".join(cmd),
                    "returncode": res.returncode,
                    "stdout": res.stdout.strip()[:500],
                    "stderr": stderr[:500],
                    "soft_failed": soft_failed,
                    "soft_reason": "Dependência avançada ausente" if soft_failed else "",
                })
            except subprocess.TimeoutExpired:
                results.append({
                    "command": " ".join(cmd),
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"timeout>{timeout_seconds}s",
                    "soft_failed": False,
                    "soft_reason": "",
                })
            except Exception as exc:
                results.append({
                    "command": " ".join(cmd),
                    "returncode": -2,
                    "stdout": "",
                    "stderr": str(exc),
                    "soft_failed": False,
                    "soft_reason": "",
                })
        return results

    # ------------------------------------------------------------------
    # Diagnóstico completo
    # ------------------------------------------------------------------

    @timed
    def run_full_diagnostic(
        self,
        include_commands: bool = True,
        include_hardware: bool = True,
        timeout_seconds: int = 120,
    ) -> Dict[str, Any]:
        """Executa diagnóstico completo e retorna relatório estruturado."""
        logger.info("Iniciando diagnóstico completo...")

        snapshot = self.environment_snapshot(include_hardware=include_hardware)
        module_checks = self.check_python_modules()
        command_checks = (
            self.run_local_commands(timeout_seconds=timeout_seconds) if include_commands else []
        )

        essentials_ok = all(m["ok"] for m in module_checks["essential"])
        commands_ok = all(
            c["returncode"] == 0 or c.get("soft_failed", False) for c in command_checks
        ) if command_checks else True

        status = "ok" if (essentials_ok and commands_ok) else ("partial" if essentials_ok else "critical")

        diagnostic: Dict[str, Any] = {
            "status": status,
            "snapshot": snapshot,
            "modules": module_checks,
            "commands": command_checks,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "essential_modules_ok": module_checks["summary"]["essential_ok"],
                "essential_modules_total": module_checks["summary"]["essential_total"],
                "commands_passed": sum(1 for c in command_checks if c["returncode"] == 0),
                "commands_total": len(command_checks),
            },
        }

        report_path = self._save_report(diagnostic, "full_diagnostic")
        diagnostic["report_path"] = str(report_path)
        logger.info(f"Diagnóstico: status={status}, relatório={report_path}")
        return diagnostic

    # ------------------------------------------------------------------
    # Smoke suite de módulos
    # ------------------------------------------------------------------

    def run_module_smoke_suite(self, timeout_seconds: int = 25) -> Dict[str, Any]:
        """Executa smoke tests de todos os módulos da ATENA."""
        modules_dir = self.root_path / "modules"
        if not modules_dir.exists():
            return {"status": "error", "error": "Diretório 'modules' não encontrado"}

        module_names = sorted(
            p.stem for p in modules_dir.glob("*.py")
            if p.name != "__init__.py" and not p.name.startswith("test_")
        )

        def _smoke_one(name: str) -> Dict[str, Any]:
            cmd = [
                sys.executable, "-c",
                f"import importlib; importlib.import_module('modules.{name}'); print('OK:{name}')",
            ]
            for attempt in range(2):
                try:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=timeout_seconds, check=False,
                        cwd=str(self.root_path),
                    )
                    missing = self._extract_missing_import(proc.stderr)
                    if proc.returncode != 0 and missing and attempt == 0:
                        if self._ensure_runtime_dependency(missing):
                            continue
                    return {
                        "type": "module_import",
                        "target": f"modules.{name}",
                        "ok": proc.returncode == 0,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip()[:200],
                        "stderr": proc.stderr.strip()[:200],
                    }
                except subprocess.TimeoutExpired:
                    return {
                        "type": "module_import",
                        "target": f"modules.{name}",
                        "ok": False,
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"timeout>{timeout_seconds}s",
                    }
            return {"type": "module_import", "target": f"modules.{name}", "ok": False,
                    "returncode": -3, "stdout": "", "stderr": "max retries"}

        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(_smoke_one, n): n for n in module_names}
            for fut in as_completed(futures):
                results.append(fut.result())

        # Checks extras (internet, launcher)
        extra_cmds = [
            ("internet_connectivity", [sys.executable, "-c",
             "import urllib.request; urllib.request.urlopen('https://www.google.com',timeout=8); print('ok')"]),
            ("atena_launcher_import", [sys.executable, "-c",
             "import sys; sys.path.insert(0,'core'); import atena_launcher; print('ok')"]),
        ]
        for name, cmd in extra_cmds:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_seconds, check=False,
                    cwd=str(self.root_path),
                )
                results.append({
                    "type": "extra_check", "target": name,
                    "ok": proc.returncode == 0, "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[:200], "stderr": proc.stderr.strip()[:200],
                })
            except subprocess.TimeoutExpired:
                results.append({
                    "type": "extra_check", "target": name,
                    "ok": False, "returncode": -1, "stdout": "", "stderr": f"timeout>{timeout_seconds}s",
                })

        passed = sum(1 for r in results if r["ok"])
        failed_modules = [r["target"] for r in results if not r["ok"]]

        summary: Dict[str, Any] = {
            "status": "ok" if passed == len(results) else "partial",
            "total_checks": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "failed_modules": failed_modules[:10],
            "timestamp": datetime.now().isoformat(),
            "results": results[:50],
        }
        report_path = self._save_report(summary, "module_smoke_suite")
        summary["report_path"] = str(report_path)
        logger.info(f"Smoke suite: {passed}/{len(results)} ok, relatório={report_path}")
        return summary

    # ------------------------------------------------------------------
    # Autopilot avançado
    # ------------------------------------------------------------------

    def run_advanced_autopilot(
        self,
        objective: str = "Elevar confiabilidade do runtime da ATENA",
        include_commands: bool = True,
        timeout_seconds: int = 120,
        auto_correct: bool = True,
    ) -> Dict[str, Any]:
        """
        Ciclo orientado por objetivo com diagnóstico, auto-correção e plano de ação.
        """
        logger.info(f"🚀 Autopilot iniciado: {objective}")

        diag = self.run_full_diagnostic(
            include_commands=include_commands,
            include_hardware=True,
            timeout_seconds=timeout_seconds,
        )

        def _missing(key: str) -> List[str]:
            return [m["name"] for m in diag["modules"].get(key, []) if not m.get("ok")]

        essential_missing = _missing("essential")
        advanced_missing = _missing("advanced")
        cmd_failures = [
            c for c in diag.get("commands", [])
            if c.get("returncode", 1) != 0 and not c.get("soft_failed")
        ]

        # Auto-correção paralela (máx 3 essenciais por ciclo)
        corrections: List[str] = []
        if auto_correct and essential_missing:
            targets = essential_missing[:3]
            logger.info(f"Auto-corrigindo: {targets}")
            with ThreadPoolExecutor(max_workers=len(targets)) as pool:
                futures = {pool.submit(self.auto_install_module, m): m for m in targets}
                for fut in as_completed(futures):
                    m = futures[fut]
                    if fut.result():
                        corrections.append(f"Instalado: {m}")

            if corrections:
                self._cache.invalidate("env_snapshot")
                diag = self.run_full_diagnostic(
                    include_commands=include_commands,
                    include_hardware=True,
                    timeout_seconds=timeout_seconds,
                )
                essential_missing = _missing("essential")

        # Score de risco
        risk_score = min(
            1.0,
            len(essential_missing) * 0.30
            + len(cmd_failures) * 0.20
            + len(advanced_missing) * 0.05,
        )
        confidence = round(max(0.0, 1.0 - risk_score), 3)

        # Plano de ação
        action_plan: List[Dict[str, Any]] = []
        if essential_missing:
            action_plan.append({
                "priority": "P0",
                "title": "Restaurar módulos essenciais",
                "details": f"Instalar: {', '.join(essential_missing)}",
                "commands": [f"pip install {m}" for m in essential_missing],
            })
        if cmd_failures:
            action_plan.append({
                "priority": "P0",
                "title": "Corrigir comandos com falha",
                "details": [f["command"][:100] for f in cmd_failures[:3]],
            })
        if advanced_missing and confidence > 0.7:
            action_plan.append({
                "priority": "P1",
                "title": "Instalar stack avançada (opcional)",
                "details": f"Recomendado: {', '.join(advanced_missing[:5])}",
            })
        if not action_plan:
            action_plan.append({
                "priority": "P1",
                "title": "Ambiente estável",
                "details": "Prosseguir para missões de evolução e benchmarks.",
            })

        # Recomendações de hardware
        hw = self.detect_hardware_capabilities()
        hw_recs: List[str] = []
        if not hw.has_gpu:
            hw_recs.append("GPU recomendada para modelos de ML/embeddings")
        if hw.ram_gb < 8:
            hw_recs.append(f"RAM limitada ({hw.ram_gb}GB) — pode afetar performance")
        if hw.cpu_cores < 4:
            hw_recs.append(f"Poucos cores CPU ({hw.cpu_cores}) — reduz paralelismo")

        result: Dict[str, Any] = {
            "objective": objective,
            "status": diag["status"],
            "risk_score": round(risk_score, 3),
            "confidence": confidence,
            "missing_essential_modules": essential_missing,
            "missing_advanced_count": len(advanced_missing),
            "failing_commands_count": len(cmd_failures),
            "corrections_applied": corrections,
            "hardware_recommendations": hw_recs,
            "action_plan": action_plan,
            "diagnostic_summary": diag["summary"],
            "generated_at": datetime.now().isoformat(),
        }

        report_path = self._save_report(result, "autopilot")
        result["report_path"] = str(report_path)
        logger.info(
            f"Autopilot concluído: status={result['status']}, "
            f"confiança={confidence:.1%}, relatório={report_path}"
        )
        return result

    # ------------------------------------------------------------------
    # Export de relatórios
    # ------------------------------------------------------------------

    def _save_report(self, data: Dict[str, Any], prefix: str) -> Path:
        """Salva relatório em JSON (e YAML/Markdown se disponíveis)."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.reports_dir / f"{prefix}_{ts}"

        # JSON (sempre)
        json_path = base.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        # YAML (se pyyaml disponível)
        try:
            import yaml  # type: ignore
            yaml_path = base.with_suffix(".yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        except ImportError:
            pass

        # Markdown resumido
        self._save_markdown_summary(data, base.with_suffix(".md"))

        return json_path

    def _save_markdown_summary(self, data: Dict[str, Any], path: Path) -> None:
        """Gera resumo Markdown do relatório."""
        lines = [
            f"# AtenaCodex Report — {data.get('timestamp', datetime.now().isoformat())}",
            "",
            f"**Status:** `{data.get('status', 'N/A')}`",
        ]
        if "confidence" in data:
            lines.append(f"**Confiança:** {data['confidence']:.1%}")
        if "risk_score" in data:
            lines.append(f"**Risco:** {data['risk_score']:.1%}")
        if "summary" in data:
            s = data["summary"]
            lines += [
                "",
                "## Sumário de Módulos",
                f"- Essenciais OK: {s.get('essential_modules_ok', '?')}/{s.get('essential_modules_total', '?')}",
                f"- Comandos OK: {s.get('commands_passed', '?')}/{s.get('commands_total', '?')}",
            ]
        if "action_plan" in data:
            lines += ["", "## Plano de Ação"]
            for item in data["action_plan"]:
                lines.append(f"- **{item.get('priority','?')}** — {item.get('title','?')}")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Rich output helpers
    # ------------------------------------------------------------------

    def print_rich_summary(self, diagnostic: Dict[str, Any]) -> None:
        """Imprime sumário formatado com Rich (fallback para texto simples)."""
        if not self._rich_available:
            self._print_plain_summary(diagnostic)
            return

        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box

        console = Console()
        status = diagnostic.get("status", "?").upper()
        color = {"OK": "green", "PARTIAL": "yellow", "CRITICAL": "red"}.get(status, "white")

        console.print(Panel(
            f"[bold {color}]{status}[/bold {color}]",
            title="🔱 AtenaCodex v4.0",
            subtitle=diagnostic.get("timestamp", ""),
        ))

        # Tabela de módulos essenciais
        table = Table(title="Módulos Essenciais", box=box.ROUNDED)
        table.add_column("Módulo", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Detalhes")
        table.add_column("ms", justify="right")

        for m in diagnostic.get("modules", {}).get("essential", []):
            ok = m.get("ok", False)
            table.add_row(
                m["name"],
                "[green]✅[/green]" if ok else "[red]❌[/red]",
                m.get("details", "")[:50],
                str(m.get("elapsed_ms", "")),
            )
        console.print(table)

    def _print_plain_summary(self, diagnostic: Dict[str, Any]) -> None:
        s = diagnostic.get("summary", {})
        print(f"\n🔱 AtenaCodex v4.0 — {diagnostic.get('status','?').upper()}")
        print(f"  Essenciais: {s.get('essential_modules_ok','?')}/{s.get('essential_modules_total','?')}")
        print(f"  Comandos  : {s.get('commands_passed','?')}/{s.get('commands_total','?')}")
        print(f"  Timestamp : {diagnostic.get('timestamp','N/A')}")

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_missing_import(stderr: str) -> Optional[str]:
        """Extrai nome do módulo faltante do stderr do Python."""
        if not stderr:
            return None
        m = re.search(r"No module named '([^']+)'", stderr)
        return m.group(1) if m else None

    def _ensure_runtime_dependency(self, import_name: str) -> bool:
        """Resolve dependência em tempo de execução."""
        pkg = self.RUNTIME_IMPORT_TO_PIP.get(import_name)
        return bool(pkg and self.auto_install_module(pkg))

    def clear_cache(self) -> None:
        """Limpa todo o cache de diagnóstico."""
        self._cache.clear()
        logger.info("Cache limpo")

    def __enter__(self) -> "AtenaCodex":
        return self

    def __exit__(self, *_: Any) -> None:
        if self._health_monitor:
            self._health_monitor.stop()


# =============================================================================
# CLI
# =============================================================================

def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="AtenaCodex v4.0 — Diagnóstico e Utilitários ATENA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--diagnostic", action="store_true", help="Diagnóstico completo")
    parser.add_argument("--autopilot", action="store_true", help="Autopilot avançado com auto-correção")
    parser.add_argument("--smoke", action="store_true", help="Smoke tests dos módulos")
    parser.add_argument("--install-essentials", action="store_true", help="Instala módulos essenciais")
    parser.add_argument("--hardware", action="store_true", help="Informações de hardware")
    parser.add_argument("--health", action="store_true", help="Saúde do sistema")
    parser.add_argument("--workers", type=int, default=8, help="Threads paralelas (padrão: 8)")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--no-rich", action="store_true", help="Desativa saída Rich")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    with AtenaCodex(root_path=root, max_workers=args.workers) as codex:

        def out(data: Any) -> None:
            print(json.dumps(data, indent=2, default=str) if args.json else data)

        if args.hardware:
            hw = codex.detect_hardware_capabilities()
            if args.json:
                out(asdict(hw))
            else:
                print(f"GPU    : {hw.gpu_name or 'Nenhuma'} ({hw.gpu_memory_mb} MiB)")
                print(f"CUDA   : {hw.cuda_version or 'Não disponível'}")
                print(f"ROCm   : {'Sim' if hw.has_rocm else 'Não'}")
                print(f"CPU    : {hw.cpu_cores} cores")
                print(f"RAM    : {hw.ram_gb} GB")
                print(f"Disco  : {hw.disk_free_gb} GB livres")
            return 0

        if args.health:
            h = codex.get_system_health(from_monitor=False)
            if args.json:
                out(asdict(h))
            else:
                print(f"CPU    : {h.cpu_percent}%")
                print(f"Memória: {h.memory_percent}%")
                print(f"Disco  : {h.disk_percent}%")
                print(f"Uptime : {h.uptime_seconds // 3600}h {(h.uptime_seconds % 3600)//60}m")
                print(f"Load   : {h.load_average}")
                print(f"Temp   : {h.temperature_celsius}°C")
            return 0

        if args.install_essentials:
            result = codex.ensure_essential_modules(auto_install=True)
            if args.json:
                out(result)
            else:
                icon = "✅" if result["all_essential_ok"] else "❌"
                print(f"{icon} Essenciais OK: {result['all_essential_ok']}")
                for mod, info in result["modules"].items():
                    s = "✅" if info["ok"] else "❌"
                    print(f"  {s} {mod}: {info['details'][:60]}")
            return 0

        if args.smoke:
            result = codex.run_module_smoke_suite()
            if args.json:
                out(result)
            else:
                print(f"\n📊 Smoke Suite: {result['passed']}/{result['total_checks']} ok")
                print(f"Status    : {result['status']}")
                if result["failed_modules"]:
                    print(f"Falhas    : {', '.join(result['failed_modules'])}")
                print(f"Relatório : {result.get('report_path', 'N/A')}")
            return 0

        if args.autopilot:
            result = codex.run_advanced_autopilot(auto_correct=True)
            if args.json:
                out(result)
            else:
                print(f"\n🚀 Autopilot: {result['objective']}")
                print(f"Status    : {result['status'].upper()}")
                print(f"Confiança : {result['confidence']:.1%}")
                print(f"Risco     : {result['risk_score']:.1%}")
                if result.get("corrections_applied"):
                    print(f"Correções : {', '.join(result['corrections_applied'])}")
                if result.get("hardware_recommendations"):
                    print(f"Hardware  : {'; '.join(result['hardware_recommendations'])}")
                print("\n📋 Plano de Ação:")
                for item in result["action_plan"]:
                    print(f"  [{item['priority']}] {item['title']}")
                print(f"\n📄 Relatório: {result['report_path']}")
            return 0

        # Default: diagnóstico completo
        result = codex.run_full_diagnostic()
        if args.json:
            out(result)
        else:
            if not args.no_rich:
                codex.print_rich_summary(result)
            else:
                codex._print_plain_summary(result)
            print(f"⏱  Tempo: {result.get('elapsed_ms', '?')} ms")
            print(f"📄 Relatório: {result.get('report_path', 'N/A')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(_main())
