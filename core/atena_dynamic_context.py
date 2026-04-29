import logging
from typing import Dict, Any, List

logger = logging.getLogger("AtenaDynamicContext")

class DynamicContextAdapter:
    """
    Sistema de Adaptação Dinâmica de Contexto.
    Ajusta o foco e a prioridade das informações processadas pela IA com base na situação atual.
    """
    def __init__(self):
        self.current_context = "idle"
        self.priority_queue = []
        
    def update_context(self, new_situation: str, urgency: int) -> None:
        """
        Atualiza o contexto atual e reordena prioridades.
        """
        logger.info(f"🔄 Atualizando contexto para: {new_situation} (Urgência: {urgency})")
        self.current_context = new_situation
        
        # Adiciona à fila de prioridade
        self.priority_queue.append({"situation": new_situation, "urgency": urgency})
        
        # Ordena por urgência (maior primeiro)
        self.priority_queue.sort(key=lambda x: x["urgency"], reverse=True)
        
    def get_active_context(self) -> Dict[str, Any]:
        """
        Retorna o contexto mais urgente atual.
        """
        if not self.priority_queue:
            return {"situation": "idle", "urgency": 0}
            
        active = self.priority_queue[0]
        logger.info(f"🎯 Foco atual: {active['situation']}")
        return active

if __name__ == "__main__":
    adapter = DynamicContextAdapter()
    adapter.update_context("Análise de logs de erro", 5)
    adapter.update_context("Ataque DDoS detectado", 10)
    print(adapter.get_active_context())
