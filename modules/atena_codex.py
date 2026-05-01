#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — AtenaCodex v3.0
Módulo avançado de diagnóstico, orquestração e utilidades para a ATENA.

Recursos:
- 🩺 Diagnóstico completo do ambiente e dependências
- 🔧 Auto-recuperação de módulos faltantes
- 📊 Telemetria e métricas de saúde do sistema
- 🧠 Análise de compatibilidade de hardware/software
- 🔄 Auto-atualização de dependências
- 📝 Geração de relatórios executivos
- 🚀 Modo autopilot para correção automática
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
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Suporte para importação resiliente
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
            class AtenaSysAware:
                def get_profile(self) -> Dict:
                    return {"info": "SysAware não disponível"}

logger = logging.getLogger("atena.codex")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CheckResult:
    """Resultado de uma verificação individual."""
    name: str
    ok: bool
    details: str
    severity: str = "info"  # critical, warning, info
    remediation: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class HardwareCapability:
    """Informações sobre capacidade de hardware."""
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_mb: int = 0
    has_cuda: bool = False
    cuda_version: str = ""
    has_rocm: bool = False
    cpu_cores: int = 0
    ram_gb: float = 0.0
    disk_free_gb: float = 0.0


@dataclass
class SystemHealth:
    """Métricas de saúde do sistema."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    uptime_seconds: int = 0
    load_average: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    temperature_celsius: float = 0.0
    last_checked: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# AtenaCodex Principal
# =============================================================================

class AtenaCodex:
    """
    Camada utilitária avançada de operação/diagnóstico para a ATENA.
    Suporta auto-recuperação, telemetria e análise de compatibilidade.
    """

    # Módulos obrigatórios para o núcleo operacional da ATENA
    ESSENTIAL_MODULES = [
        "requests",
        "astor",
        "rich",
        "click",
        "pydantic",
    ]

    # Stack avançada recomendada para recursos de alto desempenho
    ADVANCED_STACK_MODULES = [
        "aiosqlite",
        "aiohttp",
        "numpy",
        "pandas",
        "transformers",
        "torch",
        "chromadb",
        "faiss",
        "networkx",
        "sentence_transformers",
    ]

    # Módulos opcionais com benefícios específicos
    OPTIONAL_MODULES = [
        "matplotlib",
        "seaborn",
        "sklearn",
        "python_dotenv",
        "tqdm",
        "colorama",
        "yaml",
        "playwright",
        "beautifulsoup4",
        "lxml",
    ]

    # Dependências soft que podem ser instaladas sob demanda
    SOFT_DEPENDENCY_MODULES = {
        "numpy",
        "pandas",
        "torch",
        "transformers",
        "chromadb",
        "faiss",
        "networkx",
        "sentence_transformers",
    }

    # Mapeamento de import para nome do pacote pip
    RUNTIME_IMPORT_TO_PIP = {
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
    }

    def __init__(self, root_path: Optional[Path] = None):
        self.sysaware = AtenaSysAware()
        self._lock = threading.RLock()
        self._diagnostic_cache: Dict[str, Any] = {}
        self._cache_ttl: int = 60  # segundos
        
        # Define a raiz do projeto
        if root_path:
            self.root_path = Path(root_path)
        else:
            # Assume que estamos em /modules/ e a raiz é um nível acima
            self.root_path = Path(__file__).parent.parent
        
        # Diretórios de saída
        self.evolution_dir = self.root_path / "atena_evolution"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = self.evolution_dir / "codex_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuração de logging
        self._setup_logging()
        
        logger.info("🔱 AtenaCodex v3.0 inicializado")
        logger.info(f"   Root: {self.root_path}")
        logger.info(f"   Reports: {self.reports_dir}")

    def _setup_logging(self):
        """Configura logging estruturado."""
        log_file = self.evolution_dir / "codex.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
        ))
        logger.addHandler(file_handler)

    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se cache ainda é válido."""
        if key not in self._diagnostic_cache:
            return False
        cached_time = self._diagnostic_cache[key].get("timestamp", 0)
        return (time.time() - cached_time) < self._cache_ttl

    def _cache_set(self, key: str, value: Any):
        """Armazena valor em cache."""
        self._diagnostic_cache[key] = {"data": value, "timestamp": time.time()}

    def _cache_get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache."""
        if self._is_cache_valid(key):
            return self._diagnostic_cache[key]["data"]
        return None

    # =========================================================================
    # Hardware Detection
    # =========================================================================

    def detect_hardware_capabilities(self) -> HardwareCapability:
        """Detecta capacidades de hardware (GPU, CPU, RAM, etc.)."""
        caps = HardwareCapability()
        
        # CPU cores
        caps.cpu_cores = os.cpu_count() or 1
        
        # RAM detection
        try:
            import psutil
            caps.ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            caps.disk_free_gb = round(psutil.disk_usage(str(self.root_path)).free / (1024**3), 1)
        except ImportError:
            # Fallback para Linux
            if sys.platform == "linux":
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_kb = int(line.split()[1])
                            caps.ram_gb = round(mem_kb / (1024**2), 1)
                            break
        
        # GPU detection (NVIDIA CUDA)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout:
                caps.has_gpu = True
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    caps.gpu_name = parts[0].strip()
                    mem_str = parts[1].strip().replace(' MiB', '')
                    caps.gpu_memory_mb = int(mem_str) if mem_str.isdigit() else 0
                
                # CUDA version
                result = subprocess.run(
                    ["nvidia-smi", "--query", "--format=csv"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if "CUDA Version" in line:
                        caps.cuda_version = re.search(r'(\d+\.\d+)', line).group(1) if re.search(r'(\d+\.\d+)', line) else ""
                        caps.has_cuda = bool(caps.cuda_version)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # AMD ROCm detection
        try:
            result = subprocess.run(
                ["rocm-smi", "--showhw"],
                capture_output=True,
                text=True,
                timeout=5
            )
            caps.has_rocm = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        logger.debug(f"Hardware detectado: GPU={caps.has_gpu}, CPU={caps.cpu_cores}, RAM={caps.ram_gb}GB")
        return caps

    def get_system_health(self) -> SystemHealth:
        """Obtém métricas de saúde do sistema em tempo real."""
        health = SystemHealth()
        
        try:
            import psutil
            health.cpu_percent = psutil.cpu_percent(interval=1)
            health.memory_percent = psutil.virtual_memory().percent
            health.disk_percent = psutil.disk_usage(str(self.root_path)).percent
            health.uptime_seconds = int(time.time() - psutil.boot_time())
            health.load_average = os.getloadavg() if hasattr(os, 'getloadavg') else (0.0, 0.0, 0.0)
        except ImportError:
            pass
        
        # Temperature (Linux)
        if sys.platform == "linux":
            try:
                temp_paths = [
                    "/sys/class/thermal/thermal_zone0/temp",
                    "/sys/class/hwmon/hwmon0/temp1_input"
                ]
                for path in temp_paths:
                    if Path(path).exists():
                        temp_raw = int(Path(path).read_text().strip()) / 1000
                        health.temperature_celsius = temp_raw
                        break
            except Exception:
                pass
        
        health.last_checked = datetime.now().isoformat()
        return health

    # =========================================================================
    # Module Checks
    # =========================================================================

    def _check_single_module(self, module_name: str) -> CheckResult:
        """Verifica um único módulo Python."""
        import_map = {
            "sklearn": "sklearn",
            "python_dotenv": "dotenv",
            "yaml": "yaml",
            "faiss": "faiss",
            "chromadb": "chromadb",
            "sentence_transformers": "sentence_transformers",
            "beautifulsoup4": "bs4",
            "playwright": "playwright",
        }
        
        actual_import = import_map.get(module_name, module_name)
        
        try:
            module = importlib.import_module(actual_import)
            version = getattr(module, "__version__", getattr(module, "__version__", "desconhecida"))
            return CheckResult(
                name=module_name,
                ok=True,
                details=f"versão={version}",
                severity="info",
                remediation=None
            )
        except ImportError as e:
            pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
            remediation = f"pip install {pip_name}"
            severity = "critical" if module_name in self.ESSENTIAL_MODULES else "warning"
            return CheckResult(
                name=module_name,
                ok=False,
                details=str(e),
                severity=severity,
                remediation=remediation
            )
        except Exception as e:
            return CheckResult(
                name=module_name,
                ok=False,
                details=str(e),
                severity="warning",
                remediation=None
            )

    def check_python_modules(self) -> Dict[str, List[Dict]]:
        """Valida módulos essenciais, avançados e opcionais."""
        essential = [self._check_single_module(name).to_dict() for name in self.ESSENTIAL_MODULES]
        advanced = [self._check_single_module(name).to_dict() for name in self.ADVANCED_STACK_MODULES]
        optional = [self._check_single_module(name).to_dict() for name in self.OPTIONAL_MODULES]
        
        return {
            "essential": essential,
            "advanced": advanced,
            "optional": optional,
            "summary": {
                "essential_ok": sum(1 for m in essential if m["ok"]),
                "essential_total": len(essential),
                "advanced_ok": sum(1 for m in advanced if m["ok"]),
                "advanced_total": len(advanced),
            }
        }

    def auto_install_module(self, module_name: str) -> bool:
        """
        Tenta instalar módulo automaticamente via pip.
        
        Args:
            module_name: Nome do módulo (pode ser nome pip ou import)
        
        Returns:
            True se instalado com sucesso
        """
        pip_name = self.RUNTIME_IMPORT_TO_PIP.get(module_name, module_name)
        
        logger.info(f"Tentando instalar automaticamente: {pip_name}")
        
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
                check=True
            )
            logger.info(f"✅ Módulo instalado: {pip_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Falha ao instalar {pip_name}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao instalar {pip_name}: {e}")
            return False

    def ensure_essential_modules(self, auto_install: bool = True) -> Dict[str, Any]:
        """Garante que módulos essenciais estão disponíveis."""
        results = {}
        
        for module in self.ESSENTIAL_MODULES:
            check = self._check_single_module(module)
            results[module] = check.to_dict()
            
            if not check.ok and auto_install:
                if self.auto_install_module(module):
                    # Re-verifica após instalação
                    check = self._check_single_module(module)
                    results[module] = check.to_dict()
        
        all_ok = all(r["ok"] for r in results.values())
        
        return {
            "all_essential_ok": all_ok,
            "modules": results,
            "auto_install_enabled": auto_install
        }

    # =========================================================================
    # Environment Snapshot
    # =========================================================================

    def environment_snapshot(self, include_hardware: bool = True) -> Dict:
        """Retorna snapshot completo do ambiente."""
        cached = self._cache_get("environment_snapshot")
        if cached:
            return cached
        
        try:
            profile = dict(self.sysaware.get_profile())
        except Exception:
            profile = {"error": "Falha ao obter perfil do SysAware"}
        
        snapshot = {
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
                k: v[:100] if len(v) > 100 else v
                for k, v in os.environ.items()
                if not any(secret in k.lower() for secret in ["key", "token", "secret", "password"])
            },
            "checked_at": datetime.now().isoformat(),
            **profile,
        }
        
        if include_hardware:
            snapshot["hardware"] = asdict(self.detect_hardware_capabilities())
            snapshot["health"] = asdict(self.get_system_health())
        
        self._cache_set("environment_snapshot", snapshot)
        return snapshot

    # =========================================================================
    # Command Execution
    # =========================================================================

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict]:
        """Executa comandos seguros de validação local."""
        targets = [
            "core/atena_launcher.py",
            "core/atena_terminal_assistant.py",
            "modules"
        ]
        existing_targets = [t for t in targets if (self.root_path / t).exists()]
        
        commands = []
        if existing_targets:
            commands.append([sys.executable, "-m", "compileall", "-q"] + existing_targets)
        
        # Validação de import do launcher
        commands.append([
            sys.executable, "-c",
            "import sys; sys.path.insert(0, 'core'); import atena_launcher; print('Launcher Import: OK')"
        ])
        
        # Validação do codex
        commands.append([
            sys.executable, "-c",
            "import sys; sys.path.insert(0, 'modules'); from AtenaCodex import AtenaCodex; print('AtenaCodex Import: OK')"
        ])
        
        results = []
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                    cwd=str(self.root_path)
                )
                cmd_str = " ".join(cmd)
                stderr = result.stderr.strip()
                
                soft_failed = False
                soft_reason = ""
                
                # Detecta soft-fails (dependências opcionais faltando)
                if result.returncode != 0:
                    missing_soft_dep = any(
                        f"No module named '{dep}'" in stderr 
                        for dep in self.SOFT_DEPENDENCY_MODULES
                    )
                    if missing_soft_dep:
                        soft_failed = True
                        soft_reason = "Dependência avançada ausente para import opcional"

                results.append({
                    "command": cmd_str,
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip()[:500],
                    "stderr": stderr[:500],
                    "soft_failed": soft_failed,
                    "soft_reason": soft_reason,
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
            except Exception as e:
                results.append({
                    "command": " ".join(cmd),
                    "returncode": -2,
                    "stdout": "",
                    "stderr": str(e),
                    "soft_failed": False,
                    "soft_reason": "",
                })
        
        return results

    # =========================================================================
    # Full Diagnostic
    # =========================================================================

    def run_full_diagnostic(
        self,
        include_commands: bool = True,
        include_hardware: bool = True,
        timeout_seconds: int = 120
    ) -> Dict:
        """Executa diagnóstico completo."""
        logger.info("Iniciando diagnóstico completo...")
        
        snapshot = self.environment_snapshot(include_hardware=include_hardware)
        module_checks = self.check_python_modules()
        command_checks = self.run_local_commands(timeout_seconds=timeout_seconds) if include_commands else []
        
        # Health status
        essentials_ok = all(item["ok"] for item in module_checks["essential"])
        commands_ok = all(
            item["returncode"] == 0 or item.get("soft_failed", False)
            for item in command_checks
        ) if command_checks else True
        
        if essentials_ok and commands_ok:
            status = "ok"
        elif essentials_ok:
            status = "partial"
        else:
            status = "critical"
        
        diagnostic = {
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
            }
        }
        
        # Salva relatório
        report_path = self._save_report(diagnostic, "full_diagnostic")
        diagnostic["report_path"] = str(report_path)
        
        logger.info(f"Diagnóstico concluído: status={status}, report={report_path}")
        return diagnostic

    # =========================================================================
    # Module Smoke Suite
    # =========================================================================

    def run_module_smoke_suite(self, timeout_seconds: int = 25) -> Dict[str, Any]:
        """Executa smoke tests dos módulos da ATENA."""
        modules_dir = self.root_path / "modules"
        if not modules_dir.exists():
            return {"status": "error", "error": "Módulos directory not found"}
        
        module_targets = sorted(
            p.stem for p in modules_dir.glob("*.py")
            if p.name != "__init__.py" and not p.name.startswith("test_")
        )
        
        results: List[Dict] = []
        failed_modules = []
        
        for module_name in module_targets:
            cmd = [
                sys.executable, "-c",
                f"import importlib; importlib.import_module('modules.{module_name}'); print('OK:{module_name}')"
            ]
            
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                    cwd=str(self.root_path),
                )
                
                missing_import = self._extract_missing_import_from_stderr(proc.stderr)
                if proc.returncode != 0 and missing_import:
                    if self._ensure_runtime_dependency(missing_import):
                        proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=timeout_seconds,
                            check=False,
                            cwd=str(self.root_path),
                        )
                
                ok = proc.returncode == 0
                results.append({
                    "type": "module_import",
                    "target": f"modules.{module_name}",
                    "ok": ok,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[:200],
                    "stderr": proc.stderr.strip()[:200],
                })
                if not ok:
                    failed_modules.append(module_name)
                    
            except subprocess.TimeoutExpired:
                results.append({
                    "type": "module_import",
                    "target": f"modules.{module_name}",
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"timeout>{timeout_seconds}s",
                })
                failed_modules.append(module_name)
        
        # Extra checks
        extra_checks = [
            {
                "name": "internet_connectivity",
                "cmd": [sys.executable, "-c",
                        "import urllib.request; urllib.request.urlopen('https://www.google.com', timeout=8); print('internet:ok')"],
            },
            {
                "name": "atena_launcher_import",
                "cmd": [sys.executable, "-c",
                        "import sys; sys.path.insert(0, 'core'); import atena_launcher; print('launcher:ok')"],
            },
        ]
        
        for check in extra_checks:
            try:
                proc = subprocess.run(
                    check["cmd"],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                    cwd=str(self.root_path),
                )
                results.append({
                    "type": "extra_check",
                    "target": check["name"],
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[:200],
                    "stderr": proc.stderr.strip()[:200],
                })
            except subprocess.TimeoutExpired:
                results.append({
                    "type": "extra_check",
                    "target": check["name"],
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"timeout>{timeout_seconds}s",
                })
        
        passed = sum(1 for r in results if r["ok"])
        total = len(results)
        failed = total - passed
        
        summary = {
            "status": "ok" if failed == 0 else "partial",
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "failed_modules": failed_modules[:10],
            "timestamp": datetime.now().isoformat(),
            "results": results[:50],
        }
        
        report_path = self._save_report(summary, "module_smoke_suite")
        summary["report_path"] = str(report_path)
        
        logger.info(f"Smoke suite concluído: {passed}/{total} passaram, report={report_path}")
        return summary

    # =========================================================================
    # Advanced Autopilot
    # =========================================================================

    def run_advanced_autopilot(
        self,
        objective: str = "Elevar confiabilidade do runtime da ATENA",
        include_commands: bool = True,
        timeout_seconds: int = 120,
        auto_correct: bool = True
    ) -> Dict[str, Any]:
        """
        Executa ciclo avançado orientado por objetivo com auto-correção.
        
        Args:
            objective: Objetivo do autopilot
            include_commands: Se deve executar comandos locais
            timeout_seconds: Timeout para comandos
            auto_correct: Se deve tentar corrigir problemas automaticamente
        
        Returns:
            Relatório completo com diagnóstico, plano de ação e resultados
        """
        logger.info(f"🚀 Iniciando Autopilot: {objective}")
        
        diagnostic = self.run_full_diagnostic(
            include_commands=include_commands,
            include_hardware=True,
            timeout_seconds=timeout_seconds
        )
        
        # Identifica problemas
        essential_missing = [
            item["name"] for item in diagnostic["modules"]["essential"]
            if not item.get("ok", False)
        ]
        advanced_missing = [
            item["name"] for item in diagnostic["modules"].get("advanced", [])
            if not item.get("ok", False)
        ]
        command_failures = [
            item for item in diagnostic.get("commands", [])
            if item.get("returncode", 1) != 0 and not item.get("soft_failed", False)
        ]
        
        # Auto-correção
        corrections = []
        if auto_correct:
            for module in essential_missing[:3]:
                logger.info(f"Tentando corrigir módulo faltante: {module}")
                if self.auto_install_module(module):
                    corrections.append(f"Instalado: {module}")
            
            # Re-verifica após correções
            if corrections:
                logger.info("Re-verificando diagnóstico após correções...")
                diagnostic = self.run_full_diagnostic(
                    include_commands=include_commands,
                    include_hardware=True,
                    timeout_seconds=timeout_seconds
                )
                essential_missing = [
                    item["name"] for item in diagnostic["modules"]["essential"]
                    if not item.get("ok", False)
                ]
        
        # Cálculo de risco e confiança
        risk_score = min(1.0,
            (len(essential_missing) * 0.30) +
            (len(command_failures) * 0.20) +
            (len(advanced_missing) * 0.05)
        )
        confidence = max(0.0, 1.0 - risk_score)
        
        # Plano de ação
        action_plan = []
        if essential_missing:
            action_plan.append({
                "priority": "P0",
                "title": "Restaurar módulos essenciais faltantes",
                "details": f"Instalar/validar: {', '.join(essential_missing)}",
                "commands": [f"pip install {m}" for m in essential_missing]
            })
        
        if command_failures:
            action_plan.append({
                "priority": "P0",
                "title": "Corrigir comandos locais com falha",
                "details": [f["command"][:100] for f in command_failures[:3]],
            })
        
        if advanced_missing and confidence > 0.7:
            action_plan.append({
                "priority": "P1",
                "title": "Instalar stack avançada (opcional)",
                "details": f"Para melhor performance: {', '.join(advanced_missing[:5])}",
            })
        
        if not action_plan:
            action_plan.append({
                "priority": "P1",
                "title": "Ambiente estável",
                "details": "Prosseguir para missões de evolução e benchmarks.",
            })
        
        # Hardware recommendations
        hardware_caps = self.detect_hardware_capabilities()
        hw_recommendations = []
        if not hardware_caps.has_gpu and "torch" not in essential_missing:
            hw_recommendations.append("GPU recomendada para modelos de ML e embeddings")
        if hardware_caps.ram_gb < 8:
            hw_recommendations.append(f"RAM limitada ({hardware_caps.ram_gb}GB) - pode afetar performance")
        if hardware_caps.cpu_cores < 4:
            hw_recommendations.append(f"Poucos cores de CPU ({hardware_caps.cpu_cores}) - reduz paralelismo")
        
        result = {
            "objective": objective,
            "status": diagnostic["status"],
            "risk_score": round(risk_score, 3),
            "confidence": round(confidence, 3),
            "missing_essential_modules": essential_missing,
            "missing_advanced_modules_count": len(advanced_missing),
            "failing_commands_count": len(command_failures),
            "corrections_applied": corrections,
            "hardware_recommendations": hw_recommendations,
            "action_plan": action_plan,
            "diagnostic_summary": diagnostic["summary"],
            "generated_at": datetime.now().isoformat(),
        }
        
        report_path = self._save_report(result, "autopilot")
        result["report_path"] = str(report_path)
        
        logger.info(f"Autopilot concluído: status={result['status']}, confidence={confidence:.1%}, report={report_path}")
        return result

    # =========================================================================
    # Utilities
    # =========================================================================

    def _save_report(self, data: Dict, prefix: str) -> Path:
        """Salva relatório em JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.reports_dir / f"{prefix}_{timestamp}.json"
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        return report_path

    @staticmethod
    def _extract_missing_import_from_stderr(stderr: str) -> Optional[str]:
        """Extrai nome do módulo faltante do stderr."""
        if not stderr:
            return None
        match = re.search(r"No module named '([^']+)'", stderr)
        return match.group(1) if match else None

    def _ensure_runtime_dependency(self, import_name: str) -> bool:
        """Garante dependência em tempo de execução."""
        package_name = self.RUNTIME_IMPORT_TO_PIP.get(import_name)
        if not package_name:
            return False
        return self.auto_install_module(package_name)

    def clear_cache(self):
        """Limpa cache de diagnóstico."""
        self._diagnostic_cache.clear()
        logger.info("Cache de diagnóstico limpo")


