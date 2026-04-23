import os
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from .base import BaseActuator

logger = logging.getLogger(__name__)

class FileActuator(BaseActuator):
    """Manipulação segura e resiliente de arquivos e diretórios."""
    
    def __init__(self, sysaware=None, safe_mode=True):
        self.safe_mode = safe_mode
        # Caminhos protegidos para evitar danos ao sistema
        self._protected_paths = {
            Path.home().resolve(), 
            Path("/").resolve(), 
            Path("/etc").resolve(), 
            Path("/usr").resolve(),
            Path("/var").resolve(),
            Path("/boot").resolve()
        } if safe_mode else set()
        super().__init__(sysaware)

    def _check_dependencies(self):
        """Sem dependências externas necessárias."""
        pass

    def _is_safe_path(self, path: Path) -> bool:
        """Verifica se o caminho é seguro para manipulação."""
        if not self.safe_mode:
            return True
        try:
            path = path.resolve()
            # Impede manipulação direta de caminhos do sistema
            for protected in self._protected_paths:
                if path == protected or protected in path.parents:
                    # Exceção: permitir escrita dentro da pasta de evolução da Atena
                    atena_dir = Path("./atena_evolution").resolve()
                    if atena_dir in path.parents or path == atena_dir:
                        return True
                    return False
            return True
        except Exception:
            return False

    def read_file(self, filepath: str) -> Optional[str]:
        """Lê conteúdo de um arquivo com tratamento de erros."""
        try:
            path = Path(filepath).resolve()
            if not self._is_safe_path(path):
                logger.error(f"[FileActuator] Acesso negado: {path}")
                return None
            
            if not path.is_file():
                logger.warning(f"[FileActuator] Arquivo não encontrado: {path}")
                return None

            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"[FileActuator] Erro ao ler {filepath}: {e}")
            return None

    def write_file(self, filepath: str, content: str, mode='w') -> bool:
        """Escreve em um arquivo com criação automática de diretórios."""
        try:
            path = Path(filepath).resolve()
            if not self._is_safe_path(path):
                logger.error(f"[FileActuator] Escrita negada em caminho protegido: {path}")
                return False

            # Auto-correção: criar diretórios pais se não existirem
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
            
            self.log_action("write_file", {"path": str(path), "mode": mode})
            return True
        except Exception as e:
            logger.error(f"[FileActuator] Erro ao escrever em {filepath}: {e}")
            return False

    def delete_file(self, filepath: str) -> bool:
        """Remove um arquivo de forma segura."""
        try:
            path = Path(filepath).resolve()
            if not self._is_safe_path(path):
                logger.error(f"[FileActuator] Deleção negada: {path}")
                return False
            
            if path.exists():
                if path.is_file():
                    os.remove(path)
                elif path.is_dir():
                    shutil.rmtree(path)
                self.log_action("delete_file", {"path": str(path)})
                return True
            return False
        except Exception as e:
            logger.error(f"[FileActuator] Erro ao deletar {filepath}: {e}")
            return False

    def list_directory(self, directory: str = ".") -> List[str]:
        """Lista arquivos em um diretório de forma segura."""
        try:
            path = Path(directory).resolve()
            if not self._is_safe_path(path):
                return []
            if path.is_dir():
                return [str(f.name) for f in path.iterdir()]
            return []
        except Exception as e:
            logger.error(f"[FileActuator] Erro ao listar diretório {directory}: {e}")
            return []
