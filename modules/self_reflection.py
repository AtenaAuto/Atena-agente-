import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("atena.reflection")

class SelfReflection:
    """
    Self-Reflection: Diário de Bordo e Auto-Crítica.
    Permite que a ATENA analise seu próprio desempenho e ajuste estratégias
    de longo prazo baseada em sucessos e falhas recentes.
    """
    def __init__(self, log_path: str = "atena_evolution/reflection_journal.json"):
        self.log_path = log_path
        self.journal = self._load_journal()

    def _load_journal(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def reflect(self, generation: int, last_mutation: str, success: bool, score: float):
        """Adiciona uma entrada ao diário de bordo e gera uma auto-crítica."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "generation": generation,
            "mutation": last_mutation,
            "success": success,
            "score": score,
            "thought": self._generate_thought(success, score)
        }
        self.journal.append(entry)
        self._save_journal()
        logger.info(f"[Reflection] Pensamento da Geração {generation}: {entry['thought']}")

    def _generate_thought(self, success: bool, score: float) -> str:
        """Gera uma string de pensamento baseada no resultado."""
        if success:
            if score > 90:
                return "Excelente progresso. O padrão atual é altamente eficiente. Manter estratégia."
            return "Melhoria incremental detectada. Explorar variações deste padrão."
        else:
            return "A mutação não trouxe benefícios. Talvez o código atual esteja saturado ou o padrão seja incompatível."

    def get_strategy_adjustment(self) -> Dict[str, float]:
        """Analisa as últimas entradas para sugerir ajustes de estratégia."""
        if len(self.journal) < 5:
            return {}
        
        recent = self.journal[-5:]
        success_rate = sum(1 for e in recent if e['success']) / 5
        
        if success_rate < 0.2:
            logger.warning("[Reflection] Baixa taxa de sucesso detectada. Sugerindo mudança de estratégia.")
            return {"exploration_rate": 1.5, "mutation_intensity": 0.8}
        return {"exploration_rate": 1.0, "mutation_intensity": 1.0}

    def _save_journal(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, 'w') as f:
            json.dump(self.journal[-100:], f, indent=2) # Mantém as últimas 100 reflexões

# Instância global
reflection = SelfReflection()
