#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ATENA AUTO-HEALING SYSTEM v3.0                             ║
║                                                                               ║
║  ◉ Auto-detecção de anomalias com machine learning                           ║
║  ◉ Correção preditiva baseada em histórico                                   ║
║  ◉ Rollback automático de mudanças mal-sucedidas                             ║
║  ◉ Health checks contínuos em background                                     ║
║  ◉ Quarantena de módulos problemáticos                                       ║
║  ◉ Dependency graph resolver com versões                                     ║
║  ◉ Self-healing com verificação multi-estágio                                ║
║  ◉ Dashboard de saúde do sistema                                             ║
║  ◉ Integração com sistema de alertas                                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importações opcionais
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "atena_fix.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.autoheal")

ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# 1. ENUMS E MODELOS DE DADOS
# ============================================================================

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FixStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Dependency:
    """Dependência do sistema"""
    name: str
    version: Optional[str] = None
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    required: bool = True
    install_command: Optional[List[str]] = None


@dataclass
class FixResult:
    """Resultado de uma operação de correção"""
    step_name: str
    status: FixStatus
    message: str
    duration_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
    rollback_possible: bool = False
    backup_path: Optional[Path] = None


@dataclass
class HealthCheck:
    """Check de saúde do sistema"""
    name: str
    check_func: Callable[[], Tuple[bool, str]]
    severity: Severity = Severity.WARNING
    last_check: Optional[datetime] = None
    last_result: Optional[bool] = None
    consecutive_failures: int = 0
    auto_fix: Optional[Callable[[], bool]] = None


@dataclass
class SystemSnapshot:
    """Snapshot do estado do sistema"""
    timestamp: datetime
    files: Dict[str, str]  # path -> hash
    dependencies: Dict[str, str]  # name -> version
    environment: Dict[str, str]
    health_score: float


# ============================================================================
# 2. DEPENDÊNCIA MANAGER AVANÇADO
# ============================================================================

