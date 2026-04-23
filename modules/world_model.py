import os
import subprocess
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger("atena.world_model")

class WorldModel:
    """
    World Model: Simulação de Ambiente.
    Permite que a ATENA preveja o impacto de uma mutação em um ambiente isolado (Mirror)
    antes de aplicá-la ao DNA principal.
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.mirror_dir = self.base_dir / "atena_evolution" / "mirror_world"
        os.makedirs(self.mirror_dir, exist_ok=True)

    def simulate_mutation(self, code: str, test_script: str = "quick_test.py") -> Tuple[bool, float, str]:
        """
        Cria um 'espelho' do ambiente, aplica a mutação e roda testes de estresse.
        Retorna (sucesso, score_previsto, logs).
        """
        with tempfile.TemporaryDirectory(dir=self.mirror_dir) as tmp_mirror:
            tmp_path = Path(tmp_mirror)
            
            # 1. Clonar arquivos essenciais para o espelho
            essential_files = ["main.py", "quick_test.py", "requirements.txt"]
            for f in essential_files:
                src = self.base_dir / f
                if src.exists():
                    shutil.copy(src, tmp_path / f)
            
            # 2. Aplicar a nova mutação no main.py do espelho
            (tmp_path / "main.py").write_text(code)
            
            # 3. Executar simulação
            logger.info(f"[WorldModel] Iniciando simulação em ambiente isolado...")
            try:
                result = subprocess.run(
                    ["python3", test_script],
                    cwd=tmp_mirror,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                success = result.returncode == 0
                # Extrair score do output se disponível, senão usar heurística
                score = 1.0 if success else 0.0
                if "RESULTADO: Todos os" in result.stdout:
                    score = 1.0
                
                logger.info(f"[WorldModel] Simulação concluída. Sucesso: {success}, Score: {score}")
                return success, score, result.stdout + result.stderr
                
            except subprocess.TimeoutExpired:
                logger.warning("[WorldModel] Simulação atingiu timeout!")
                return False, 0.0, "Timeout"
            except Exception as e:
                logger.error(f"[WorldModel] Erro na simulação: {e}")
                return False, 0.0, str(e)

# Instância global
world_model = WorldModel()
