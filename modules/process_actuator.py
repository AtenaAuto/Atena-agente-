import subprocess
import psutil
import time
import signal
import logging
import os
from typing import List, Dict, Optional, Tuple, Union, Any
from pathlib import Path
from .base import BaseActuator

logger = logging.getLogger("atena.actuator.process")

class ProcessActuator(BaseActuator):
    """
    Atuador resiliente para gerenciamento de processos do sistema.
    Implementa auto-correção para falhas comuns e proteção de execução.
    """

    def __init__(self, command_whitelist: Optional[List[str]] = None):
        super().__init__()
        self.command_whitelist = command_whitelist
        self._check_dependencies()

    def _check_dependencies(self):
        """Verifica dependências e inicializa o ambiente."""
        try:
            import psutil
            logger.info(f"ProcessActuator inicializado com psutil {psutil.__version__}")
        except ImportError:
            logger.error("psutil não encontrado. Algumas funcionalidades serão limitadas.")

    def _is_command_allowed(self, command: Union[str, List[str]]) -> bool:
        """Verifica se o comando é permitido pela política de segurança."""
        if self.command_whitelist is None:
            return True
        cmd_str = command if isinstance(command, str) else command[0]
        base_cmd = Path(cmd_str).name
        return base_cmd in self.command_whitelist

    def run_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: Optional[float] = 60.0,
        input_data: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Union[str, Path]] = None
    ) -> Tuple[str, str, int]:
        """
        Executa um comando com tratamento automático de erros e timeout.
        """
        if not self._is_command_allowed(command):
            logger.error(f"Comando negado: {command}")
            return "", "Permission Denied by Whitelist", -1

        try:
            # Auto-correção: Garantir que o CWD existe
            if cwd and not Path(cwd).exists():
                logger.warning(f"CWD {cwd} não existe, criando diretório...")
                Path(cwd).mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_data,
                env=env or os.environ.copy(),
                cwd=str(cwd) if cwd else None
            )
            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout ao executar {command}")
            return e.stdout.decode() if e.stdout else "", "Timeout Expired", -1
        except Exception as e:
            logger.error(f"Erro inesperado ao executar comando: {e}")
            return "", str(e), -1

    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Encerra um processo de forma segura e resiliente."""
        try:
            if not psutil.pid_exists(pid):
                return True
            
            p = psutil.Process(pid)
            if force:
                p.kill()
            else:
                p.terminate()
                # Aguarda término gracioso
                _, alive = psutil.wait_procs([p], timeout=3)
                if alive:
                    p.kill()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            logger.error(f"Erro ao encerrar processo {pid}: {e}")
            return False

    def get_system_load(self) -> Dict[str, float]:
        """Retorna a carga atual do sistema para decisões de escalonamento."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