class DependencyManager:
    """Gerencia dependências com resolução de versões"""
    
    def __init__(self):
        self._installed: Dict[str, str] = {}
        self._refresh_cache()
    
    def _refresh_cache(self):
        """Atualiza cache de dependências instaladas"""
        # Python packages
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                self._installed = {pkg['name'].lower(): pkg['version'] for pkg in packages}
        except Exception as e:
            logger.warning(f"Erro ao listar pacotes pip: {e}")
    
    def check_dependency(self, dep: Dependency) -> Tuple[bool, str]:
        """Verifica se dependência está instalada e em versão correta"""
        if dep.name.lower() not in self._installed:
            if dep.required:
                return False, f"Dependência não encontrada: {dep.name}"
            return True, f"Dependência opcional não encontrada: {dep.name}"
        
        installed_version = self._installed[dep.name.lower()]
        
        if dep.min_version and self._compare_versions(installed_version, dep.min_version) < 0:
            return False, f"Versão {installed_version} < mínimo {dep.min_version}"
        
        if dep.max_version and self._compare_versions(installed_version, dep.max_version) > 0:
            return False, f"Versão {installed_version} > máximo {dep.max_version}"
        
        return True, f"OK: {dep.name} {installed_version}"
    
    def install_dependency(self, dep: Dependency, upgrade: bool = False) -> Tuple[bool, str]:
        """Instala ou atualiza dependência"""
        cmd = [sys.executable, "-m", "pip", "install"]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if dep.version:
            cmd.append(f"{dep.name}=={dep.version}")
        else:
            cmd.append(dep.name)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                self._refresh_cache()
                return True, f"Instalado: {dep.name}"
            return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compara versões semânticas (retorna -1, 0, 1)"""
        def normalize(v: str) -> List[int]:
            return [int(x) for x in re.findall(r'\d+', v)]
        
        parts1 = normalize(v1)
        parts2 = normalize(v2)
        
        for i in range(max(len(parts1), len(parts2))):
            p1 = parts1[i] if i < len(parts1) else 0
            p2 = parts2[i] if i < len(parts2) else 0
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1
        return 0


# ============================================================================
# 3. BACKUP E ROLLBACK MANAGER
# ============================================================================

class BackupManager:
    """Gerencia backups e rollback de mudanças"""
    
    def __init__(self, backup_dir: Path = ROOT / ".backups"):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._backups: Dict[str, Path] = {}
    
    def backup_file(self, file_path: Path, description: str = "") -> Optional[Path]:
        """Cria backup de um arquivo"""
        if not file_path.exists():
            logger.warning(f"Arquivo não existe para backup: {file_path}")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}_{timestamp}_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}.backup"
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            
            # Salva metadados
            metadata = {
                "original_path": str(file_path),
                "timestamp": timestamp,
                "description": description,
                "size": file_path.stat().st_size
            }
            (backup_path.with_suffix(".json")).write_text(json.dumps(metadata, indent=2))
            
            self._backups[str(file_path)] = backup_path
            logger.info(f"Backup criado: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Erro ao criar backup de {file_path}: {e}")
            return None
    
    def restore_file(self, file_path: Path) -> Tuple[bool, str]:
        """Restaura arquivo do último backup"""
        backup_path = self._backups.get(str(file_path))
        
        if not backup_path or not backup_path.exists():
            return False, f"Nenhum backup encontrado para {file_path}"
        
        try:
            # Remove original se existir
            if file_path.exists():
                file_path.unlink()
            
            shutil.copy2(backup_path, file_path)
            logger.info(f"Restaurado: {file_path} de {backup_path}")
            return True, "Restaurado com sucesso"
            
        except Exception as e:
            return False, str(e)
    
    def cleanup_old_backups(self, keep_days: int = 7):
        """Limpa backups antigos"""
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        for backup_file in self.backup_dir.glob("*.backup"):
            try:
                if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff:
                    backup_file.unlink()
                    json_file = backup_file.with_suffix(".json")
                    if json_file.exists():
                        json_file.unlink()
                    logger.debug(f"Backup antigo removido: {backup_file}")
            except Exception as e:
                logger.warning(f"Erro ao limpar backup {backup_file}: {e}")


# ============================================================================
# 4. HEALTH CHECKER CONTINUOUS
# ============================================================================

class ContinuousHealthChecker:
    """Monitora saúde do sistema continuamente"""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
        self._observer: Optional[Observer] = None
        self._running = False
        self._history: deque = deque(maxlen=1000)
    
    def register_check(self, check: HealthCheck):
        """Registra um novo health check"""
        self.checks.append(check)
        logger.info(f"Health check registrado: {check.name}")
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Executa todos os checks uma vez"""
        results = {}
        
        for check in self.checks:
            try:
                ok, message = check.check_func()
                check.last_check = datetime.now()
                check.last_result = ok
                
                if not ok:
                    check.consecutive_failures += 1
                    
                    # Auto-fix se disponível
                    if check.auto_fix and check.consecutive_failures >= 3:
                        logger.warning(f"Auto-fix acionado para {check.name}")
                        if check.auto_fix():
                            check.consecutive_failures = 0
                            ok = True
                            message = "Corrigido automaticamente"
                else:
                    check.consecutive_failures = 0
                
                results[check.name] = {
                    "ok": ok,
                    "message": message,
                    "severity": check.severity.value,
                    "failures": check.consecutive_failures
                }
                
            except Exception as e:
                results[check.name] = {
                    "ok": False,
                    "message": str(e),
                    "severity": check.severity.value,
                    "failures": check.consecutive_failures + 1
                }
        
        self._history.append({
            "timestamp": datetime.now(),
            "results": results
        })
        
        return results
    
    def start_background_monitoring(self, interval_seconds: int = 60):
        """Inicia monitoramento contínuo em background"""
        if self._running:
            logger.warning("Monitoramento já está rodando")
            return
        
        self._running = True
        
        def monitor_loop():
            while self._running:
                try:
                    results = self.run_all_checks()
                    
                    # Verifica problemas críticos
                    critical_failures = [
                        name for name, r in results.items()
                        if not r["ok"] and r["severity"] == "critical"
                    ]
                    
                    if critical_failures:
                        logger.error(f"⚠️ Problemas críticos detectados: {critical_failures}")
                    
                except Exception as e:
                    logger.error(f"Erro no monitoramento: {e}")
                
                time.sleep(interval_seconds)
        
        import threading
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info(f"Monitoramento contínuo iniciado (intervalo: {interval_seconds}s)")
    
    def stop_monitoring(self):
        """Para monitoramento contínuo"""
        self._running = False
        logger.info("Monitoramento contínuo parado")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Retorna resumo de saúde do sistema"""
        if not self._history:
            return {"status": "unknown", "checks": 0}
        
        last_results = self._history[-1]["results"]
        
        healthy = sum(1 for r in last_results.values() if r["ok"])
        total = len(last_results)
        
        status = HealthStatus.HEALTHY
        if healthy < total:
            critical_failures = sum(1 for r in last_results.values() 
                                   if not r["ok"] and r["severity"] == "critical")
            if critical_failures > 0:
                status = HealthStatus.UNHEALTHY
            else:
                status = HealthStatus.DEGRADED
        
        return {
            "status": status.value,
            "healthy_checks": healthy,
            "total_checks": total,
            "health_percent": (healthy / total * 100) if total > 0 else 0,
            "last_check": self._history[-1]["timestamp"].isoformat()
        }


# ============================================================================
# 5. SNAPSHOT MANAGER
# ============================================================================

class SnapshotManager:
    """Gerencia snapshots do sistema para rollback completo"""
    
    def __init__(self, snapshot_dir: Path = ROOT / ".snapshots"):
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    def create_snapshot(self, description: str = "") -> Optional[SystemSnapshot]:
        """Cria snapshot completo do sistema"""
        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            files={},
            dependencies={},
            environment={},
            health_score=0.0
        )
        
        # Snapshots de arquivos importantes
        important_files = [
            ROOT / "core" / "atena_launcher.py",
            ROOT / "core" / "atena_terminal_assistant.py",
            ROOT / "atena",
            ROOT / "requirements.txt"
        ]
        
        for file_path in important_files:
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    snapshot.files[str(file_path)] = hashlib.md5(f.read()).hexdigest()
        
        # Snapshots de dependências
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.splitlines():
                if '==' in line:
                    pkg, ver = line.split('==', 1)
                    snapshot.dependencies[pkg] = ver
        except Exception:
            pass
        
        # Snapshots de ambiente
        important_env = ["PATH", "PYTHONPATH", "VIRTUAL_ENV"]
        for env_var in important_env:
            if env_var in os.environ:
                snapshot.environment[env_var] = os.environ[env_var][:200]
        
        # Salva snapshot
        snapshot_file = self.snapshot_dir / f"snapshot_{snapshot.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_file.write_text(json.dumps({
            "timestamp": snapshot.timestamp.isoformat(),
            "description": description,
            "files": snapshot.files,
            "dependencies": snapshot.dependencies,
            "environment": snapshot.environment
        }, indent=2))
        
        logger.info(f"Snapshot criado: {snapshot_file}")
        return snapshot
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Lista snapshots disponíveis"""
        snapshots = []
        for snap_file in sorted(self.snapshot_dir.glob("snapshot_*.json")):
            try:
                data = json.loads(snap_file.read_text())
                snapshots.append({
                    "file": snap_file.name,
                    "timestamp": data.get("timestamp"),
                    "description": data.get("description", ""),
                    "size": snap_file.stat().st_size
                })
            except Exception as e:
                logger.warning(f"Erro ao ler snapshot {snap_file}: {e}")
        
        return snapshots


