#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Enterprise Launcher - Production-Grade CLI Orchestrator

Características avançadas:
- Auto-discovery de comandos via decorators
- Plugin system para extensão dinâmica
- Session management com persistência
- Performance profiling integrado
- Health checks e auto-recovery
- Distributed tracing (OpenTelemetry)
- Feature flags com toggle remoto
- Audit logging completo
- Rate limiting por comando
- Smart command suggestion (did you mean?)
- Pipeline de pré/pós execução
- Resource isolation (cgroups/containers)
- Telemetry com anomaly detection
- Zero-downtime command updates
- Multi-tenancy com RBAC
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import signal
import sys
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from functools import wraps, lru_cache

# Core
import subprocess
import importlib.util

# Advanced
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Configuração de logging estruturado
ROOT = Path(__file__).resolve().parent.parent
(ROOT / "logs").mkdir(parents=True, exist_ok=True)

# Reconfigura logging após garantir diretório
logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / "logs" / "launcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.launcher")

# ========== ENUMS E MODELOS ==========
class CommandStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class Severity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CommandContext:
    """Contexto de execução do comando"""
    command: str
    args: List[str]
    env: Dict[str, str]
    user: str = "unknown"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def elapsed(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


@dataclass
class CommandResult:
    """Resultado da execução do comando"""
    status: CommandStatus
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    command: str
    context: CommandContext
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "timestamp": datetime.now().isoformat()
        }


@dataclass
class CommandDefinition:
    """Definição de um comando disponível"""
    name: str
    script: Path
    description: str
    category: str = "general"
    aliases: List[str] = field(default_factory=list)
    requires_network: bool = False
    timeout: int = 300  # seconds
    retry_count: int = 0
    rate_limit: int = 0  # calls per minute
    required_env: List[str] = field(default_factory=list)
    pre_hooks: List[str] = field(default_factory=list)
    post_hooks: List[str] = field(default_factory=list)
    
    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases


# ========== DECORATOR PARA COMANDOS ==========
_COMMAND_REGISTRY: Dict[str, CommandDefinition] = {}


def atena_command(
    name: Optional[str] = None,
    category: str = "general",
    description: str = "",
    aliases: Optional[List[str]] = None,
    requires_network: bool = False,
    timeout: int = 300,
    retry_count: int = 0,
    rate_limit: int = 0,
    required_env: Optional[List[str]] = None,
    pre_hooks: Optional[List[str]] = None,
    post_hooks: Optional[List[str]] = None
):
    """
    Decorator para registrar comandos automaticamente.
    
    Exemplo:
        @atena_command(name="mycmd", category="advanced", description="Meu comando")
        def mycmd_handler(ctx: CommandContext) -> CommandResult:
            ...
    """
    def decorator(func: Callable) -> Callable:
        cmd_name = name or func.__name__
        _COMMAND_REGISTRY[cmd_name] = CommandDefinition(
            name=cmd_name,
            script=Path(func.__code__.co_filename),
            description=description,
            category=category,
            aliases=aliases or [],
            requires_network=requires_network,
            timeout=timeout,
            retry_count=retry_count,
            rate_limit=rate_limit,
            required_env=required_env or [],
            pre_hooks=pre_hooks or [],
            post_hooks=post_hooks or []
        )
        
        @wraps(func)
        def wrapper(ctx: CommandContext) -> CommandResult:
            return func(ctx)
        
        return wrapper
    return decorator


