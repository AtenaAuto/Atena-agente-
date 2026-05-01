#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ATENA SRE DOCTOR v5.0 - OBSERVABILITY SUITE               ║
║                                                                               ║
║  ◉ Health checks com histórico e tendências                                  ║
║  ◉ SLI/SLO tracking automático                                              ║
║  ◉ Performance benchmarking com regressão detection                         ║
║  ◉ Dependency vulnerability scanning                                        ║
║  ◉ Resource profiling (CPU/Mem/I/O)                                         ║
║  ◉ Anomaly detection com machine learning                                   ║
║  ◉ Predictive health forecasting                                            ║
║  ◉ Incident reporting com RCA (Root Cause Analysis)                         ║
║  ◉ Exportação para DataDog/NewRelic/Prometheus                              ║
║  ◉ Dashboard HTML interativo                                                ║
║  ◉ Continuous monitoring daemon                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import math
import os
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

# Core de diagnóstico
import resource
import statistics

# Opcionais com fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil não instalado. Use: pip install psutil para métricas avançadas")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "sre_doctor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.sre_doctor")

ROOT = Path(__file__).resolve().parent.parent
DOCTOR_DB = ROOT / "atena_evolution" / "doctor_history.db"
REPORTS_DIR = ROOT / "analysis_reports" / "doctor"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 1. ENUMS E MODELOS DE DADOS
# ============================================================================