# =============================================================================
# CLI
# =============================================================================

def _main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="AtenaCodex v3.0 - Diagnóstico e Utilitários")
    parser.add_argument("--diagnostic", action="store_true", help="Executa diagnóstico completo")
    parser.add_argument("--autopilot", action="store_true", help="Executa autopilot avançado")
    parser.add_argument("--smoke", action="store_true", help="Executa smoke tests dos módulos")
    parser.add_argument("--install-essentials", action="store_true", help="Instala módulos essenciais")
    parser.add_argument("--hardware", action="store_true", help="Mostra informações de hardware")
    parser.add_argument("--health", action="store_true", help="Mostra saúde do sistema")
    parser.add_argument("--json", action="store_true", help="Saída em formato JSON")
    
    args = parser.parse_args()
    
    root = Path(__file__).parent.parent
    codex = AtenaCodex(root_path=root)
    
    if args.hardware:
        hw = codex.detect_hardware_capabilities()
        if args.json:
            print(json.dumps(asdict(hw), indent=2))
        else:
            print(f"GPU: {hw.gpu_name if hw.has_gpu else 'Nenhuma'} ({hw.gpu_memory_mb}MB)" if hw.has_gpu else "GPU: Nenhuma")
            print(f"CUDA: {hw.cuda_version if hw.has_cuda else 'Não disponível'}")
            print(f"CPU Cores: {hw.cpu_cores}")
            print(f"RAM: {hw.ram_gb}GB")
            print(f"Disco Livre: {hw.disk_free_gb}GB")
        return 0
    
    if args.health:
        health = codex.get_system_health()
        if args.json:
            print(json.dumps(asdict(health), indent=2))
        else:
            print(f"CPU: {health.cpu_percent}%")
            print(f"Memória: {health.memory_percent}%")
            print(f"Disco: {health.disk_percent}%")
            print(f"Uptime: {health.uptime_seconds // 3600}h")
            print(f"Load: {health.load_average}")
        return 0
    
    if args.install_essentials:
        result = codex.ensure_essential_modules(auto_install=True)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Essenciais OK: {'✅' if result['all_essential_ok'] else '❌'}")
            for mod, info in result["modules"].items():
                status = "✅" if info["ok"] else "❌"
                print(f"  {status} {mod}: {info['details'][:50]}")
        return 0
    
    if args.smoke:
        result = codex.run_module_smoke_suite()
        print(json.dumps(result, indent=2) if args.json else (
            f"\n📊 Smoke Suite: {result['passed']}/{result['total_checks']} passaram\n"
            f"Status: {result['status']}\n"
            f"Relatório: {result.get('report_path', 'N/A')}"
        ))
        return 0
    
    if args.autopilot:
        result = codex.run_advanced_autopilot(auto_correct=True)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\n🚀 Autopilot: {result['objective']}")
            print(f"Status: {result['status'].upper()}")
            print(f"Confiança: {result['confidence']:.1%}")
            print(f"Risco: {result['risk_score']:.1%}")
            if result["action_plan"]:
                print("\n📋 Plano de Ação:")
                for plan in result["action_plan"]:
                    print(f"  {plan['priority']}: {plan['title']}")
            if result["corrections_applied"]:
                print(f"\n✅ Correções aplicadas: {', '.join(result['corrections_applied'])}")
            print(f"\n📄 Relatório: {result['report_path']}")
        return 0
    
    # Default: diagnóstico completo
    result = codex.run_full_diagnostic()
    print(json.dumps(result, indent=2, default=str) if args.json else (
        f"\n🔍 Diagnóstico ATENA Codex\n"
        f"Status: {result['status']}\n"
        f"Módulos essenciais: {result['summary']['essential_modules_ok']}/{result['summary']['essential_modules_total']}\n"
        f"Comandos: {result['summary']['commands_passed']}/{result['summary']['commands_total']}\n"
        f"Timestamp: {result['timestamp']}"
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
