import os
import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class AtenaControlBridge:
    def __init__(self, state_file: str | None = None):
        if state_file is None:
            repo_root = Path(__file__).resolve().parent.parent
            state_file = str(repo_root / "atena_evolution" / "atena_state.json")
        self.state_file = state_file
        self._ensure_state_file()

    def _ensure_state_file(self):
        """Garante que o arquivo de estado exista com valores padrão."""
        if not os.path.exists(self.state_file):
            self.set_state({"status": "running", "last_command": "start", "timestamp": ""})

    def get_state(self) -> Dict[str, Any]:
        """Lê o estado atual do sistema."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler estado: {e}")
        return {"status": "running"}

    def set_state(self, state: Dict[str, Any]):
        """Atualiza o estado do sistema."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")

    def send_command(self, command: str):
        """Envia um comando para a ATENA (pause, resume, stop)."""
        state = self.get_state()
        state["status"] = "paused" if command == "pause" else "running"
        state["last_command"] = command
        state["timestamp"] = str(os.times().elapsed)
        self.set_state(state)
        logger.info(f"Comando enviado via Bridge: {command}")

    def is_paused(self) -> bool:
        """Verifica se o sistema deve estar pausado."""
        return self.get_state().get("status") == "paused"
