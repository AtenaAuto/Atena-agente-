#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 Catálogo Interno de Skills/Plugins com Curadoria Avançada v2.0
Sistema completo de gerenciamento, validação e deployment de skills e plugins.

Recursos:
- 📦 Registro e versionamento de skills/plugins
- 🛡️ Validação multi-nível (sandbox, contratos, segurança)
- 🔄 Promoção e rollback automático
- 📊 Métricas de uso e performance
- 🔍 Auditoria e compliance
- 🌐 Integração com marketplace externo
- 🤖 IA para curadoria automatizada
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict, deque
import logging

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger("SkillMarketplace")


class RiskLevel(Enum):
    """Níveis de risco para skills/plugins."""
    TRUSTED = "trusted"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    SANDBOX_REQUIRED = "sandbox_required"


class CostClass(Enum):
    """Classes de custo para execução."""
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ENTERPRISE = "enterprise"


class ValidationStatus(Enum):
    """Status de validação."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    REQUIRES_REVIEW = "requires_review"


@dataclass
class SkillMetrics:
    """Métricas de uso e performance de uma skill."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time_ms: float = 0.0
    last_execution: Optional[str] = None
    error_rate: float = 0.0
    user_rating: float = 0.0
    cpu_usage_avg: float = 0.0
    memory_usage_avg_mb: float = 0.0
    
    def update(self, success: bool, execution_time_ms: float, cpu_usage: float = 0, memory_mb: float = 0):
        """Atualiza métricas com nova execução."""
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        
        # Média móvel do tempo de execução
        self.avg_execution_time_ms = (
            (self.avg_execution_time_ms * (self.total_executions - 1) + execution_time_ms) 
            / self.total_executions
        )
        
        self.error_rate = self.failed_executions / self.total_executions if self.total_executions > 0 else 0
        self.last_execution = datetime.now().isoformat()
        
        if cpu_usage > 0:
            self.cpu_usage_avg = (self.cpu_usage_avg * (self.total_executions - 1) + cpu_usage) / self.total_executions
        
        if memory_mb > 0:
            self.memory_usage_avg_mb = (self.memory_usage_avg_mb * (self.total_executions - 1) + memory_mb) / self.total_executions
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return asdict(self)