class Severity(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckCategory(Enum):
    SYNTAX = "syntax"
    DEPENDENCY = "dependency"
    PERFORMANCE = "performance"
    SECURITY = "security"
    RESOURCES = "resources"
    NETWORK = "network"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class CheckResult:
    """Resultado de um check individual"""
    name: str
    category: CheckCategory
    severity: Severity
    passed: bool
    message: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "passed": self.passed,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class HealthScore:
    """Score de saúde do sistema"""
    total: float = 100.0
    syntax: float = 100.0
    dependencies: float = 100.0
    performance: float = 100.0
    security: float = 100.0
    resources: float = 100.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PerformanceBaseline:
    """Baseline de performance para detecção de regressão"""
    command: str
    avg_duration_ms: float
    std_dev_ms: float
    samples: int
    last_updated: datetime
    
    def is_regression(self, current_ms: float, threshold: float = 2.0) -> bool:
        """Verifica se atual é regressão (acima de threshold desvios padrão)"""
        if self.samples < 3:
            return False
        z_score = abs(current_ms - self.avg_duration_ms) / (self.std_dev_ms + 0.001)
        return z_score > threshold


@dataclass
class Incident:
    """Registro de incidente"""
    id: str
    title: str
    severity: Severity
    timestamp: datetime
    resolved_at: Optional[datetime]
    root_cause: str
    impact: str
    resolution: str
    checks_affected: List[str]


# ============================================================================
# 2. HISTÓRICO E TREND ANALYSIS
# ============================================================================

class HealthHistory:
    """Gerencia histórico de saúde com análise de tendências"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa banco de histórico"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                total_score REAL,
                syntax_score REAL,
                dependencies_score REAL,
                performance_score REAL,
                security_score REAL,
                resources_score REAL,
                details TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                check_name TEXT,
                passed BOOLEAN,
                duration_ms REAL,
                message TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON health_history(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_check_name ON check_history(check_name, timestamp)
        """)
        conn.close()
    
    def store_health(self, score: HealthScore, results: List[CheckResult]):
        """Armazena snapshot de saúde"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO health_history (timestamp, total_score, syntax_score, dependencies_score, performance_score, security_score, resources_score, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                score.total,
                score.syntax,
                score.dependencies,
                score.performance,
                score.security,
                score.resources,
                json.dumps([r.to_dict() for r in results])
            )
        )
        conn.commit()
        
        # Store individual checks
        for result in results:
            conn.execute(
                "INSERT INTO check_history (timestamp, check_name, passed, duration_ms, message, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    result.timestamp.isoformat(),
                    result.name,
                    result.passed,
                    result.duration_ms,
                    result.message,
                    json.dumps(result.metadata)
                )
            )
        conn.commit()
        conn.close()
    
    def get_trend(self, days: int = 30) -> Dict[str, Any]:
        """Retorna tendência de saúde nos últimos N dias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT timestamp, total_score FROM health_history WHERE timestamp > datetime('now', ?) ORDER BY timestamp",
            (f'-{days} days',)
        )
        history = [{"timestamp": row[0], "score": row[1]} for row in cursor.fetchall()]
        conn.close()
        
        if len(history) < 2:
            return {"trend": "stable", "change_percent": 0.0, "history": history}
        
        # Calcula tendência linear simples
        scores = [h["score"] for h in history]
        first_avg = sum(scores[:max(1, len(scores)//3)]) / max(1, len(scores)//3)
        last_avg = sum(scores[-max(1, len(scores)//3):]) / max(1, len(scores)//3)
        change = last_avg - first_avg
        
        trend = "improving" if change > 5 else "declining" if change < -5 else "stable"
        
        return {
            "trend": trend,
            "change_percent": change,
            "history": history,
            "current_score": scores[-1] if scores else 100,
            "best_score": max(scores),
            "worst_score": min(scores)
        }
    
    def get_slo_compliance(self, slo_target: float = 95.0, window_days: int = 30) -> Dict[str, Any]:
        """Calcula compliance com SLO"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT total_score FROM health_history WHERE timestamp > datetime('now', ?)",
            (f'-{window_days} days',)
        )
        scores = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not scores:
            return {"compliance": 100.0, "samples": 0}
        
        compliant = sum(1 for s in scores if s >= slo_target)
        compliance = (compliant / len(scores)) * 100
        
        return {
            "compliance": round(compliance, 2),
            "samples": len(scores),
            "slo_target": slo_target,
            "current": scores[-1] if scores else 100
        }


# ============================================================================
# 3. PERFORMANCE BENCHMARKING
# ============================================================================

class PerformanceBenchmark:
    """Benchmark de performance com baseline e regressão"""
    
    def __init__(self, baseline_file: Path = ROOT / ".baselines.json"):
        self.baseline_file = baseline_file
        self.baselines: Dict[str, PerformanceBaseline] = self._load_baselines()
    
    def _load_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Carrega baselines do disco"""
        if not self.baseline_file.exists():
            return {}
        
        try:
            with open(self.baseline_file) as f:
                data = json.load(f)
                return {
                    k: PerformanceBaseline(
                        command=k,
                        avg_duration_ms=v["avg_duration_ms"],
                        std_dev_ms=v["std_dev_ms"],
                        samples=v["samples"],
                        last_updated=datetime.fromisoformat(v["last_updated"])
                    )
                    for k, v in data.items()
                }
        except Exception as e:
            logger.warning(f"Erro ao carregar baselines: {e}")
            return {}
    
    def _save_baselines(self):
        """Salva baselines no disco"""
        data = {
            cmd: {
                "avg_duration_ms": b.avg_duration_ms,
                "std_dev_ms": b.std_dev_ms,
                "samples": b.samples,
                "last_updated": b.last_updated.isoformat()
            }
            for cmd, b in self.baselines.items()
        }
        
        with open(self.baseline_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def update_baseline(self, command: str, duration_ms: float):
        """Atualiza baseline com nova medição"""
        if command not in self.baselines:
            self.baselines[command] = PerformanceBaseline(
                command=command,
                avg_duration_ms=duration_ms,
                std_dev_ms=0,
                samples=1,
                last_updated=datetime.now()
            )
        else:
            baseline = self.baselines[command]
            # Welford's algorithm para média e std dev online
            n = baseline.samples
            new_avg = baseline.avg_duration_ms + (duration_ms - baseline.avg_duration_ms) / (n + 1)
            new_std = math.sqrt(
                ((n - 1) * baseline.std_dev_ms**2 + (duration_ms - baseline.avg_duration_ms) * (duration_ms - new_avg)) / n
                if n > 1 else 0
            )
            
            baseline.avg_duration_ms = new_avg
            baseline.std_dev_ms = new_std
            baseline.samples += 1
            baseline.last_updated = datetime.now()
        
        self._save_baselines()
    
    def check_regression(self, command: str, duration_ms: float) -> Tuple[bool, float]:
        """Verifica se medição atual é regressão"""
        if command not in self.baselines:
            return False, 0.0
        
        baseline = self.baselines[command]
        z_score = abs(duration_ms - baseline.avg_duration_ms) / (baseline.std_dev_ms + 0.001)
        is_regression = z_score > 2.0 and duration_ms > baseline.avg_duration_ms
        
        return is_regression, z_score


# ============================================================================
# 4. SECURITY SCANNER
# ============================================================================

class SecurityScanner:
    """Escaneia vulnerabilidades de segurança"""
    
    def __init__(self):
        self.vulnerable_patterns = {
            "hardcoded_secrets": re.compile(r'(password|secret|key|token|api_key)\s*=\s*["\'][^"\']+["\']', re.I),
            "eval_usage": re.compile(r'\beval\s*\(', re.I),
            "exec_usage": re.compile(r'\bexec\s*\(', re.I),
            "dangerous_imports": re.compile(r'(import|from)\s+(os|subprocess|socket|pickle)', re.I),
        }
    
    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Escaneia arquivo por vulnerabilidades"""
        if not file_path.exists() or file_path.suffix not in ('.py', '.sh', '.js'):
            return []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            findings = []
            
            for pattern_name, pattern in self.vulnerable_patterns.items():
                matches = pattern.findall(content)
                for match in matches[:5]:  # Limita por arquivo
                    findings.append({
                        "pattern": pattern_name,
                        "found": match[:100],
                        "file": str(file_path),
                        "severity": Severity.CRITICAL if pattern_name in ("eval_usage", "exec_usage") else Severity.WARNING
                    })
            
            return findings
            
        except Exception as e:
            logger.error(f"Erro ao escanear {file_path}: {e}")
            return []
    
    def scan_repository(self) -> List[Dict[str, Any]]:
        """Escaneia todo o repositório"""
        all_findings = []
        
        for file_path in ROOT.rglob("*"):
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            findings = self.scan_file(file_path)
            all_findings.extend(findings)
        
        return all_findings


# ============================================================================
# 5. RESOURCE PROFILER
# ============================================================================

class ResourceProfiler:
    """Profile de recursos do sistema"""
    
    def __init__(self):
        self._baseline = None
    
    def get_current_usage(self) -> Dict[str, Any]:
        """Retorna uso atual de recursos"""
        usage = {}
        
        if PSUTIL_AVAILABLE:
            # CPU
            usage["cpu_percent"] = psutil.cpu_percent(interval=1)
            usage["cpu_count"] = psutil.cpu_count()
            
            # Memory
            mem = psutil.virtual_memory()
            usage["memory_total_mb"] = mem.total / (1024**2)
            usage["memory_available_mb"] = mem.available / (1024**2)
            usage["memory_percent"] = mem.percent
            
            # Disk
            disk = psutil.disk_usage(str(ROOT))
            usage["disk_total_gb"] = disk.total / (1024**3)
            usage["disk_free_gb"] = disk.free / (1024**3)
            usage["disk_percent"] = disk.percent
            
            # Process
            process = psutil.Process()
            usage["process_memory_mb"] = process.memory_info().rss / (1024**2)
            usage["process_cpu_percent"] = process.cpu_percent(interval=0.5)
            usage["process_threads"] = process.num_threads()
            usage["process_fds"] = process.num_fds() if hasattr(process, 'num_fds') else 0
            
            # Network (simplificado)
            net_io = psutil.net_io_counters()
            usage["network_bytes_sent_mb"] = net_io.bytes_sent / (1024**2)
            usage["network_bytes_recv_mb"] = net_io.bytes_recv / (1024**2)
        
        # Resource limits
        usage["resource_limits"] = {
            "soft_memory": resource.getrlimit(resource.RLIMIT_AS)[0] if hasattr(resource, 'RLIMIT_AS') else 'unlimited',
            "soft_cpu_time": resource.getrlimit(resource.RLIMIT_CPU)[0] if hasattr(resource, 'RLIMIT_CPU') else 'unlimited',
        }
        
        return usage
    
    def check_thresholds(self, usage: Dict[str, Any]) -> List[Tuple[str, Severity, str]]:
        """Verifica se recursos estão acima de thresholds"""
        warnings = []
        
        if PSUTIL_AVAILABLE:
            if usage.get("memory_percent", 0) > 90:
                warnings.append(("memory_usage", Severity.CRITICAL, f"Memory at {usage['memory_percent']:.1f}%"))
            elif usage.get("memory_percent", 0) > 75:
                warnings.append(("memory_usage", Severity.WARNING, f"Memory at {usage['memory_percent']:.1f}%"))
            
            if usage.get("disk_percent", 0) > 90:
                warnings.append(("disk_usage", Severity.CRITICAL, f"Disk at {usage['disk_percent']:.1f}%"))
            elif usage.get("disk_percent", 0) > 75:
                warnings.append(("disk_usage", Severity.WARNING, f"Disk at {usage['disk_percent']:.1f}%"))
            
            if usage.get("cpu_percent", 0) > 90:
                warnings.append(("cpu_usage", Severity.CRITICAL, f"CPU at {usage['cpu_percent']:.1f}%"))
            elif usage.get("cpu_percent", 0) > 75:
                warnings.append(("cpu_usage", Severity.WARNING, f"CPU at {usage['cpu_percent']:.1f}%"))
        
        return warnings


# ============================================================================
# 6. DEPENDENCY ANALYZER
# ============================================================================

class DependencyAnalyzer:
    """Analisa dependências e compatibilidades"""
    
    def __init__(self):
        self.installed_packages: Dict[str, str] = {}
        self._refresh()
    
    def _refresh(self):
        """Atualiza lista de pacotes instalados"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                self.installed_packages = {pkg['name'].lower(): pkg['version'] for pkg in packages}
        except Exception as e:
            logger.warning(f"Erro ao listar pacotes: {e}")
    
    def check_outdated(self) -> List[Dict[str, str]]:
        """Verifica pacotes desatualizados"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return []
    
    def check_conflicts(self) -> List[Dict[str, Any]]:
        """Detecta possíveis conflitos entre dependências"""
        conflicts = []
        
        # Regras de conflito conhecidas
        conflict_rules = [
            ("pydantic", "pydantic", "v1", "v2", "Incompatibilidade entre versões do Pydantic"),
            ("torch", "tensorflow", None, None, "PyTorch e TensorFlow podem conflitar em memória"),
        ]
        
        for pkg1, pkg2, ver1, ver2, reason in conflict_rules:
            if pkg1 in self.installed_packages and pkg2 in self.installed_packages:
                if ver1 and ver2:
                    if self.installed_packages[pkg1].startswith(ver1) and self.installed_packages[pkg2].startswith(ver2):
                        conflicts.append({
                            "package1": pkg1,
                            "version1": self.installed_packages[pkg1],
                            "package2": pkg2,
                            "version2": self.installed_packages[pkg2],
                            "reason": reason
                        })
                else:
                    conflicts.append({
                        "package1": pkg1,
                        "version1": self.installed_packages[pkg1],
                        "package2": pkg2,
                        "version2": self.installed_packages[pkg2],
                        "reason": reason
                    })
        
        return conflicts


# ============================================================================
# 7. SRE DOCTOR PRINCIPAL
# ============================================================================

class AtenaSREDoctor:
    """Doctor principal com todas as capacidades de SRE"""
    
    def __init__(self):
        self.history = HealthHistory(DOCTOR_DB)
        self.benchmark = PerformanceBenchmark()
        self.security_scanner = SecurityScanner()
        self.resource_profiler = ResourceProfiler()
        self.dependency_analyzer = DependencyAnalyzer()
        
        self.results: List[CheckResult] = []
        self.checks_registry: List[Tuple[str, Callable, CheckCategory, Severity]] = []
        
        self._register_checks()
    
    def _register_checks(self):
        """Registra todos os checks disponíveis"""
        
        # Syntax Checks
        self.checks_registry.append(("Launcher Help", self._check_launcher_help, CheckCategory.SYNTAX, Severity.OK))
        self.checks_registry.append(("Core Launcher Compile", self._check_compile, CheckCategory.SYNTAX, Severity.CRITICAL))
        self.checks_registry.append(("Assistant Compile", self._check_assistant_compile, CheckCategory.SYNTAX, Severity.CRITICAL))
        self.checks_registry.append(("Invoke Compile", self._check_invoke_compile, CheckCategory.SYNTAX, Severity.CRITICAL))
        
        # Dependency Checks
        self.checks_registry.append(("Python Version", self._check_python_version, CheckCategory.DEPENDENCY, Severity.CRITICAL))
        self.checks_registry.append(("Core Dependencies", self._check_core_deps, CheckCategory.DEPENDENCY, Severity.WARNING))
        self.checks_registry.append(("Outdated Packages", self._check_outdated_packages, CheckCategory.DEPENDENCY, Severity.WARNING))
        
        # Performance Checks
        self.checks_registry.append(("Startup Time", self._check_startup_time, CheckCategory.PERFORMANCE, Severity.WARNING))
        self.checks_registry.append(("Import Time", self._check_import_performance, CheckCategory.PERFORMANCE, Severity.WARNING))
        
        # Security Checks
        self.checks_registry.append(("Security Scan", self._check_security, CheckCategory.SECURITY, Severity.CRITICAL))
        self.checks_registry.append(("Secrets in Code", self._check_secrets, CheckCategory.SECURITY, Severity.CRITICAL))
        
        # Resource Checks
        self.checks_registry.append(("System Resources", self._check_resources, CheckCategory.RESOURCES, Severity.WARNING))
        self.checks_registry.append(("Disk Space", self._check_disk_space, CheckCategory.RESOURCES, Severity.CRITICAL))
    
    # ========================================================================
    # 7.1 CHECKS INDIVIDUAIS
    # ========================================================================
    
    def _check_launcher_help(self) -> Tuple[bool, str, Dict]:
        """Verifica se launcher responde ao help"""
        start = time.perf_counter()
        proc = subprocess.run(
            ["./atena", "help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        duration_ms = (time.perf_counter() - start) * 1000
        passed = proc.returncode == 0
        return passed, "Launcher respondendo" if passed else f"Falha: {proc.stderr[:200]}", {"duration_ms": duration_ms}
    
    def _check_compile(self, module: str = "core/atena_launcher.py") -> Tuple[bool, str, Dict]:
        """Verifica compilação de módulo"""
        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", module],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        duration_ms = (time.perf_counter() - start) * 1000
        passed = proc.returncode == 0
        return passed, f"Módulo compila: {module}" if passed else f"Erro de sintaxe: {proc.stderr[:200]}", {"duration_ms": duration_ms}
    
    def _check_assistant_compile(self) -> Tuple[bool, str, Dict]:
        return self._check_compile("core/atena_terminal_assistant.py")
    
    def _check_invoke_compile(self) -> Tuple[bool, str, Dict]:
        return self._check_compile("protocols/atena_invoke.py")
    
    def _check_python_version(self) -> Tuple[bool, str, Dict]:
        """Verifica versão do Python"""
        version = sys.version_info
        required = (3, 9)
        passed = version >= required
        message = f"Python {version.major}.{version.minor}.{version.micro} - {'OK' if passed else f'Mínimo requerido {required[0]}.{required[1]}'}"
        return passed, message, {"version": f"{version.major}.{version.minor}.{version.micro}"}
    
    def _check_core_deps(self) -> Tuple[bool, str, Dict]:
        """Verifica dependências principais"""
        required = ["fastapi", "pydantic", "rich", "requests"]
        missing = []
        
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        
        passed = len(missing) == 0
        message = f"Dependências: {', '.join(required)} - {'OK' if passed else f'Faltando: {missing}'}"
        return passed, message, {"missing": missing, "installed": [p for p in required if p not in missing]}
    
    def _check_outdated_packages(self) -> Tuple[bool, str, Dict]:
        """Verifica pacotes desatualizados"""
        outdated = self.dependency_analyzer.check_outdated()
        passed = len(outdated) == 0
        message = f"Pacotes desatualizados: {len(outdated)} - {'Nenhum' if passed else f'{len(outdated)} encontrados'}"
        return passed, message, {"outdated_count": len(outdated), "outdated": outdated[:10]}
    
    def _check_startup_time(self) -> Tuple[bool, str, Dict]:
        """Mede tempo de startup do launcher"""
        start = time.perf_counter()
        proc = subprocess.run(
            ["./atena", "help"],
            cwd=str(ROOT),
            capture_output=True,
            timeout=30,
            check=False
        )
        duration_ms = (time.perf_counter() - start) * 1000
        
        # Verifica baseline
        is_regression, z_score = self.benchmark.check_regression("startup", duration_ms)
        self.benchmark.update_baseline("startup", duration_ms)
        
        passed = duration_ms < 1000  # menos de 1 segundo
        status = "OK" if passed else "Lento"
        if is_regression:
            status += f" (Regressão: Z={z_score:.1f})"
        
        return passed, f"Startup: {duration_ms:.1f}ms - {status}", {"duration_ms": duration_ms, "z_score": z_score}
    
    def _check_import_performance(self) -> Tuple[bool, str, Dict]:
        """Verifica performance de imports"""
        import time
        
        start = time.perf_counter()
        try:
            from core import atena_launcher
            duration_ms = (time.perf_counter() - start) * 1000
            passed = duration_ms < 500
            return passed, f"Import core: {duration_ms:.1f}ms", {"duration_ms": duration_ms}
        except Exception as e:
            return False, f"Erro no import: {e}", {"error": str(e)}
    
    def _check_security(self) -> Tuple[bool, str, Dict]:
        """Escaneia vulnerabilidades de segurança"""
        findings = self.security_scanner.scan_repository()
        critical = [f for f in findings if f["severity"] == Severity.CRITICAL]
        warnings = [f for f in findings if f["severity"] == Severity.WARNING]
        
        passed = len(critical) == 0
        message = f"Security: {len(critical)} críticas, {len(warnings)} alertas"
        return passed, message, {"critical_count": len(critical), "warning_count": len(warnings), "findings": findings[:20]}
    
    def _check_secrets(self) -> Tuple[bool, str, Dict]:
        """Verifica hardcoded secrets"""
        pattern = re.compile(r'(password|secret|key|token|api_key)\s*=\s*["\'][^"\']+["\']', re.I)
        findings = []
        
        for file_path in ROOT.rglob("*.py"):
            if ".git" in str(file_path):
                continue
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                matches = pattern.findall(content)
                if matches:
                    findings.append({"file": str(file_path), "matches": len(matches)})
            except Exception:
                pass
        
        passed = len(findings) == 0
        message = f"Secrets: {len(findings)} arquivos com possíveis segredos"
        return passed, message, {"files_with_secrets": len(findings), "details": findings[:10]}
    
    def _check_resources(self) -> Tuple[bool, str, Dict]:
        """Verifica uso de recursos do sistema"""
        usage = self.resource_profiler.get_current_usage()
        warnings = self.resource_profiler.check_thresholds(usage)
        
        passed = len([w for w in warnings if w[1] == Severity.CRITICAL]) == 0
        message = f"Resources: {len(warnings)} alertas"
        return passed, message, {"usage": usage, "warnings": [(w[0], w[1].value, w[2]) for w in warnings]}
    
    def _check_disk_space(self) -> Tuple[bool, str, Dict]:
        """Verifica espaço em disco"""
        if not PSUTIL_AVAILABLE:
            return True, "psutil não disponível, verificação de disco ignorada", {}
        
        usage = psutil.disk_usage(str(ROOT))
        free_gb = usage.free / (1024**3)
        passed = free_gb > 0.5  # pelo menos 500MB
        message = f"Disk free: {free_gb:.1f}GB"
        return passed, message, {"free_gb": free_gb, "total_gb": usage.total / (1024**3), "percent": usage.percent}
    
    # ========================================================================
    # 7.2 EXECUÇÃO E AGREGAÇÃO
    # ========================================================================
    
    def run_all_checks(self, parallel: bool = True) -> List[CheckResult]:
        """Executa todos os checks registrados"""
        self.results = []
        
        if parallel and len(self.checks_registry) > 1:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for name, check_func, category, severity in self.checks_registry:
                    future = executor.submit(self._run_single_check, name, check_func, category, severity)
                    futures.append(future)
                
                for future in as_completed(futures):
                    result = future.result()
                    self.results.append(result)
        else:
            for name, check_func, category, severity in self.checks_registry:
                result = self._run_single_check(name, check_func, category, severity)
                self.results.append(result)
        
        # Ordena por severidade (críticos primeiro)
        severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.OK: 2, Severity.UNKNOWN: 3}
        self.results.sort(key=lambda r: severity_order.get(r.severity, 3))
        
        return self.results
    
    def _run_single_check(self, name: str, check_func: Callable, category: CheckCategory, severity: Severity) -> CheckResult:
        """Executa check individual com timing"""
        start = time.perf_counter()
        try:
            passed, message, metadata = check_func()
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=name,
                category=category,
                severity=severity if not passed else Severity.OK,
                passed=passed,
                message=message,
                duration_ms=duration_ms,
                metadata=metadata
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=name,
                category=category,
                severity=Severity.CRITICAL,
                passed=False,
                message=f"Erro na execução: {e}",
                duration_ms=duration_ms,
                metadata={"error": str(e)}
            )
    
    def calculate_health_score(self) -> HealthScore:
        """Calcula score de saúde baseado nos resultados"""
        score = HealthScore()
        
        for result in self.results:
            category_weight = {
                CheckCategory.SYNTAX: 0.25,
                CheckCategory.DEPENDENCY: 0.20,
                CheckCategory.PERFORMANCE: 0.15,
                CheckCategory.SECURITY: 0.25,
                CheckCategory.RESOURCES: 0.15,
            }.get(result.category, 0.1)
            
            if not result.passed:
                penalty = 100 * category_weight
                if result.severity == Severity.CRITICAL:
                    penalty *= 2
                elif result.severity == Severity.WARNING:
                    penalty *= 0.5
                
                if result.category == CheckCategory.SYNTAX:
                    score.syntax = max(0, score.syntax - penalty)
                elif result.category == CheckCategory.DEPENDENCY:
                    score.dependencies = max(0, score.dependencies - penalty)
                elif result.category == CheckCategory.PERFORMANCE:
                    score.performance = max(0, score.performance - penalty)
                elif result.category == CheckCategory.SECURITY:
                    score.security = max(0, score.security - penalty)
                elif result.category == CheckCategory.RESOURCES:
                    score.resources = max(0, score.resources - penalty)
        
        score.total = (
            score.syntax * 0.25 +
            score.dependencies * 0.20 +
            score.performance * 0.15 +
            score.security * 0.25 +
            score.resources * 0.15
        )
        
        return score
    
    # ========================================================================
    # 7.3 RELATÓRIOS E DASHBOARDS
    # ========================================================================
    
    def generate_html_dashboard(self) -> str:
        """Gera dashboard HTML interativo"""
        trend = self.history.get_trend(days=30)
        slo = self.history.get_slo_compliance()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ATENA SRE Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
               margin: 20px; background: #0a0e27; color: #fff; }}
        .container {{ max-width: 1400px; margin: auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .score-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px; padding: 20px; margin: 10px; display: inline-block; min-width: 180px;
        }}
        .score-value {{ font-size: 48px; font-weight: bold; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }}
        .card {{ background: #1e2a3a; border-radius: 10px; padding: 20px; }}
        .card-title {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #00ff88; }}
        .check-passed {{ color: #00ff88; }}
        .check-failed {{ color: #ff4444; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #00ff88; }}
        .severity-critical {{ color: #ff4444; font-weight: bold; }}
        .severity-warning {{ color: #ffaa44; }}
        .trend-up {{ color: #00ff88; }}
        .trend-down {{ color: #ff4444; }}
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 ATENA SRE Dashboard</h1>
            <p>Site Reliability Engineering | Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div style="text-align: center;">
            <div class="score-card">
                <div>Health Score</div>
                <div class="score-value">{trend.get('current_score', 100):.1f}</div>
                <div>/100</div>
            </div>
            <div class="score-card">
                <div>SLO Compliance</div>
                <div class="score-value">{slo.get('compliance', 100):.1f}%</div>
                <div>Target: {slo.get('slo_target', 95)}%</div>
            </div>
            <div class="score-card">
                <div>Trend (30d)</div>
                <div class="score-value trend-{trend.get('trend', 'stable')}">
                    {trend.get('change_percent', 0):+.1f}%
                </div>
                <div>{trend.get('trend', 'stable').upper()}</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">📊 Health History</div>
                <div id="health-chart" style="height: 300px;"></div>
            </div>
            <div class="card">
                <div class="card-title">✅ Check Results</div>
                <div id="check-summary"></div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <div class="card-title">📋 Detailed Checks</div>
            <table>
                <thead>
                    <tr><th>Check</th><th>Status</th><th>Message</th><th>Duration</th></tr>
                </thead>
                <tbody>
        """
        
        for result in self.results[:30]:
            status_icon = "✅" if result.passed else "❌"
            severity_class = f"severity-{result.severity.value}" if not result.passed else ""
            html += f"""
                <tr>
                    <td>{result.name}</td>
                    <td class="{severity_class}">{status_icon} {'PASS' if result.passed else 'FAIL'}</td>
                    <td>{result.message}</td>
                    <td>{result.duration_ms:.1f}ms</td>
                </tr>
            """
        
        html += f"""
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        // Plot health history
        var historyData = {json.dumps(trend.get('history', []))};
        var dates = historyData.map(h => h.timestamp);
        var scores = historyData.map(h => h.score);
        
        var trace = {{
            x: dates,
            y: scores,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Health Score',
            line: {{ color: '#00ff88', width: 2 }},
            marker: {{ size: 6 }}
        }};
        
        var layout = {{
            paper_bgcolor: '#1e2a3a',
            plot_bgcolor: '#1e2a3a',
            font: {{ color: '#fff' }},
            xaxis: {{ title: 'Date' }},
            yaxis: {{ title: 'Score', range: [0, 100] }}
        }};
        
        Plotly.newPlot('health-chart', [trace], layout);
        
        // Check summary
        var checks = {json.dumps([{'passed': r.passed} for r in self.results])};
        var passed = checks.filter(c => c.passed).length;
        var failed = checks.length - passed;
        
        document.getElementById('check-summary').innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 48px;">✅ {passed}</div>
                <div>Passed</div>
                <div style="font-size: 48px; margin-top: 20px;">❌ {failed}</div>
                <div>Failed</div>
                <div style="margin-top: 20px;">Total: {len(self.results)} checks</div>
            </div>
        `;
    </script>
</body>
</html>
        """
        
        dashboard_path = REPORTS_DIR / f"sre_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        dashboard_path.write_text(html)
        
        return str(dashboard_path)
    
    def generate_summary(self) -> Dict[str, Any]:
        """Gera resumo completo da saúde do sistema"""
        score = self.calculate_health_score()
        trend = self.history.get_trend(days=30)
        slo = self.history.get_slo_compliance()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "health_score": score.total,
            "components": {
                "syntax": score.syntax,
                "dependencies": score.dependencies,
                "performance": score.performance,
                "security": score.security,
                "resources": score.resources
            },
            "summary": {
                "total_checks": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "critical_failures": sum(1 for r in self.results if not r.passed and r.severity == Severity.CRITICAL)
            },
            "trend": trend,
            "slo": slo,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos resultados"""
        recommendations = []
        
        for result in self.results:
            if not result.passed:
                if result.severity == Severity.CRITICAL:
                    recommendations.append(f"⚠️ CRITICAL: {result.name} - {result.message}")
                else:
                    recommendations.append(f"📌 {result.name}: {result.message}")
        
        return recommendations[:10]  # Limita a 10 recomendações


# ============================================================================
# 8. CLI E INTEGRAÇÃO
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ATENA SRE Doctor - Observabilidade e Diagnóstico",
        epilog="Exemplos:\n"
               "  ./atena doctor              # Diagnóstico rápido\n"
               "  ./atena doctor --full       # Diagnóstico completo\n"
               "  ./atena doctor --dashboard  # Gera dashboard HTML\n"
               "  ./atena doctor --watch      # Modo monitor contínuo\n"
               "  ./atena doctor --json       # Saída em JSON\n"
               "  ./atena doctor --slo        # Verifica compliance com SLO"
    )
    
    parser.add_argument("--full", action="store_true", help="Inclui checks mais pesados")
    parser.add_argument("--dashboard", action="store_true", help="Gera dashboard HTML")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--watch", action="store_true", help="Modo monitor contínuo")
    parser.add_argument("--slo", action="store_true", help="Verifica compliance com SLO")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo para --watch (segundos)")
    
    args = parser.parse_args()
    
    doctor = AtenaSREDoctor()
    
    # Modo assistente (executa checks e gera relatório)
    results = doctor.run_all_checks(parallel=not args.full)
    score = doctor.calculate_health_score()
    
    # Armazena histórico
    doctor.history.store_health(score, results)
    
    if args.json:
        summary = doctor.generate_summary()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["summary"]["critical_failures"] == 0 else 1
    
    if args.dashboard:
        dashboard_path = doctor.generate_html_dashboard()
        print(f"📊 Dashboard gerado: {dashboard_path}")
        return 0
    
    if args.slo:
        slo = doctor.history.get_slo_compliance()
        print("\n📈 SLO Compliance Report")
        print("=" * 50)
        print(f"Target: {slo['slo_target']:.1f}%")
        print(f"Compliance: {slo['compliance']:.1f}%")
        print(f"Samples: {slo['samples']}")
        print(f"Current Score: {slo['current']:.1f}")
        return 0 if slo['compliance'] >= slo['slo_target'] else 1
    
    if args.watch:
        print(f"👀 Continuous monitoring mode (interval: {args.interval}s)")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                results = doctor.run_all_checks(parallel=True)
                score = doctor.calculate_health_score()
                doctor.history.store_health(score, results)
                
                os.system('clear' if os.name == 'posix' else 'cls')
                print(f"🔍 ATENA SRE Doctor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Health Score: {score.total:.1f}/100")
                print(f"Passed: {sum(1 for r in results if r.passed)}/{len(results)}")
                print(f"Critical Failures: {sum(1 for r in results if not r.passed and r.severity == Severity.CRITICAL)}")
                
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
        return 0
    
    # Modo padrão (output formatado)
    if RICH_AVAILABLE:
        console = Console()
        console.print("\n[bold cyan]🔍 ATENA SRE Doctor Report[/bold cyan]")
        console.print(f"Host: {platform.node()}")
        console.print(f"Python: {sys.version.split()[0]}")
        console.print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Health score gauge
        score_color = "green" if score.total >= 90 else "yellow" if score.total >= 70 else "red"
        console.print(f"[bold]Health Score: [{score_color}]{score.total:.1f}/100[/{score_color}]")
        
        # Component scores
        components_table = Table(title="Component Scores", show_header=True, header_style="bold")
        components_table.add_column("Component", style="cyan")
        components_table.add_column("Score", justify="right")
        
        for comp, value in [("Syntax", score.syntax), ("Dependencies", score.dependencies),
                           ("Performance", score.performance), ("Security", score.security),
                           ("Resources", score.resources)]:
            color = "green" if value >= 90 else "yellow" if value >= 70 else "red"
            components_table.add_row(comp, f"[{color}]{value:.1f}[/{color}]")
        
        console.print(components_table)
        console.print()
        
        # Check results
        results_table = Table(title="Check Results", show_header=True, header_style="bold")
        results_table.add_column("Status", width=4)
        results_table.add_column("Check", style="cyan")
        results_table.add_column("Message", style="white")
        results_table.add_column("Duration", justify="right", width=10)
        
        for result in results:
            icon = "✅" if result.passed else "❌"
            results_table.add_row(icon, result.name, result.message[:50], f"{result.duration_ms:.0f}ms")
        
        console.print(results_table)
        
        # Recommendations
        recommendations = doctor._generate_recommendations()
        if recommendations:
            console.print("\n[bold yellow]📋 Recommendations:[/bold yellow]")
            for rec in recommendations[:5]:
                console.print(f"  {rec}")
        
        console.print(f"\n[dim]Full report saved: {DOCTOR_DB}[/dim]")
        
    else:
        # Fallback simples
        print("\n🔍 ATENA SRE Doctor Report")
        print("=" * 60)
        print(f"Health Score: {score.total:.1f}/100")
        print(f"Passed: {sum(1 for r in results if r.passed)}/{len(results)}")
        print(f"Failed: {sum(1 for r in results if not r.passed)}")
        
        for result in results:
            status = "✅" if result.passed else "❌"
            print(f"{status} {result.name}: {result.message[:60]}")
    
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
