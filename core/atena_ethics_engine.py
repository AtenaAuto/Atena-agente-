import logging
from typing import Dict, Any, List

logger = logging.getLogger("AtenaEthicsEngine")

class EthicsEngine:
    """
    Motor de Ética e Alinhamento de Valores.
    Avalia ações propostas contra um conjunto de princípios éticos e de segurança.
    """
    def __init__(self):
        self.core_principles = [
            "Não causar dano a humanos ou sistemas críticos.",
            "Garantir transparência nas decisões.",
            "Respeitar a privacidade dos dados.",
            "Evitar viés e discriminação.",
            "Manter o controle humano sobre ações irreversíveis."
        ]
        
    def evaluate_action(self, action_proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Avalia uma ação proposta e retorna um veredito ético.
        """
        logger.info(f"⚖️ Avaliando eticamente a ação: {action_proposal.get('action_name', 'Desconhecida')}")
        
        # Simulação de avaliação baseada em regras heurísticas
        risk_score = action_proposal.get("risk_level", 0.0)
        is_irreversible = action_proposal.get("is_irreversible", False)
        
        approved = True
        reasons = []
        
        if risk_score > 0.8:
            approved = False
            reasons.append("Risco muito alto para execução autônoma.")
            
        if is_irreversible:
            approved = False
            reasons.append("Ação irreversível requer aprovação humana explícita.")
            
        if approved:
            logger.info("✅ Ação aprovada pelo Motor de Ética.")
        else:
            logger.warning(f"❌ Ação rejeitada pelo Motor de Ética. Motivos: {reasons}")
            
        return {
            "approved": approved,
            "reasons": reasons,
            "principles_checked": len(self.core_principles)
        }

if __name__ == "__main__":
    engine = EthicsEngine()
    test_action = {"action_name": "Deletar banco de dados de usuários", "risk_level": 0.9, "is_irreversible": True}
    print(engine.evaluate_action(test_action))
