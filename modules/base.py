import logging
import time
import functools
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger("atena.actuators")


def track_action(action_name: Optional[str] = None):
    """
    Decorator que registra automaticamente a execuo de um mtodo da classe BaseActuator.
    Registra o nome da ao, parmetros, tempo de execuo e excees.
    O mtodo deve estar em uma classe que tenha o mtodo `log_action`.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            act_name = action_name or func.__name__
            start = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start
                # Chama o mtodo da instncia corretamente
                self.log_action(
                    act_name,
                    {
                        "args": args,
                        "kwargs": kwargs,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "success",
                    },
                )
                return result
            except Exception as e:
                duration = time.time() - start
                self.log_action(
                    act_name,
                    {
                        "args": args,
                        "kwargs": kwargs,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "error",
                        "error": str(e),
                    },
                    level=logging.ERROR,
                )
                raise

        return wrapper

    return decorator


class BaseActuator(ABC):
    """
    Classe base abstrata para todos os atuadores da ATENA .

    Fornece funcionalidades comuns:
        - Verificao de dependncias (abstrato)
        - Logging estruturado com contexto
        - Rastreamento de aes (tempo, sucesso/erro)
        - Configurao opcional de histrico

    Atributos:
        sysaware: Instncia de SysAware (para acesso a contexto do sistema, opcional)
        history: Lista opcional para armazenar histrico de aes (se ativado)
    """

    def __init__(self, sysaware: Optional[Any] = None, enable_history: bool = False):
        """
        Inicializa o atuador.

        Args:
            sysaware: Instncia de SysAware (fornece contexto adicional, ex: sistema operacional, configuraes)
            enable_history: Se True, mantm um histrico interno das aes executadas.
        """
        self.sysaware = sysaware
        self.enable_history = enable_history
        self._action_history: list = [] if enable_history else None
        self._check_dependencies()
        logger.debug(
            f"{self.__class__.__name__} inicializado com sysaware={sysaware is not None}"
        )

    @abstractmethod
    def _check_dependencies(self) -> None:
        """
        Verifica se as dependncias necessrias para o atuador esto disponveis.

        Deve ser implementado por cada subclasse.
        Exemplo: verificar se bibliotecas (psutil, pyautogui) ou comandos (pactl) esto presentes.

        Raises:
            ImportError: Se alguma biblioteca obrigatria no estiver instalada.
            RuntimeError: Se alguma ferramenta de sistema no for encontrada.
        """
        pass

    def log_action(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
    ) -> None:
        """
        Registra uma ao realizada pelo atuador com contexto estruturado.

        Args:
            action: Nome da ao (ex: "click", "set_volume", "kill_process").
            details: Dicionrio com detalhes adicionais (parmetros, resultados, etc.).
            level: Nvel de log (logging.INFO, WARNING, ERROR, etc.).
        """
        msg = f"[{self.__class__.__name__}] {action}"
        if details:
            safe_details = self._sanitize_details(details)
            msg += f" {safe_details}"

        logger.log(level, msg)

        # Se histrico estiver ativado, armazena a ao
        if self.enable_history and self._action_history is not None:
            self._action_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "actuator": self.__class__.__name__,
                    "action": action,
                    "details": details,
                    "level": logging.getLevelName(level),
                }
            )
            # Limita histrico a 1000 itens para evitar vazamento de memria
            if len(self._action_history) > 1000:
                self._action_history.pop(0)

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove ou mascara informaes sensveis dos detalhes antes de logar.

        Pode ser sobrescrito por subclasses para regras especficas.
        """
        sensitive_keys = {"password", "token", "secret", "command"}
        safe = {}
        for k, v in details.items():
            if k in sensitive_keys:
                safe[k] = "***REDACTED***"
            elif isinstance(v, dict):
                safe[k] = self._sanitize_details(v)
            else:
                safe[k] = v
        return safe

    def get_action_history(self, limit: Optional[int] = None) -> list:
        """
        Retorna o histrico de aes (se enable_history=True).

        Args:
            limit: Nmero mximo de aes retornadas (mais recentes).

        Returns:
            Lista de dicionrios com as aes registradas.
        """
        if not self.enable_history:
            logger.warning(
                f"{self.__class__.__name__}: histrico no est habilitado."
            )
            return []
        if limit:
            return self._action_history[-limit:]
        return self._action_history.copy()

    def log_error(
        self, action: str, error: Exception, details: Optional[Dict] = None
    ) -> None:
        """
        Registra um erro ocorrido durante uma ao, com detalhes da exceo.
        """
        error_details = {"error_type": type(error).__name__, "error_msg": str(error)}
        if details:
            error_details.update(details)
        self.log_action(action, error_details, level=logging.ERROR)

    @track_action()  # Usa o decorator corrigido
    def execute(self, action: str, **kwargs) -> Any:
        """
        Mtodo genrico para executar uma ao no atuador.

        Por padro, levanta NotImplementedError. Subclasses podem implementar
        um dispatcher para aes comuns.

        Args:
            action: Nome da ao a executar.
            **kwargs: Parmetros especficos da ao.

        Returns:
            Resultado da ao.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} no implementa o mtodo execute() genrico."
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sysaware={self.sysaware is not None}, history={self.enable_history})"