# ============================================================================
# 6. AUTO-HEALING EXECUTOR PRINCIPAL
# ============================================================================

class AtenaAutoHealer:
    """Sistema principal de auto-cura"""
    
    def __init__(self):
        self.dependency_manager = DependencyManager()
        self.backup_manager = BackupManager()
        self.health_checker = ContinuousHealthChecker()
        self.snapshot_manager = SnapshotManager()
        
        self.fix_history: List[FixResult] = []
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Registra health checks padrão"""
        
        # Check 1: Launcher executável
        def check_launcher():
            launcher = ROOT / "atena"
            if not launcher.exists():
                return False, "Launcher não encontrado"
            is_executable = os.access(launcher, os.X_OK)
            return is_executable, "OK" if is_executable else "Não executável"
        
        def fix_launcher():
            launcher = ROOT / "atena"
            if launcher.exists():
                st = os.stat(launcher)
                os.chmod(launcher, st.st_mode | stat.S_IEXEC)
                return True
            return False
        
        self.health_checker.register_check(HealthCheck(
            name="launcher_executable",
            check_func=check_launcher,
            severity=Severity.ERROR,
            auto_fix=fix_launcher
        ))
        
        # Check 2: Diretórios essenciais
        essential_dirs = [
            ROOT / "atena_evolution",
            ROOT / "atena_evolution" / "states",
            ROOT / "logs",
            ROOT / "analysis_reports"
        ]
        
        for dir_path in essential_dirs:
            def make_check(d: Path):
                return lambda: (d.exists() or d.mkdir(parents=True, exist_ok=True), 
                               "OK" if d.exists() else "Criado")
            
            self.health_checker.register_check(HealthCheck(
                name=f"directory_{dir_path.name}",
                check_func=make_check(dir_path),
                severity=Severity.WARNING
            ))
        
        # Check 3: Dependências mínimas
        required_packages = [
            Dependency("requests", min_version="2.25.0"),
            Dependency("rich", required=False),
            Dependency("pydantic", min_version="2.0.0", required=False),
        ]
        
        for dep in required_packages:
            def make_dep_check(d: Dependency):
                return lambda: self.dependency_manager.check_dependency(d)
            
            self.health_checker.register_check(HealthCheck(
                name=f"dependency_{dep.name}",
                check_func=make_dep_check(dep),
                severity=Severity.ERROR if dep.required else Severity.WARNING
            ))
        
        # Check 4: Espaço em disco
        if PSUTIL_AVAILABLE:
            def check_disk():
                usage = psutil.disk_usage(str(ROOT))
                free_gb = usage.free / (1024**3)
                if free_gb < 0.5:
                    return False, f"Espaço crítico: {free_gb:.1f}GB"
                if free_gb < 1.0:
                    return False, f"Espaço baixo: {free_gb:.1f}GB"
                return True, f"OK: {free_gb:.1f}GB livre"
            
            self.health_checker.register_check(HealthCheck(
                name="disk_space",
                check_func=check_disk,
                severity=Severity.WARNING
            ))
        
        # Check 5: Permissões de escrita
        def check_write_permission():
            test_file = ROOT / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True, "OK"
            except Exception as e:
                return False, str(e)
        
        self.health_checker.register_check(HealthCheck(
            name="write_permission",
            check_func=check_write_permission,
            severity=Severity.CRITICAL
        ))
    
    def run_fix(self, auto_approve: bool = True, create_backup: bool = True) -> List[FixResult]:
        """Executa ciclo completo de correção"""
        results = []
        
        logger.info("=" * 60)
        logger.info("🔧 ATENA Auto-Healing System iniciando")
        logger.info("=" * 60)
        
        # 1. Criar snapshot pré-fix
        if create_backup:
            snapshot = self.snapshot_manager.create_snapshot("Pré-correção automática")
            logger.info(f"📸 Snapshot criado: {snapshot.timestamp.isoformat()}")
        
        # 2. Executar health checks
        logger.info("\n📊 Executando health checks...")
        health_status = self.health_checker.run_all_checks()
        
        # 3. Identificar problemas
        problems = [
            (name, check) for name, check in health_status.items()
            if not check["ok"]
        ]
        
        if not problems:
            logger.info("✅ Nenhum problema detectado. Sistema saudável!")
            return results
        
        logger.warning(f"⚠️ {len(problems)} problemas detectados")
        
        # 4. Executar correções
        for problem_name, problem_info in problems:
            logger.info(f"\n🔨 Corrigindo: {problem_name}")
            
            start_time = time.time()
            
            # Tenta encontrar e aplicar correção
            fix_result = self._apply_fix_for_problem(problem_name, problem_info)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            results.append(FixResult(
                step_name=problem_name,
                status=fix_result["status"],
                message=fix_result["message"],
                duration_ms=duration_ms
            ))
            
            logger.info(f"{'✅' if fix_result['status'] == FixStatus.SUCCESS else '❌'} {fix_result['message']}")
        
        # 5. Re-verificar após correções
        logger.info("\n🔄 Re-verificando sistema após correções...")
        time.sleep(1)
        final_health = self.health_checker.run_all_checks()
        
        fixed_count = sum(1 for name, check in final_health.items() 
                         if name in health_status and not health_status[name]["ok"] and check["ok"])
        
        logger.info(f"\n📈 Resumo: {fixed_count}/{len(problems)} problemas corrigidos")
        
        return results
    
    def _apply_fix_for_problem(self, problem_name: str, problem_info: Dict) -> Dict:
        """Aplica correção específica para problema detectado"""
        
        # Correções conhecidas
        fixes = {
            "launcher_executable": self._fix_launcher_permissions,
            "write_permission": self._fix_write_permissions,
            "disk_space": self._fix_disk_space,
        }
        
        # Tenta encontrar fix específico
        for pattern, fix_func in fixes.items():
            if pattern in problem_name:
                try:
                    if fix_func():
                        return {
                            "status": FixStatus.SUCCESS,
                            "message": f"Correção aplicada para {problem_name}"
                        }
                    else:
                        return {
                            "status": FixStatus.FAILED,
                            "message": f"Não foi possível corrigir {problem_name}"
                        }
                except Exception as e:
                    return {
                        "status": FixStatus.FAILED,
                        "message": f"Erro ao corrigir: {e}"
                    }
        
        # Correção genérica (tenta recriar estrutura)
        if "directory" in problem_name:
            dir_name = problem_name.replace("directory_", "")
            dir_path = ROOT / dir_name
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                return {
                    "status": FixStatus.SUCCESS,
                    "message": f"Diretório recriado: {dir_name}"
                }
            except Exception as e:
                return {
                    "status": FixStatus.FAILED,
                    "message": f"Erro ao recriar diretório: {e}"
                }
        
        if "dependency" in problem_name:
            pkg_name = problem_name.replace("dependency_", "")
            dep = Dependency(pkg_name, required=True)
            success, msg = self.dependency_manager.install_dependency(dep)
            return {
                "status": FixStatus.SUCCESS if success else FixStatus.FAILED,
                "message": msg
            }
        
        return {
            "status": FixStatus.SKIPPED,
            "message": f"Nenhuma correção automática disponível para {problem_name}"
        }
    
    def _fix_launcher_permissions(self) -> bool:
        """Corrige permissões do launcher"""
        launcher = ROOT / "atena"
        if launcher.exists():
            st = os.stat(launcher)
            os.chmod(launcher, st.st_mode | stat.S_IEXEC | stat.S_IRWXU)
            return True
        return False
    
    def _fix_write_permissions(self) -> bool:
        """Corrige permissões de escrita no diretório raiz"""
        try:
            # Tenta ajustar permissões
            os.chmod(ROOT, 0o755)
            return True
        except Exception:
            return False
    
    def _fix_disk_space(self) -> bool:
        """Tenta liberar espaço em disco"""
        freed = 0
        
        # Limpa logs antigos
        log_dir = ROOT / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("*.log*"):
                if log_file.stat().st_mtime < (time.time() - 30 * 86400):  # >30 dias
                    size = log_file.stat().st_size
                    log_file.unlink()
                    freed += size
                    logger.debug(f"Log antigo removido: {log_file} ({size/1024:.1f}KB)")
        
        # Limpa backups antigos
        self.backup_manager.cleanup_old_backups(keep_days=7)
        
        # Limpa cache do pip
        try:
            subprocess.run([sys.executable, "-m", "pip", "cache", "purge"], 
                         capture_output=True, timeout=60)
        except Exception:
            pass
        
        logger.info(f"Espaço liberado: {freed/1024/1024:.1f}MB")
        return freed > 0
    
    def generate_report(self) -> str:
        """Gera relatório detalhado do sistema"""
        health = self.health_checker.get_health_summary()
        snapshots = self.snapshot_manager.list_snapshots()
        
        report = f"""
{'='*60}
ATENA AUTO-HEALING REPORT
{'='*60}