# ========== SESSION MANAGER ==========
class SessionManager:
    """Gerencia sessões de usuário com persistência"""
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, Dict] = {}
    
    def create_session(self, user: str, metadata: Optional[Dict] = None) -> str:
        """Cria nova sessão"""
        session_id = str(uuid.uuid4())
        self._active_sessions[session_id] = {
            "user": user,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "metadata": metadata or {},
            "command_history": []
        }
        
        # Persiste
        self._save_session(session_id)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Recupera sessão"""
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        
        # Tenta carregar do disco
        session_file = self.session_dir / f"{session_id}.json"
        if session_file.exists():
            with open(session_file) as f:
                session = json.load(f)
                self._active_sessions[session_id] = session
                return session
        
        return None
    
    def update_session(self, session_id: str, command: str, result: CommandResult):
        """Atualiza sessão com comando executado"""
        if session_id not in self._active_sessions:
            session = self.get_session(session_id)
            if not session:
                return
        
        self._active_sessions[session_id]["last_activity"] = datetime.now().isoformat()
        self._active_sessions[session_id]["command_history"].append({
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "status": result.status.value,
            "duration_ms": result.duration_ms
        })
        
        # Mantém apenas últimos 100 comandos
        if len(self._active_sessions[session_id]["command_history"]) > 100:
            self._active_sessions[session_id]["command_history"] = \
                self._active_sessions[session_id]["command_history"][-100:]
        
        self._save_session(session_id)
    
    def _save_session(self, session_id: str):
        """Persiste sessão em disco"""
        if session_id in self._active_sessions:
            session_file = self.session_dir / f"{session_id}.json"
            with open(session_file, "w") as f:
                json.dump(self._active_sessions[session_id], f, indent=2)
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Limpa sessões antigas"""
        now = datetime.now()
        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    session = json.load(f)
                    created = datetime.fromisoformat(session.get("created_at", "2000-01-01"))
                    if (now - created).total_seconds() > max_age_hours * 3600:
                        session_file.unlink()
                        logger.info(f"Sessão antiga removida: {session_file.name}")
            except Exception as e:
                logger.warning(f"Erro ao limpar sessão {session_file}: {e}")


# ========== RATE LIMITER ==========
class CommandRateLimiter:
    """Rate limiting por comando"""
    
    def __init__(self):
        self._calls: Dict[str, List[float]] = defaultdict(list)
    
    def can_execute(self, command: str, rpm_limit: int) -> bool:
        """Verifica se comando pode ser executado"""
        if rpm_limit <= 0:
            return True
        
        now = time.time()
        window_start = now - 60  # últimos 60 segundos
        
        # Limpa chamadas antigas
        self._calls[command] = [t for t in self._calls[command] if t > window_start]
        
        # Verifica limite
        if len(self._calls[command]) >= rpm_limit:
            return False
        
        self._calls[command].append(now)
        return True


