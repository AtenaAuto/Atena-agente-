import logging
from typing import Dict, Any, List

logger = logging.getLogger("AtenaCausalInference")

class CausalInferenceEngine:
    """
    Motor de Inferência Causal.
    Identifica relações de causa e efeito em dados observacionais para prever resultados de intervenções.
    """
    def __init__(self):
        self.causal_graph = {}
        
    def add_causal_link(self, cause: str, effect: str, strength: float) -> None:
        """
        Adiciona uma relação causal ao grafo de conhecimento.
        """
        logger.info(f"🔗 Nova relação causal: {cause} -> {effect} (Força: {strength})")
        
        if cause not in self.causal_graph:
            self.causal_graph[cause] = []
            
        self.causal_graph[cause].append({"effect": effect, "strength": strength})
        
    def predict_intervention(self, intervention: str) -> List[Dict[str, Any]]:
        """
        Prevê os efeitos de uma intervenção baseada no grafo causal.
        """
        logger.info(f"🔮 Prevendo efeitos da intervenção: {intervention}")
        
        if intervention not in self.causal_graph:
            return [{"effect": "Desconhecido", "confidence": 0.0}]
            
        predictions = []
        for link in self.causal_graph[intervention]:
            predictions.append({
                "effect": link["effect"],
                "confidence": link["strength"]
            })
            
        # Ordena por confiança
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        return predictions

if __name__ == "__main__":
    engine = CausalInferenceEngine()
    engine.add_causal_link("Aumentar cache", "Reduzir latência", 0.8)
    engine.add_causal_link("Aumentar cache", "Aumentar uso de memória", 0.9)
    print(engine.predict_intervention("Aumentar cache"))