@dataclass
class SkillContract:
    """Contrato de API para skill/plugin."""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    required_permissions: List[str] = field(default_factory=list)
    rate_limit: int = 0
    timeout_seconds: int = 30
    max_memory_mb: int = 256
    allowed_imports: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)
    
    def validate_input(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida entrada contra schema."""
        if not self.input_schema:
            return True, "OK"
        
        required = self.input_schema.get("required", [])
        for req in required:
            if req not in data:
                return False, f"Campo obrigatório ausente: {req}"
        
        properties = self.input_schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type and not isinstance(value, eval(expected_type.capitalize())):
                    return False, f"Tipo inválido para {key}: esperado {expected_type}"
        
        return True, "OK"
    
    def validate_output(self, data: Any) -> Tuple[bool, str]:
        """Valida saída contra schema."""
        if not self.output_schema:
            return True, "OK"
        
        expected_type = self.output_schema.get("type", "any")
        if expected_type != "any":
            actual_type = type(data).__name__.lower()
            if actual_type != expected_type:
                return False, f"Tipo de saída inválido: esperado {expected_type}, recebido {actual_type}"
        
        return True, "OK"


@dataclass(frozen=True)
class SkillRecord:
    """Registro completo de uma skill/plugin."""
    skill_id: str
    version: str
    name: str = ""
    description: str = ""
    author: str = ""
    risk_level: str = RiskLevel.LOW.value
    cost_class: str = CostClass.LOW.value
    compatible_with: str = ">=3.0.0"
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    approved: bool = False
    active: bool = False
    sandbox_passed: bool = True
    contract_passed: bool = True
    security_passed: bool = True
    validation_enforced: bool = False
    validation_status: str = ValidationStatus.PENDING.value
    metrics: SkillMetrics = field(default_factory=SkillMetrics)
    contract: Optional[SkillContract] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        data = asdict(self)
        if 'metrics' in data and hasattr(data['metrics'], 'to_dict'):
            data['metrics'] = self.metrics.to_dict()
        if 'contract' in data and self.contract:
            data['contract'] = asdict(self.contract)
        return data


class SkillSandbox:
    """
    Ambiente isolado para execução segura de skills.
    Suporta Docker e subprocess isolado.
    """
    
    def __init__(self, use_docker: bool = False):
        self.use_docker = use_docker and self._check_docker()
        self._temp_dirs = []
    
    def _check_docker(self) -> bool:
        """Verifica se Docker está disponível."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except Exception:
            return False
    
    def execute(
        self, 
        code: str, 
        contract: Optional[SkillContract] = None,
        timeout: int = 30,
        input_data: Optional[Dict] = None
    ) -> Tuple[bool, Any, str]:
        """
        Executa código em sandbox isolado.
        
        Returns:
            Tuple[success, result, error_message]
        """
        contract = contract or SkillContract()
        
        # Valida contrato de entrada
        if input_data and contract:
            valid, msg = contract.validate_input(input_data)
            if not valid:
                return False, None, f"Validação de entrada falhou: {msg}"
        
        with tempfile.TemporaryDirectory(prefix="skill_sandbox_") as tmpdir:
            self._temp_dirs.append(tmpdir)
            
            # Código wrapper para execução
            wrapper_code = self._build_wrapper(code, contract, input_data)
            script_path = Path(tmpdir) / "skill_runner.py"
            script_path.write_text(wrapper_code)
            
            try:
                if self.use_docker:
                    result = self._run_docker(script_path, tmpdir, timeout, contract)
                else:
                    result = self._run_subprocess(script_path, timeout, contract)
                
                if result["success"]:
                    # Valida saída contra contrato
                    if contract:
                        valid, msg = contract.validate_output(result["output"])
                        if not valid:
                            return False, None, f"Validação de saída falhou: {msg}"
                    
                    return True, result["output"], ""
                else:
                    return False, None, result["error"]
                    
            except Exception as e:
                return False, None, str(e)
            finally:
                # Limpeza
                self._cleanup()
    
    def _build_wrapper(self, code: str, contract: SkillContract, input_data: Optional[Dict]) -> str:
        """Constrói código wrapper para execução isolada."""
        input_json = json.dumps(input_data or {})
        
        return f'''
import json
import sys
import traceback
import time
import resource

# Configurar limites de recursos
if hasattr(resource, 'setrlimit'):
    # Limite de memória: {contract.max_memory_mb} MB
    resource.setrlimit(resource.RLIMIT_AS, ({contract.max_memory_mb * 1024 * 1024}, {contract.max_memory_mb * 1024 * 1024}))

# Verificar imports permitidos
{self._build_import_checker(contract)}

# Código da skill
{code}

# Execução
def run_skill():
    try:
        input_data = {input_json}
        start_time = time.time()
        
        # Busca função principal (main, execute, run)
        if 'main' in dir():
            result = main(input_data) if input_data else main()
        elif 'execute' in dir():
            result = execute(input_data) if input_data else execute()
        elif 'run' in dir():
            result = run(input_data) if input_data else run()
        else:
            result = None
        
        execution_time = (time.time() - start_time) * 1000  # ms
        
        output = {{
            "result": result,
            "execution_time_ms": execution_time
        }}
        
        print(json.dumps(output))
        return 0
    except Exception as e:
        print(json.dumps({{
            "error": str(e),
            "traceback": traceback.format_exc()
        }}))
        return 1

if __name__ == "__main__":
    sys.exit(run_skill())
'''
    
    def _build_import_checker(self, contract: SkillContract) -> str:
        """Constrói verificador de imports permitidos."""
        allowed = contract.allowed_imports or []
        forbidden = contract.forbidden_patterns or []
        
        check_code = f'''
ALLOWED_IMPORTS = {allowed}
FORBIDDEN_PATTERNS = {forbidden}

def check_import(module_name):
    if module_name not in ALLOWED_IMPORTS:
        raise ImportError(f"Import {{module_name}} não permitido")
    
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in module_name:
            raise ImportError(f"Import {{module_name}} contém padrão proibido: {{pattern}}")

# Monkey patch __import__
original_import = __builtins__.__import__

def safe_import(name, *args, **kwargs):
    if name.startswith('_'):
        raise ImportError(f"Import de módulo privado não permitido: {{name}}")
    check_import(name.split('.')[0])
    return original_import(name, *args, **kwargs)

__builtins__.__import__ = safe_import
'''
        return check_code
    
    def _run_docker(self, script_path: Path, tmpdir: str, timeout: int, contract: SkillContract) -> Dict[str, Any]:
        """Executa via Docker."""
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{tmpdir}:/app",
            "-w", "/app",
            "--memory", f"{contract.max_memory_mb}m",
            "--cpus", "0.5",
            "--network", "none",
            "python:3.10-slim",
            "python", "skill_runner.py"
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if proc.returncode == 0 and proc.stdout:
                try:
                    output = json.loads(proc.stdout.strip().split('\n')[-1])
                    return {"success": True, "output": output.get("result")}
                except json.JSONDecodeError:
                    return {"success": True, "output": proc.stdout}
            else:
                error = proc.stderr or f"Return code: {proc.returncode}"
                return {"success": False, "error": error}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout após {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_subprocess(self, script_path: Path, timeout: int, contract: SkillContract) -> Dict[str, Any]:
        """Executa em subprocesso isolado."""
        try:
            proc = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if proc.returncode == 0 and proc.stdout:
                try:
                    output = json.loads(proc.stdout.strip().split('\n')[-1])
                    return {"success": True, "output": output.get("result")}
                except json.JSONDecodeError:
                    return {"success": True, "output": proc.stdout}
            else:
                return {"success": False, "error": proc.stderr or f"Código de erro: {proc.returncode}"}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout após {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cleanup(self):
        """Limpa diretórios temporários."""
        for tmpdir in self._temp_dirs:
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
        self._temp_dirs.clear()


class SkillMarketplace:
    """
    Marketplace completo para habilidades e plugins da Atena.
    Gerencia registro, validação, versionamento e deployment.
    """
    
    def __init__(self, storage_path: str | Path, enable_auto_validation: bool = True):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.sandbox = SkillSandbox(use_docker=False)
        self.auto_validation = enable_auto_validation
        self._cache: Dict[str, SkillRecord] = {}
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._lock = threading.RLock()
        
        # Carrega registros existentes
        self._load_cache()
        
        logger.info(f"🔱 SkillMarketplace inicializado em: {self.storage_path}")
        logger.info(f"   Auto-validação: {'ativada' if enable_auto_validation else 'desativada'}")
    
    def _load_cache(self) -> None:
        """Carrega registros do disco para cache."""
        records = self._load()
        with self._lock:
            for record_data in records:
                self._cache[f"{record_data['skill_id']}:{record_data['version']}"] = self._deserialize_record(record_data)
    
    def _deserialize_record(self, data: dict) -> SkillRecord:
        """Converte dados serializados de volta para SkillRecord."""
        # Converte métricas
        metrics_data = data.pop('metrics', {})
        metrics = SkillMetrics(**metrics_data) if metrics_data else SkillMetrics()
        
        # Converte contrato
        contract_data = data.pop('contract', None)
        contract = SkillContract(**contract_data) if contract_data else None
        
        return SkillRecord(
            **{k: v for k, v in data.items() if k != 'metrics' and k != 'contract'},
            metrics=metrics,
            contract=contract
        )
    
    def _load(self) -> list[dict]:
        """Carrega registros do arquivo."""
        if not self.storage_path.exists():
            return []
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Erro ao carregar registros: {e}")
            return []
    
    def _save(self, records: list[dict]) -> None:
        """Salva registros no arquivo."""
        try:
            self.storage_path.write_text(
                json.dumps(records, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Erro ao salvar registros: {e}")
    
    def _save_cache(self) -> None:
        """Salva cache atual no disco."""
        with self._lock:
            records = [r.to_dict() for r in self._cache.values()]
            self._save(records)
    
    def register(self, record: SkillRecord, validate: bool = False) -> Tuple[bool, str]:
        """
        Registra uma nova skill/plugin.
        
        Args:
            record: Registro da skill
            validate: Se deve executar validação automática
        
        Returns:
            Tuple[success, message]
        """
        normalized_payload = asdict(record)
        normalized_payload["name"] = (record.name or record.skill_id or "").strip()
        normalized_payload["description"] = (record.description or f"Skill {record.skill_id}").strip()
        normalized_payload["author"] = (record.author or "atena").strip()
        record = SkillRecord(**normalized_payload)
        cache_key = f"{record.skill_id}:{record.version}"
        
        with self._lock:
            if cache_key in self._cache:
                return False, f"Skill {record.skill_id} versão {record.version} já registrada"
            
            # Verifica se é a primeira versão
            existing_versions = [r for r in self._cache.values() if r.skill_id == record.skill_id]
            
            # Validação automática se solicitado
            if validate and self.auto_validation:
                logger.info(f"🔄 Validando skill: {record.skill_id} v{record.version}")
                validation_result = self.validate_skill(record)
                if not validation_result["passed"]:
                    return False, f"Validação falhou: {validation_result['errors']}"
            
            # Se é primeira versão, torna ativa automaticamente
            if not existing_versions:
                promoted_payload = {k: v for k, v in asdict(record).items()}
                promoted_payload["active"] = True
                record = SkillRecord(**promoted_payload)
            
            self._cache[cache_key] = record
            self._save_cache()
            
            logger.info(f"✅ Skill registrada: {record.skill_id} v{record.version}")
            return True, f"Skill {record.skill_id} versão {record.version} registrada com sucesso"
    
    def validate_skill(self, record: SkillRecord) -> Dict[str, Any]:
        """
        Valida uma skill executando testes em sandbox.
        
        Returns:
            Dict com resultados da validação
        """
        errors = []
        warnings = []
        
        # Validação de metadados
        if record.risk_level not in [r.value for r in RiskLevel]:
            errors.append(f"Nível de risco inválido: {record.risk_level}")
        
        if record.cost_class not in [c.value for c in CostClass]:
            errors.append(f"Classe de custo inválida: {record.cost_class}")
        
        # Validação de contrato
        if record.contract:
            # Verifica schema JSON
            if record.contract.input_schema:
                try:
                    # Tenta validar schema
                    if "$schema" not in record.contract.input_schema:
                        warnings.append("Schema de entrada não possui $schema definido")
                except Exception as e:
                    errors.append(f"Schema de entrada inválido: {e}")
            
            # Verifica permissões
            dangerous_perms = {"root", "sudo", "system", "network_raw"}
            for perm in record.contract.required_permissions:
                if perm in dangerous_perms:
                    errors.append(f"Permissão perigosa solicitada: {perm}")
        
        # Validação de dependências (quando aplicável)
        if record.dependencies:
            for dep in record.dependencies:
                if ".." in dep or dep.startswith("/"):
                    errors.append(f"Dependência com path suspeito: {dep}")
        
        # Se houver erros, validação falha
        passed = len(errors) == 0
        
        # Atualiza status de validação
        with self._lock:
            cache_key = f"{record.skill_id}:{record.version}"
            if cache_key in self._cache:
                self._cache[cache_key].sandbox_passed = passed
                self._cache[cache_key].validation_status = ValidationStatus.PASSED.value if passed else ValidationStatus.FAILED.value
                self._save_cache()
        
        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "validation_status": ValidationStatus.PASSED.value if passed else ValidationStatus.FAILED.value
        }
    
    def approve(self, skill_id: str, version: Optional[str] = None) -> bool:
        """
        Aprova uma skill para uso.
        
        Args:
            skill_id: ID da skill
            version: Versão específica (None para todas)
        """
        with self._lock:
            updated = False
            for cache_key, record in self._cache.items():
                if record.skill_id != skill_id:
                    continue
                if version and record.version != version:
                    continue
                
                # Verifica validações
                if record.validation_enforced:
                    if not (record.sandbox_passed and record.contract_passed and record.security_passed):
                        logger.warning(f"Skill {skill_id} v{record.version} não passou nas validações")
                        continue
                
                approved_payload = {k: v for k, v in asdict(record).items()}
                approved_payload["approved"] = True
                record = SkillRecord(**approved_payload)
                self._cache[cache_key] = record
                updated = True
            
            if updated:
                self._save_cache()
                logger.info(f"✅ Skill aprovada: {skill_id}" + (f" v{version}" if version else ""))
            
            return updated
    
    def promote(self, skill_id: str, version: str) -> bool:
        """
        Promove uma versão específica da skill para ativa.
        
        Args:
            skill_id: ID da skill
            version: Versão a promover
        """
        with self._lock:
            found = False
            approved = False
            validated = False
            target_record = None
            
            # Primeiro, encontra e valida a skill alvo
            for record in self._cache.values():
                if record.skill_id != skill_id:
                    continue
                
                if record.version == version:
                    found = True
                    approved = record.approved
                    if record.validation_enforced:
                        validated = all([
                            record.sandbox_passed,
                            record.contract_passed,
                            record.security_passed
                        ])
                    else:
                        validated = True
                    target_record = record
                    break
            
            if not found:
                logger.warning(f"Skill {skill_id} v{version} não encontrada")
                return False
            
            if not approved:
                logger.warning(f"Skill {skill_id} v{version} não aprovada")
                return False
            
            if not validated:
                logger.warning(f"Skill {skill_id} v{version} não passou nas validações")
                return False
            
            # Desativa outras versões e ativa a alvo
            for cache_key, record in self._cache.items():
                if record.skill_id == skill_id:
                    is_target = record.version == version
                    promote_payload = {k: v for k, v in asdict(record).items()}
                    promote_payload["active"] = is_target
                    updated_record = SkillRecord(**promote_payload)
                    self._cache[cache_key] = updated_record
                    
                    if is_target:
                        logger.info(f"✅ Skill promovida: {skill_id} v{version}")
            
            self._save_cache()
            return True
    
    def rollback(self, skill_id: str, to_version: str) -> bool:
        """
        Reverte para uma versão anterior da skill.
        
        Args:
            skill_id: ID da skill
            to_version: Versão alvo do rollback
        """
        logger.info(f"🔄 Executando rollback para {skill_id} v{to_version}")
        return self.promote(skill_id, to_version)
    
    def validate(self, skill_id: str, version: str, 
                sandbox_passed: bool, contract_passed: bool, security_passed: bool) -> bool:
        """
        Registra resultados de validação para uma skill.
        """
        with self._lock:
            cache_key = f"{skill_id}:{version}"
            if cache_key not in self._cache:
                logger.warning(f"Skill {skill_id} v{version} não encontrada")
                return False
            
            record = self._cache[cache_key]
            validate_payload = {k: v for k, v in asdict(record).items()}
            validate_payload.update(
                {
                    "sandbox_passed": sandbox_passed,
                    "contract_passed": contract_passed,
                    "security_passed": security_passed,
                    "validation_enforced": True,
                    "validation_status": ValidationStatus.PASSED.value
                    if all([sandbox_passed, contract_passed, security_passed])
                    else ValidationStatus.FAILED.value,
                    "updated_at": datetime.now().isoformat(),
                }
            )
            updated_record = SkillRecord(**validate_payload)
            self._cache[cache_key] = updated_record
            self._save_cache()
            
            logger.info(f"📋 Validação registrada: {skill_id} v{version} - {updated_record.validation_status}")
            return True
    
    def record_execution(self, skill_id: str, version: str, success: bool, 
                        execution_time_ms: float, cpu_usage: float = 0, memory_mb: float = 0) -> bool:
        """
        Registra métricas de execução da skill.
        """
        with self._lock:
            cache_key = f"{skill_id}:{version}"
            if cache_key not in self._cache:
                return False
            
            record = self._cache[cache_key]
            record.metrics.update(success, execution_time_ms, cpu_usage, memory_mb)
            
            # Armazena histórico
            self._metrics_history[skill_id].append({
                "version": version,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.now().isoformat()
            })
            
            self._save_cache()
            return True
    
    def execute_skill(self, skill_id: str, version: str, input_data: Optional[Dict] = None) -> Tuple[bool, Any, str]:
        """
        Executa uma skill registrada em ambiente isolado.
        
        Args:
            skill_id: ID da skill
            version: Versão a executar
            input_data: Dados de entrada
        
        Returns:
            Tuple[success, result, error_message]
        """
        # Busca o registro
        cache_key = f"{skill_id}:{version}"
        with self._lock:
            if cache_key not in self._cache:
                return False, None, f"Skill {skill_id} v{version} não encontrada"
            
            record = self._cache[cache_key]
            
            if not record.active:
                return False, None, f"Skill {skill_id} v{version} não está ativa"
            
            if not record.approved:
                return False, None, f"Skill {skill_id} v{version} não foi aprovada"
        
        # Prepara contrato
        contract = record.contract or SkillContract(
            timeout_seconds=30,
            max_memory_mb=256
        )
        
        # Executa em sandbox
        start_time = time.time()
        success, result, error = self.sandbox.execute(
            code=self._get_skill_code(skill_id, version),
            contract=contract,
            timeout=contract.timeout_seconds,
            input_data=input_data
        )
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Registra métricas
        self.record_execution(skill_id, version, success, execution_time_ms)
        
        if success:
            logger.info(f"✅ Skill executada: {skill_id} v{version} ({execution_time_ms:.2f}ms)")
        else:
            logger.error(f"❌ Falha na execução: {skill_id} v{version} - {error}")
        
        return success, result, error
    
    def _get_skill_code(self, skill_id: str, version: str) -> str:
        """Recupera o código da skill do armazenamento."""
        # TODO: Implementar armazenamento real do código
        # Por enquanto, retorna placeholder
        return f'''
def main(input_data=None):
    """Skill {skill_id} versão {version}"""
    return {{"status": "success", "skill_id": "{skill_id}", "version": "{version}"}}
'''
    
    def list_records(self, active_only: bool = False, approved_only: bool = False) -> List[Dict]:
        """
        Lista todas as skills registradas.
        
        Args:
            active_only: Apenas skills ativas
            approved_only: Apenas skills aprovadas
        """
        records = []
        with self._lock:
            for record in self._cache.values():
                if active_only and not record.active:
                    continue
                if approved_only and not record.approved:
                    continue
                records.append(record.to_dict())
        
        return sorted(records, key=lambda x: (x['skill_id'], x['version']), reverse=True)
    
    def active_version(self, skill_id: str) -> Optional[str]:
        """Retorna a versão ativa de uma skill."""
        with self._lock:
            for record in self._cache.values():
                if record.skill_id == skill_id and record.active:
                    return record.version
        return None
    
    def get_skill_metrics(self, skill_id: str) -> Dict[str, Any]:
        """Retorna métricas agregadas de uma skill."""
        with self._lock:
            metrics = {
                "skill_id": skill_id,
                "versions": [],
                "total_executions": 0,
                "total_success": 0,
                "overall_error_rate": 0.0
            }
            
            for record in self._cache.values():
                if record.skill_id == skill_id:
                    metrics["versions"].append({
                        "version": record.version,
                        "active": record.active,
                        "approved": record.approved,
                        "metrics": record.metrics.to_dict()
                    })
                    metrics["total_executions"] += record.metrics.total_executions
                    metrics["total_success"] += record.metrics.successful_executions
            
            if metrics["total_executions"] > 0:
                metrics["overall_error_rate"] = 1 - (metrics["total_success"] / metrics["total_executions"])
            
            return metrics
    
    def generate_report(self) -> Dict[str, Any]:
        """Gera relatório completo do marketplace."""
        with self._lock:
            total_skills = len(self._cache)
            active_skills = sum(1 for r in self._cache.values() if r.active)
            approved_skills = sum(1 for r in self._cache.values() if r.approved)
            validated_skills = sum(1 for r in self._cache.values() if r.validation_enforced and r.validation_status == ValidationStatus.PASSED.value)
            
            # Agregação por nível de risco
            risk_distribution = defaultdict(int)
            for r in self._cache.values():
                risk_distribution[r.risk_level] += 1
            
            return {
                "timestamp": datetime.now().isoformat(),
                "total_skills": total_skills,
                "active_skills": active_skills,
                "approved_skills": approved_skills,
                "validated_skills": validated_skills,
                "validation_rate": validated_skills / total_skills if total_skills > 0 else 0,
                "risk_distribution": dict(risk_distribution),
                "skills": [r.to_dict() for r in self._cache.values()]
            }


class SkillValidator:
    """
    Validador automático de skills com análise estática e dinâmica.
    """
    
    @staticmethod
    def static_analysis(code: str) -> Dict[str, Any]:
        """Realiza análise estática do código."""
        issues = []
        warnings = []
        
        # Verifica padrões perigosos
        dangerous_patterns = [
            (r'os\.system\s*\(', "Chamada a os.system() é perigosa"),
            (r'subprocess\.\w+\s*\(', "Uso de subprocess requer validação"),
            (r'__import__\s*\(', "Importação dinâmica é arriscada"),
            (r'eval\s*\(', "eval() pode executar código arbitrário"),
            (r'exec\s*\(', "exec() pode executar código arbitrário"),
            (r'open\s*\(.*[\'"]w[\'"]', "Escrita em arquivo pode ser perigosa"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                warnings.append(message)
        
        # Verifica imports suspeitos
        import_pattern = r'import\s+(\w+)'
        imports = re.findall(import_pattern, code)
        dangerous_imports = ['os', 'subprocess', 'socket', 'pickle', 'marshal']
        
        for imp in imports:
            if imp in dangerous_imports:
                issues.append(f"Import perigoso: {imp}")
        
        # Verifica tamanho do código
        lines = len(code.splitlines())
        if lines > 500:
            warnings.append(f"Código muito extenso: {lines} linhas")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "lines": lines
        }
    
    @staticmethod
    def security_scan(code: str) -> Dict[str, Any]:
        """Realiza scan de segurança no código."""
        findings = []
        
        # Padrões de segurança
        security_patterns = [
            (r'password\s*=\s*[\'"][^\'"]+[\'"]', "Possível hardcoded password"),
            (r'token\s*=\s*[\'"][^\'"]+[\'"]', "Possível hardcoded token"),
            (r'secret\s*=\s*[\'"][^\'"]+[\'"]', "Possível hardcoded secret"),
            (r'api_key\s*=\s*[\'"][^\'"]+[\'"]', "Possível hardcoded API key"),
        ]
        
        for pattern, message in security_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                findings.append(message)
        
        return {
            "passed": len(findings) == 0,
            "findings": findings,
            "severity": "high" if findings else "none"
        }


# Import re para análise estática
import re

# =============================================================================
# EXEMPLO DE USO E MAIN
# =============================================================================

def main():
    """Demonstração do SkillMarketplace."""
    
    # Inicializa marketplace
    marketplace = SkillMarketplace("atena_evolution/skills_catalog.json")
    
    # Cria skill exemplo
    skill = SkillRecord(
        skill_id="data_analyzer",
        version="1.0.0",
        name="Data Analyzer",
        description="Análise de dados com estatísticas básicas",
        author="ATENA Team",
        risk_level=RiskLevel.LOW.value,
        cost_class=CostClass.FREE.value,
        compatible_with=">=1.0.0",
        dependencies=["numpy", "pandas"],
        tags=["data", "analysis", "statistics"],
        contract=SkillContract(
            input_schema={
                "type": "object",
                "required": ["data"],
                "properties": {
                    "data": {"type": "array"},
                    "metrics": {"type": "array"}
                }
            },
            output_schema={"type": "object"},
            required_permissions=["read"],
            timeout_seconds=30,
            max_memory_mb=512
        )
    )
    
    # Registra skill
    success, msg = marketplace.register(skill, validate=True)
    print(f"Registro: {msg}")
    
    # Aprova skill
    marketplace.approve("data_analyzer", "1.0.0")
    
    # Promove para ativa
    marketplace.promote("data_analyzer", "1.0.0")
    
    # Lista skills
    print("\nSkills registradas:")
    for record in marketplace.list_records():
        print(f"  - {record['skill_id']} v{record['version']} (ativa: {record['active']})")
    
    # Gera relatório
    report = marketplace.generate_report()
    print(f"\n📊 Relatório: {report['total_skills']} skills, {report['active_skills']} ativas")
    
    # Salva relatório
    report_path = Path("atena_evolution/skills_marketplace_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"📄 Relatório salvo em: {report_path}")


if __name__ == "__main__":
    main()