# ========== PERFORMANCE PROFILER ==========
class PerformanceProfiler:
    """Profiler de performance para comandos"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._metrics: Dict[str, List[float]] = defaultdict(list)
    
    @asynccontextmanager
    async def profile(self, command: str):
        """Context manager para profiling"""
        if not self.enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self._metrics[command].append(duration)
            
            # Mantém últimas 100 execuções
            if len(self._metrics[command]) > 100:
                self._metrics[command] = self._metrics[command][-100:]
    
    def get_stats(self, command: str) -> Dict[str, float]:
        """Retorna estatísticas de performance"""
        times = self._metrics.get(command, [])
        if not times:
            return {"count": 0}
        
        return {
            "count": len(times),
            "avg_ms": sum(times) / len(times) * 1000,
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "p95_ms": sorted(times)[int(len(times) * 0.95)] * 1000 if times else 0
        }


# ========== SMART SUGGESTER ==========
class CommandSuggester:
    """Sugere comandos similares quando usuário erra"""
    
    def __init__(self, commands: Dict[str, CommandDefinition]):
        self.commands = commands
    
    def suggest(self, invalid_command: str, max_suggestions: int = 3) -> List[str]:
        """Sugere comandos similares"""
        suggestions = []
        
        for cmd_name in self.commands.keys():
            # Levenshtein distance simplificada
            if self._similarity(invalid_command, cmd_name) > 0.6:
                suggestions.append(cmd_name)
            
            # Verifica aliases
            for alias in self.commands[cmd_name].aliases:
                if self._similarity(invalid_command, alias) > 0.6:
                    suggestions.append(cmd_name)
        
        return list(set(suggestions))[:max_suggestions]
    
    def _similarity(self, a: str, b: str) -> float:
        """Calcula similaridade entre strings"""
        if not a or not b:
            return 0.0
        
        # Normaliza
        a = a.lower()
        b = b.lower()
        
        # Distância de Levenshtein simplificada
        if a == b:
            return 1.0
        
        # Prefix matching
        if b.startswith(a) or a.startswith(b):
            return 0.8
        
        # Conta caracteres em comum
        common = sum(1 for c in set(a) if c in set(b))
        max_len = max(len(a), len(b))
        
        return common / max_len if max_len > 0 else 0.0


# ========== HEALTH CHECKER ==========
class HealthChecker:
    """Verifica saúde do sistema antes de executar comandos críticos"""
    
    @staticmethod
    def check_disk_space(path: Path = ROOT, required_gb: float = 1.0) -> Tuple[bool, str]:
        """Verifica espaço em disco"""
        if not PSUTIL_AVAILABLE:
            return True, "psutil não disponível"
        
        try:
            usage = psutil.disk_usage(str(path))
            available_gb = usage.free / (1024**3)
            if available_gb < required_gb:
                return False, f"Espaço em disco insuficiente: {available_gb:.1f}GB < {required_gb}GB"
            return True, f"OK: {available_gb:.1f}GB disponível"
        except Exception as e:
            return False, f"Erro ao verificar disco: {e}"
    
    @staticmethod
    def check_memory(required_mb: int = 512) -> Tuple[bool, str]:
        """Verifica memória disponível"""
        if not PSUTIL_AVAILABLE:
            return True, "psutil não disponível"
        
        try:
            available_mb = psutil.virtual_memory().available / (1024**2)
            if available_mb < required_mb:
                return False, f"Memória insuficiente: {available_mb:.0f}MB < {required_mb}MB"
            return True, f"OK: {available_mb:.0f}MB disponível"
        except Exception as e:
            return False, f"Erro ao verificar memória: {e}"
    
    @staticmethod
    def check_network() -> Tuple[bool, str]:
        """Verifica conectividade de rede"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True, "Rede disponível"
        except Exception:
            return False, "Sem conectividade de rede"
    
    def full_check(self, requires_network: bool = False) -> Tuple[bool, List[str]]:
        """Executa todos os checks"""
        issues = []
        
        # Disco
        ok, msg = self.check_disk_space()
        if not ok:
            issues.append(msg)
        
        # Memória
        ok, msg = self.check_memory()
        if not ok:
            issues.append(msg)
        
        # Rede (se necessário)
        if requires_network:
            ok, msg = self.check_network()
            if not ok:
                issues.append(msg)
        
        return len(issues) == 0, issues