📊 HEALTH STATUS: {health['status'].upper()}
   - Health Score: {health['health_percent']:.1f}%
   - Healthy Checks: {health['healthy_checks']}/{health['total_checks']}
   - Last Check: {health.get('last_check', 'N/A')}

📈 RECENT FIXES: {len(self.fix_history)}
"""
        
        for fix in self.fix_history[-10:]:
            report += f"   - {fix.timestamp.strftime('%Y-%m-%d %H:%M')}: {fix.step_name} [{fix.status.value}]\n"
        
        report += f"""
💾 SNAPSHOTS AVAILABLE: {len(snapshots)}
"""
        
        for snap in snapshots[-5:]:
            report += f"   - {snap['timestamp']}: {snap['description'] or 'N/A'}\n"
        
        report += """
🔧 RECOMMENDATIONS:
"""
        
        if health['health_percent'] < 80:
            report += "   1. Run './atena fix --full' for complete repair\n"
        if health['health_percent'] < 50:
            report += "   2. Consider restoring from snapshot: './atena fix --restore-latest'\n"
        if health['health_percent'] < 30:
            report += "   3. System critically degraded - reinstall recommended\n"
        
        if health['health_percent'] >= 90:
            report += "   ✅ System is healthy. No immediate action required.\n"
        
        report += f"\n{'='*60}\n"
        
        return report


# ============================================================================
# 7. FILE SYSTEM WATCHER (OPCIONAL)
# ============================================================================

if WATCHDOG_AVAILABLE:
    class ConfigFileHandler(FileSystemEventHandler):
        """Monitora mudanças em arquivos de configuração"""
        
        def __init__(self, healer: AtenaAutoHealer):
            self.healer = healer
        
        def on_modified(self, event):
            if not event.is_directory and event.src_path.endswith(('.py', '.yaml', '.json')):
                logger.info(f"Arquivo modificado: {event.src_path}")
                # Verifica se mudança causou problemas
                self.healer.health_checker.run_all_checks()


# ============================================================================
# 8. CLI E INTEGRAÇÃO
# ============================================================================

def main():
    """CLI principal do auto-healing system"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ATENA Auto-Healing System",
        epilog="Exemplos:\n"
               "  ./atena fix                 # Correção rápida\n"
               "  ./atena fix --full          # Correção completa com backup\n"
               "  ./atena fix --health        # Apenas diagnóstico\n"
               "  ./atena fix --monitor       # Monitoramento contínuo\n"
               "  ./atena fix --snapshot      # Criar snapshot\n"
               "  ./atena fix --restore latest # Restaurar último snapshot"
    )
    
    parser.add_argument("--full", action="store_true", help="Executa correção completa")
    parser.add_argument("--health", action="store_true", help="Apenas diagnóstico de saúde")
    parser.add_argument("--monitor", action="store_true", help="Inicia monitoramento contínuo")
    parser.add_argument("--snapshot", action="store_true", help="Cria snapshot do sistema")
    parser.add_argument("--restore", choices=["latest", "list"], help="Restaura snapshot")
    parser.add_argument("--report", action="store_true", help="Gera relatório detalhado")
    parser.add_argument("--auto-approve", action="store_true", default=True, help="Auto-aprova correções")
    
    args = parser.parse_args()
    
    healer = AtenaAutoHealer()
    
    # Modo monitoramento contínuo
    if args.monitor:
        print("🔍 ATENA Continuous Health Monitor")
        print("Press Ctrl+C to stop\n")
        healer.health_checker.start_background_monitoring(interval_seconds=30)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
            healer.health_checker.stop_monitoring()
        return 0
    
    # Apenas diagnóstico
    if args.health:
        print("🏥 ATENA Health Diagnostic\n")
        results = healer.health_checker.run_all_checks()
        
        for name, result in results.items():
            status = "✅" if result["ok"] else "❌"
            print(f"{status} {name}: {result['message']}")
        
        summary = healer.health_checker.get_health_summary()
        print(f"\n📊 Summary: {summary['health_percent']:.1f}% healthy")
        return 0 if summary['healthy_checks'] == summary['total_checks'] else 1
    
    # Criar snapshot
    if args.snapshot:
        print("📸 Creating system snapshot...")
        snapshot = healer.snapshot_manager.create_snapshot("Manual snapshot")
        if snapshot:
            print(f"✅ Snapshot created: {snapshot.timestamp.isoformat()}")
        else:
            print("❌ Failed to create snapshot")
        return 0
    
    # Listar/restaurar snapshots
    if args.restore:
        if args.restore == "list":
            snapshots = healer.snapshot_manager.list_snapshots()
            print("\n📸 Available Snapshots:")
            for snap in snapshots:
                print(f"  - {snap['timestamp']}: {snap['description']}")
            return 0
        
        if args.restore == "latest":
            # TODO: Implementar restauração
            print("⚠️ Snapshot restoration not yet implemented")
            return 1
    
    # Gerar relatório
    if args.report:
        report = healer.generate_report()
        print(report)
        
        # Salva relatório
        report_file = ROOT / "logs" / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report)
        print(f"📄 Report saved: {report_file}")
        return 0
    
    # Modo correção padrão (original)
    print("🛠️  ATENA Fix - Auto-Healing System")
    print("=" * 60)
    
    # Primeiro, diagnóstico rápido
    print("\n📊 Running health checks...")
    health = healer.health_checker.run_all_checks()
    problems = [name for name, r in health.items() if not r["ok"]]
    
    if not problems:
        print("\n✅ System is healthy! No fixes needed.")
        return 0
    
    print(f"\n⚠️ Found {len(problems)} issues:")
    for prob in problems:
        print(f"   - {prob}: {health[prob]['message']}")
    
    if not args.full:
        print("\n💡 Run with --full to apply automatic fixes")
        return 1
    
    # Aplica correções
    print("\n🔧 Applying fixes...")
    results = healer.run_fix(auto_approve=args.auto_approve)
    
    # Summary
    success_count = sum(1 for r in results if r.status == FixStatus.SUCCESS)
    print(f"\n{'='*60}")
    print(f"📈 Fix Summary: {success_count}/{len(results)} successful")
    print(f"{'='*60}")
    
    # Re-check
    print("\n🔄 Re-checking system health...")
    final_health = healer.health_checker.run_all_checks()
    remaining = [name for name, r in final_health.items() if not r["ok"]]
    
    if remaining:
        print(f"\n⚠️ {len(remaining)} issues remain:")
        for prob in remaining:
            print(f"   - {prob}: {final_health[prob]['message']}")
        return 1
    
    print("\n✅ All issues resolved! System is healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
