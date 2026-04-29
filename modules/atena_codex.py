"""Módulo AtenaCodex: orquestra diagnóstico e utilidades da ATENA."""

from __future__ import annotations

import importlib
import json
import logging
import platform
import re
import subprocess
import sys
import threading
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Suporte para importação resiliente
try:
    from .AtenaSysAware import AtenaSysAware
except (ImportError, ValueError):
    try:
        from AtenaSysAware import AtenaSysAware
    except ImportError:
        # Fallback para quando executado de fora do pacote
        sys.path.append(os.path.dirname(__file__))
        try:
            from AtenaSysAware import AtenaSysAware
        except ImportError:
            # Mock básico se tudo falhar
            class AtenaSysAware:
                def get_profile(self): return {"info": "SysAware não disponível"}

logger = logging.getLogger("atena.codex")


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


class AtenaCodex:
    """Camada utilitária de operação/diagnóstico para a ATENA."""

    # Módulos obrigatórios para o núcleo operacional da ATENA.
    ESSENTIAL_MODULES = [
        "requests",
        "astor",
    ]

    # Stack avançada recomendada para recursos de alto desempenho.
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
    ]

    OPTIONAL_MODULES = [
        "matplotlib",
        "seaborn",
        "sklearn",
        "dotenv",
        "tqdm",
        "colorama",
        "requests",
        "yaml",
    ]
    SOFT_DEPENDENCY_MODULES = {
        "numpy",
        "pandas",
        "torch",
        "transformers",
        "chromadb",
        "faiss",
        "networkx",
    }
    RUNTIME_IMPORT_TO_PIP = {
        "psutil": "psutil",
        "numpy": "numpy",
        "requests": "requests",
        "rich": "rich",
        "aiosqlite": "aiosqlite",
    }

    def __init__(self, root_path: Optional[str] = None):
        self.sysaware = AtenaSysAware()
        self._lock = threading.RLock()
        # Define a raiz do projeto para comandos relativos
        if root_path:
            self.root_path = Path(root_path)
        else:
            # Assume que estamos em /modules/ e a raiz é um nível acima
            self.root_path = Path(__file__).parent.parent

    def environment_snapshot(self) -> Dict:
        """Retorna snapshot básico do host e runtime."""
        with self._lock:
            try:
                profile = dict(self.sysaware.get_profile())
            except Exception:
                profile = {"error": "Falha ao obter perfil do SysAware"}
                
            profile.update(
                {
                    "python_executable": sys.executable,
                    "platform": platform.platform(),
                    "checked_at": datetime.utcnow().isoformat() + "Z",
                    "root_path": str(self.root_path.absolute()),
                }
            )
            return profile

    def check_python_modules(self) -> Dict[str, List[Dict]]:
        """Valida módulos essenciais e opcionais de runtime."""
        essential = [asdict(self._check_single_module(name)) for name in self.ESSENTIAL_MODULES]
        advanced = [asdict(self._check_single_module(name)) for name in self.ADVANCED_STACK_MODULES]
        optional = [asdict(self._check_single_module(name)) for name in self.OPTIONAL_MODULES]
        return {"essential": essential, "advanced": advanced, "optional": optional}

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict]:
        """Executa comandos seguros de validação local na raiz do projeto."""
        # Lista de arquivos para verificar compilação, se existirem
        targets = ["core/main.py", "core/neural_api.py", "core/neural_dashboard.py", "modules"]
        existing_targets = [t for t in targets if (self.root_path / t).exists()]
        
        commands = []
        if existing_targets:
            commands.append([sys.executable, "-m", "compileall", "-q"] + existing_targets)
        
        # Validação de import leve do launcher (evita acoplamento com stack científica pesada).
        commands.append(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.append('core'); import atena_launcher; print('Launcher Import: OK')",
            ]
        )
        # Validação opcional do core.main com classificação de soft-fail para
        # ambientes sem stack científica pesada.
        commands.append(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.append('core'); import main; print('Core Import: OK')",
            ]
        )
        
        out = []
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
                if "import main" in cmd_str and result.returncode != 0:
                    missing_soft_dep = any(
                        f"No module named '{dep}'" in stderr for dep in self.SOFT_DEPENDENCY_MODULES
                    )
                    if missing_soft_dep:
                        soft_failed = True
                        soft_reason = "Dependência avançada ausente para import opcional de core.main"

                out.append(
                    {
                        "command": cmd_str,
                        "returncode": result.returncode,
                        "stdout": result.stdout.strip(),
                        "stderr": stderr,
                        "soft_failed": soft_failed,
                        "soft_reason": soft_reason,
                    }
                )
            except subprocess.TimeoutExpired:
                out.append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"timeout>{timeout_seconds}s",
                        "soft_failed": False,
                        "soft_reason": "",
                    }
                )
            except Exception as e:
                out.append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -2,
                        "stdout": "",
                        "stderr": str(e),
                        "soft_failed": False,
                        "soft_reason": "",
                    }
                )
        return out

    def run_full_diagnostic(self, include_commands: bool = True, timeout_seconds: int = 120) -> Dict:
        """Executa diagnóstico completo em uma chamada única."""
        snapshot = self.environment_snapshot()
        module_checks = self.check_python_modules()
        command_checks = self.run_local_commands(timeout_seconds=timeout_seconds) if include_commands else []

        essentials_ok = all(item["ok"] for item in module_checks["essential"])
        # Consideramos OK se os comandos que rodaram retornaram 0
        commands_ok = (
            all(item["returncode"] == 0 or item.get("soft_failed", False) for item in command_checks)
            if command_checks
            else True
        )

        status = "ok" if (essentials_ok and commands_ok) else "partial"
        diagnostic = {
            "status": status,
            "snapshot": snapshot,
            "modules": module_checks,
            "commands": command_checks,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info("[AtenaCodex] diagnóstico concluído com status=%s", status)
        return diagnostic

    def run_advanced_autopilot(
        self,
        objective: str = "Elevar confiabilidade do runtime da ATENA",
        include_commands: bool = True,
        timeout_seconds: int = 120,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo avançado orientado por objetivo usando AtenaCodex.

        Fluxo:
        1) Diagnóstico do ambiente
        2) Priorização de riscos (módulos essenciais faltantes + comandos que falharam)
        3) Geração de plano de ação em etapas
        4) Persistência de relatório no diretório atena_evolution/
        """
        diagnostic = self.run_full_diagnostic(
            include_commands=include_commands,
            timeout_seconds=timeout_seconds,
        )

        essential_missing = [
            item["name"]
            for item in diagnostic["modules"]["essential"]
            if not item.get("ok", False)
        ]
        advanced_missing = [
            item["name"]
            for item in diagnostic["modules"].get("advanced", [])
            if not item.get("ok", False)
        ]
        command_failures = [
            item
            for item in diagnostic.get("commands", [])
            if item.get("returncode", 1) != 0 and not item.get("soft_failed", False)
        ]
        soft_command_warnings = [
            item
            for item in diagnostic.get("commands", [])
            if item.get("soft_failed", False)
        ]

        risk_score = min(
            1.0,
            (len(essential_missing) * 0.25)
            + (len(command_failures) * 0.20)
            + (len(advanced_missing) * 0.03),
        )
        confidence = max(0.0, 1.0 - risk_score)

        action_plan: List[Dict[str, Any]] = []
        if essential_missing:
            action_plan.append(
                {
                    "priority": "P0",
                    "title": "Restaurar módulos essenciais faltantes",
                    "details": f"Instalar/validar: {', '.join(essential_missing)}",
                }
            )
        if command_failures:
            action_plan.append(
                {
                    "priority": "P0",
                    "title": "Corrigir comandos locais com falha",
                    "details": [f["command"] for f in command_failures],
                }
            )
        if advanced_missing:
            action_plan.append(
                {
                    "priority": "P1",
                    "title": "Completar stack avançada de IA",
                    "details": f"Instalar gradualmente: {', '.join(advanced_missing)}",
                }
            )
        if soft_command_warnings:
            action_plan.append(
                {
                    "priority": "P1",
                    "title": "Eliminar soft-fails de import avançado",
                    "details": [w.get("soft_reason", "soft-fail detectado") for w in soft_command_warnings],
                }
            )
        if not action_plan:
            action_plan.append(
                {
                    "priority": "P1",
                    "title": "Ambiente estável",
                    "details": "Prosseguir para missões de evolução e benchmarks.",
                }
            )

        result = {
            "objective": objective,
            "status": diagnostic["status"],
            "risk_score": round(risk_score, 3),
            "confidence": round(confidence, 3),
            "missing_essential_modules": essential_missing,
            "missing_advanced_modules": advanced_missing,
            "failing_commands_count": len(command_failures),
            "soft_warning_commands_count": len(soft_command_warnings),
            "action_plan": action_plan,
            "diagnostic": diagnostic,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        evolution_dir = self.root_path / "atena_evolution"
        evolution_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = evolution_dir / f"codex_autopilot_report_{timestamp}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        result["report_path"] = str(report_path)
        logger.info("[AtenaCodex] autopilot avançado concluído. report=%s", report_path)
        return result

    def run_module_smoke_suite(self, timeout_seconds: int = 25) -> Dict[str, Any]:
        """
        Executa smoke tests dos módulos da ATENA um por um em subprocessos isolados.

        Também inclui verificações extras para:
        - conectividade básica de internet
        - import do módulo de busca web
        - import do módulo de automação de computador
        """
        modules_dir = self.root_path / "modules"
        module_targets = sorted(
            p.stem
            for p in modules_dir.glob("*.py")
            if p.name != "__init__.py"
        )

        results: List[Dict[str, Any]] = []
        for module_name in module_targets:
            cmd = [
                sys.executable,
                "-c",
                f"import importlib; importlib.import_module('modules.{module_name}'); print('OK:{module_name}')",
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
                results.append(
                    {
                        "type": "module_import",
                        "target": f"modules.{module_name}",
                        "ok": proc.returncode == 0,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip(),
                        "stderr": proc.stderr.strip(),
                    }
                )
            except subprocess.TimeoutExpired:
                results.append(
                    {
                        "type": "module_import",
                        "target": f"modules.{module_name}",
                        "ok": False,
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"timeout>{timeout_seconds}s",
                    }
                )

        extra_checks = [
            {
                "name": "internet_connectivity",
                "cmd": [
                    sys.executable,
                    "-c",
                    "import urllib.request; urllib.request.urlopen('https://www.google.com', timeout=8); print('internet:ok')",
                ],
            },
            {
                "name": "internet_search_module_import",
                "cmd": [
                    sys.executable,
                    "-c",
                    "import atena_google_search; print('atena_google_search:ok')",
                ],
            },
            {
                "name": "computer_control_module_import",
                "cmd": [
                    sys.executable,
                    "-c",
                    "import importlib; importlib.import_module('modules.computer_actuator'); print('computer_actuator:ok')",
                ],
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
                results.append(
                    {
                        "type": "extra_check",
                        "target": check["name"],
                        "ok": proc.returncode == 0,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip(),
                        "stderr": proc.stderr.strip(),
                    }
                )
            except subprocess.TimeoutExpired:
                results.append(
                    {
                        "type": "extra_check",
                        "target": check["name"],
                        "ok": False,
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"timeout>{timeout_seconds}s",
                    }
                )

        passed = sum(1 for r in results if r["ok"])
        total = len(results)
        failed = total - passed

        summary = {
            "status": "ok" if failed == 0 else "partial",
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results": results,
        }

        evolution_dir = self.root_path / "atena_evolution"
        evolution_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = evolution_dir / f"module_smoke_suite_{timestamp}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        summary["report_path"] = str(report_path)
        return summary

    @staticmethod
    def _extract_missing_import_from_stderr(stderr: str) -> Optional[str]:
        if not stderr:
            return None
        match = re.search(r"No module named '([^']+)'", stderr)
        return match.group(1) if match else None

    def _ensure_runtime_dependency(self, import_name: str) -> bool:
        package_name = self.RUNTIME_IMPORT_TO_PIP.get(import_name)
        if not package_name:
            return False
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                cwd=str(self.root_path),
            )
            return proc.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _check_single_module(module_name: str) -> CheckResult:
        # Mapeamento de nomes de pacotes pip para nomes de importação
        import_map = {
            "sklearn": "sklearn",
            "dotenv": "dotenv",
            "yaml": "yaml",
            "faiss": "faiss",
            "chromadb": "chromadb"
        }
        
        actual_import = import_map.get(module_name, module_name)
        
        try:
            module = importlib.import_module(actual_import)
            version = getattr(module, "__version__", "desconhecida")
            return CheckResult(module_name, True, f"versão={version}")
        except Exception as exc:
            return CheckResult(module_name, False, str(exc))


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    # Tenta detectar a raiz do projeto se estiver rodando dentro de modules/
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = AtenaCodex(root_path=root).run_full_diagnostic()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