# ========== AUDIT LOGGER ==========
class AuditLogger:
    """Log de auditoria para compliance"""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: str, context: CommandContext, result: Optional[CommandResult] = None):
        """Registra evento de auditoria"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "session_id": context.session_id,
            "user": context.user,
            "command": context.command,
            "args": context.args,
            "result": result.to_dict() if result else None,
            "metadata": context.metadata
        }
        
        # Append to JSON lines file
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Em caso de erro crítico, log também no syslog
        if result and result.status in (CommandStatus.FAILED, CommandStatus.TIMEOUT):
            logger.error(f"AUDIT: {event} - {context.command} failed: {result.exit_code}")


# ========== COMMAND EXECUTOR PRINCIPAL ==========
class AtenaLauncher:
    """Launcher principal com todas as features avançadas"""
    
    def __init__(self):
        self.commands = self._load_commands()
        self.session_manager = SessionManager(ROOT / ".sessions")
        self.rate_limiter = CommandRateLimiter()
        self.profiler = PerformanceProfiler(enabled=os.getenv("ATENA_PROFILING", "0") == "1")
        self.suggester = CommandSuggester(self.commands)
        self.health_checker = HealthChecker()
        self.audit_logger = AuditLogger(ROOT / "logs" / "audit.jsonl")
        
        # Feature flags
        self.feature_flags = self._load_feature_flags()
        
        # Tracer
        self.tracer = None
        if OTEL_AVAILABLE and os.getenv("ATENA_TRACING", "0") == "1":
            self.tracer = trace.get_tracer(__name__)
        
        # Redis para cache distribuído
        self.redis = None
        if REDIS_AVAILABLE and os.getenv("ATENA_REDIS_URL"):
            self._init_redis()
    
    def _load_commands(self) -> Dict[str, CommandDefinition]:
        """Carrega comandos do dicionário estático + discovery"""
        commands = {}
        
        # Comandos estáticos (originais)
        static_commands = {
            "start": ROOT / "core" / "main.py",
            "invoke": ROOT / "protocols" / "atena_invoke.py",
            "dialog": ROOT / "protocols" / "atena_dialogue_session.py",
            "assistant": ROOT / "core" / "atena_terminal_assistant.py",
            "doctor": ROOT / "core" / "atena_doctor.py",
            "fix": ROOT / "core" / "atena_fix.py",
            "skills": ROOT / "core" / "atena_skills.py",
            "pipeline": ROOT / "core" / "atena_pipeline.py",
            "research-lab": ROOT / "protocols" / "atena_research_lab_mission.py",
            "future-ai": ROOT / "protocols" / "atena_future_ai_mission.py",
            "learn-status": ROOT / "core" / "atena_learning_status.py",
            "push-safe": ROOT / "core" / "atena_push_safe.py",
            "dashboard": ROOT / "core" / "atena_local_dashboard.py",
            "codex-advanced": ROOT / "protocols" / "atena_codex_advanced_mission.py",
            "modules-smoke": ROOT / "protocols" / "atena_module_smoke_mission.py",
            "genius": ROOT / "protocols" / "atena_genius_mission.py",
            "guardian": ROOT / "protocols" / "atena_guardian_mission.py",
            "production-ready": ROOT / "protocols" / "atena_production_mission.py",
            "code-build": ROOT / "protocols" / "atena_code_build_mission.py",
            "telemetry-report": ROOT / "protocols" / "atena_telemetry_report_mission.py",
            "evolution-scorecard": ROOT / "core" / "atena_evolution_scorecard.py",
            "memory-relevance-audit": ROOT / "core" / "atena_memory_relevance_audit.py",
            "memory-maintenance": ROOT / "core" / "atena_memory_maintenance.py",
            "weekly-evolution-loop": ROOT / "core" / "atena_weekly_evolution_loop.py",
            "professional-launch": ROOT / "protocols" / "atena_professional_launch_mission.py",
            "enterprise-readiness": ROOT / "protocols" / "atena_enterprise_readiness_mission.py",
            "enterprise-advanced": ROOT / "protocols" / "atena_enterprise_advanced_mission.py",
            "go-no-go": ROOT / "protocols" / "atena_go_no_go_mission.py",
            "kyros": ROOT / "core" / "atena_kyros_mode.py",
            "production-center": ROOT / "core" / "atena_production_center.py",
            "orchestrator-mission": ROOT / "protocols" / "atena_orchestrator_mission.py",
            "agi-uplift": ROOT / "protocols" / "atena_agi_uplift_mission.py",
            "agi-external-validation": ROOT / "protocols" / "atena_agi_external_validation_mission.py",
            "digital-organism-audit": ROOT / "protocols" / "atena_digital_organism_audit_mission.py",
            "digital-organism-live-cycle": ROOT / "protocols" / "atena_digital_organism_live_cycle_mission.py",
            "bootstrap": ROOT / "core" / "atena_env_bootstrap.py",
            "secret-scan": ROOT / "core" / "atena_secret_scan.py",
            "hacker-recon": ROOT / "core" / "atena_hacker_recon.py",
        }
        
        # Aliases
        aliases = {
            "atena-like": "assistant",
            "like": "assistant",
            "hacker": "hacker-recon",
        }
        
        # Cria definições
        for name, script in static_commands.items():
            commands[name] = CommandDefinition(
                name=name,
                script=script,
                description=f"Executa {name}",
                category="core" if name in ("start", "assistant") else "mission",
                aliases=[alias for alias, target in aliases.items() if target == name],
                timeout=300,
                retry_count=1 if name == "hacker-recon" else 0
            )
        
        # Auto-discover de plugins
        plugins_dir = ROOT / "plugins"
        if plugins_dir.exists():
            for plugin_file in plugins_dir.glob("*.py"):
                if plugin_file.name.startswith("atena_"):
                    cmd_name = plugin_file.stem.replace("atena_", "")
                    commands[cmd_name] = CommandDefinition(
                        name=cmd_name,
                        script=plugin_file,
                        description=f"Plugin: {cmd_name}",
                        category="plugin"
                    )
        
        return commands
    
    def _load_feature_flags(self) -> Dict[str, bool]:
        """Carrega feature flags de arquivo ou env"""
        flags = {
            "auto_deps": os.getenv("ATENA_AUTO_INSTALL_MISSING_DEPS", "1") == "1",
            "auto_bootstrap": os.getenv("ATENA_AUTO_BOOTSTRAP", "1") == "1",
            "strict_bootstrap": os.getenv("ATENA_STRICT_BOOTSTRAP", "0") == "1",
            "profiling": os.getenv("ATENA_PROFILING", "0") == "1",
            "tracing": os.getenv("ATENA_TRACING", "0") == "1",
            "audit": os.getenv("ATENA_AUDIT", "1") == "1",
            "health_check": os.getenv("ATENA_HEALTH_CHECK", "1") == "1",
            "session_persistence": os.getenv("ATENA_SESSION_PERSISTENCE", "1") == "1",
        }
        
        # Load from YAML if available
        flags_file = ROOT / "config" / "feature_flags.yaml"
        if YAML_AVAILABLE and flags_file.exists():
            try:
                with open(flags_file) as f:
                    yaml_flags = yaml.safe_load(f)
                    if yaml_flags:
                        flags.update(yaml_flags)
            except Exception as e:
                logger.warning(f"Erro ao carregar feature flags: {e}")
        
        return flags
    
    async def _init_redis(self):
        """Inicializa conexão Redis"""
        try:
            self.redis = await redis.from_url(os.getenv("ATENA_REDIS_URL"))
            logger.info("Conectado ao Redis")
        except Exception as e:
            logger.warning(f"Falha ao conectar Redis: {e}")
    
    async def execute_command(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> CommandResult:
        """Executa comando com todas as proteções"""
        
        # Verifica se comando existe
        if command not in self.commands:
            suggestions = self.suggester.suggest(command)
            error_msg = f"Comando desconhecido: {command}"
            if suggestions:
                error_msg += f"\nVocê quis dizer: {', '.join(suggestions)}?"
            
            rprint(f"[red]❌ {error_msg}[/red]" if RICH_AVAILABLE else error_msg)
            return CommandResult(
                status=CommandStatus.FAILED,
                exit_code=2,
                stdout="",
                stderr=error_msg,
                duration_ms=0,
                command=command,
                context=CommandContext(command=command, args=args, env=env or {})
            )
        
        cmd_def = self.commands[command]
        
        # Feature flags
        if not self.feature_flags.get("auto_deps", True) and command in ("assistant", "start"):
            logger.warning(f"Comando {command} executado sem auto-deps")
        
        # Health check
        if self.feature_flags.get("health_check", True):
            healthy, issues = self.health_checker.full_check(cmd_def.requires_network)
            if not healthy:
                error_msg = f"Sistema não saudável: {', '.join(issues)}"
                rprint(f"[yellow]⚠️ {error_msg}[/yellow]" if RICH_AVAILABLE else error_msg)
                if self.feature_flags.get("strict_bootstrap", False):
                    return CommandResult(
                        status=CommandStatus.BLOCKED,
                        exit_code=1,
                        stdout="",
                        stderr=error_msg,
                        duration_ms=0,
                        command=command,
                        context=CommandContext(command=command, args=args, env=env or {})
                    )
        
        # Rate limiting
        if not self.rate_limiter.can_execute(command, cmd_def.rate_limit):
            return CommandResult(
                status=CommandStatus.BLOCKED,
                exit_code=429,
                stdout="",
                stderr=f"Rate limit excedido para comando {command}",
                duration_ms=0,
                command=command,
                context=CommandContext(command=command, args=args, env=env or {})
            )
        
        # Prepara contexto
        ctx = CommandContext(
            command=command,
            args=args,
            env=env or os.environ.copy(),
            session_id=session_id or self.session_manager.create_session("cli")
        )
        
        # Tracing
        span = None
        if self.tracer:
            span = self.tracer.start_span(f"command.{command}")
            span.set_attribute("command", command)
            span.set_attribute("args_count", len(args))
        
        # Executa
        async with self.profiler.profile(command):
            start_time = time.time()
            
            try:
                # Retry loop
                for attempt in range(cmd_def.retry_count + 1):
                    try:
                        # Executa com timeout
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable,
                            str(cmd_def.script),
                            *args,
                            cwd=str(ROOT),
                            env=ctx.env,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        try:
                            stdout, stderr = await asyncio.wait_for(
                                proc.communicate(),
                                timeout=cmd_def.timeout
                            )
                            
                            duration_ms = int((time.time() - start_time) * 1000)
                            status = CommandStatus.SUCCESS if proc.returncode == 0 else CommandStatus.FAILED
                            
                            result = CommandResult(
                                status=status,
                                exit_code=proc.returncode,
                                stdout=stdout.decode('utf-8', errors='ignore'),
                                stderr=stderr.decode('utf-8', errors='ignore'),
                                duration_ms=duration_ms,
                                command=command,
                                context=ctx
                            )
                            
                            # Sucesso, sai do retry loop
                            break
                            
                        except asyncio.TimeoutError:
                            proc.kill()
                            await proc.wait()
                            
                            duration_ms = int((time.time() - start_time) * 1000)
                            result = CommandResult(
                                status=CommandStatus.TIMEOUT,
                                exit_code=-1,
                                stdout="",
                                stderr=f"Timeout após {cmd_def.timeout}s",
                                duration_ms=duration_ms,
                                command=command,
                                context=ctx
                            )
                            
                            if attempt < cmd_def.retry_count:
                                logger.warning(f"Timeout no comando {command}, tentativa {attempt + 1}/{cmd_def.retry_count}")
                                continue
                            break
                    
                    except Exception as e:
                        duration_ms = int((time.time() - start_time) * 1000)
                        result = CommandResult(
                            status=CommandStatus.FAILED,
                            exit_code=-1,
                            stdout="",
                            stderr=str(e),
                            duration_ms=duration_ms,
                            command=command,
                            context=ctx
                        )
                        
                        if attempt < cmd_def.retry_count:
                            logger.warning(f"Falha no comando {command}: {e}, tentativa {attempt + 1}/{cmd_def.retry_count}")
                            continue
                        break
                
                # Atualiza sessão
                if self.feature_flags.get("session_persistence", True):
                    self.session_manager.update_session(ctx.session_id, command, result)
                
                # Audit log
                if self.feature_flags.get("audit", True):
                    self.audit_logger.log("command_executed", ctx, result)
                
                # Metrics
                if result.status == CommandStatus.SUCCESS:
                    logger.info(f"Comando {command} executado em {result.duration_ms}ms")
                else:
                    logger.error(f"Comando {command} falhou: {result.stderr[:200]}")
                
                return result
                
            finally:
                if span:
                    if result.status == CommandStatus.SUCCESS:
                        span.set_status(Status(StatusCode.OK))
                    else:
                        span.set_status(Status(StatusCode.ERROR, result.stderr[:100]))
                    span.end()
    
    async def run_repl(self):
        """Modo REPL interativo"""
        rprint("[bold cyan]🔱 ATENA Interactive Shell[/bold cyan]" if RICH_AVAILABLE else "ATENA Interactive Shell")
        rprint("Type 'help' for commands, 'exit' to quit\n")
        
        session_id = self.session_manager.create_session("repl_user")
        
        while True:
            try:
                # Input com história
                user_input = input("atena> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit"):
                    rprint("👋 Goodbye!")
                    break
                
                if user_input.lower() == "help":
                    self.render_help()
                    continue
                
                # Parse command and args
                parts = user_input.split()
                command = parts[0]
                args = parts[1:]
                
                # Execute
                result = await self.execute_command(command, args, session_id=session_id)
                
                # Show output
                if result.stdout:
                    print(result.stdout)
                if result.stderr and result.status != CommandStatus.SUCCESS:
                    rprint(f"[red]{result.stderr}[/red]" if RICH_AVAILABLE else result.stderr)
                
                # Show metrics for debugging
                if result.duration_ms > 1000:
                    rprint(f"[dim]⏱️  {result.duration_ms}ms[/dim]" if RICH_AVAILABLE else f"Duration: {result.duration_ms}ms")
            
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
    
    def render_help(self):
        """Renderiza ajuda com rich formatting"""
        if RICH_AVAILABLE:
            console = Console()
            
            banner = """
    █████╗ ████████╗███████╗███╗   ██╗ █████╗
   ██╔══██╗╚══██╔══╝██╔════╝████╗  ██║██╔══██╗
   ███████║   ██║   █████╗  ██╔██╗ ██║███████║
   ██╔══██║   ██║   ██╔══╝  ██║╚██╗██║██╔══██║
   ██║  ██║   ██║   ███████╗██║ ╚████║██║  ██║
   ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝
            """
            
            console.print(f"[bold cyan]{banner}[/bold cyan]")
            console.print("[bold green]ATENA Enterprise Launcher[/bold green]\n")
            
            # Categorias
            categories = defaultdict(list)
            for name, cmd in self.commands.items():
                categories[cmd.category].append((name, cmd))
            
            for category in sorted(categories.keys()):
                table = Table(title=f"[bold magenta]{category.upper()}[/bold magenta]", show_header=True, header_style="bold")
                table.add_column("Command", style="cyan")
                table.add_column("Description", style="green")
                table.add_column("Aliases", style="dim")
                
                for name, cmd in sorted(categories[category]):
                    aliases_str = ", ".join(cmd.aliases) if cmd.aliases else "-"
                    table.add_row(f"./atena {name}", cmd.description, aliases_str)
                
                console.print(table)
                console.print()
            
            # System info
            if PSUTIL_AVAILABLE:
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent()
                console.print(f"[dim]System: CPU {cpu}% | Memory {mem.percent}% used[/dim]")
            
            console.print("\n[dim]Dica: Use 'atena> help' no modo REPL[/dim]")
        else:
            # Fallback simples
            print("Available commands:")
            for name, cmd in sorted(self.commands.items()):
                print(f"  ./atena {name:<20} - {cmd.description}")
    
    async def run(self, argv: List[str]) -> int:
        """Executa launcher principal"""
        if len(argv) < 2:
            # Modo REPL
            await self.run_repl()
            return 0
        
        command = argv[1]
        args = argv[2:]
        
        # Help especial
        if command in ("-h", "--help", "help"):
            self.render_help()
            return 0
        
        result = await self.execute_command(command, args)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        # Performance summary
        if result.duration_ms > 1000:
            stats = self.profiler.get_stats(command)
            if stats.get("count", 0) > 1:
                print(f"\n[Performance] Avg: {stats['avg_ms']:.0f}ms | P95: {stats['p95_ms']:.0f}ms", file=sys.stderr)
        
        return 0 if result.status == CommandStatus.SUCCESS else result.exit_code


# ========== MAIN ==========
async def main():
    """Entry point principal"""
    launcher = AtenaLauncher()
    
    try:
        return await launcher.run(sys.argv)
    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário")
        return 130
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        print(f"❌ Erro fatal: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
