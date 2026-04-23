import logging
import random
from typing import List, Dict, Any, Tuple, Callable

logger = logging.getLogger(__name__)

class Player:
    def __init__(self, player_id: str, strategy: Callable[[List[Any], List[Any]], Any]):
        self.player_id = player_id
        self.strategy = strategy
        self.history: List[Any] = []
        self.score: float = 0.0

    def choose_action(self, opponent_history: List[Any]) -> Any:
        action = self.strategy(self.history, opponent_history)
        self.history.append(action)
        return action

    def update_score(self, points: float):
        self.score += points

    def reset(self):
        self.history = []
        self.score = 0.0

class GameTheorySimulator:
    def __init__(self, players: List[Player], payoff_matrix: Dict[Tuple[Any, ...], Tuple[float, ...]]):
        self.players = players
        self.payoff_matrix = payoff_matrix
        self.num_players = len(players)
        if self.num_players != 2: # Simplificando para jogos de 2 jogadores por enquanto
            raise ValueError("Atualmente, o simulador suporta apenas 2 jogadores.")

    def run_round(self) -> Dict[str, Any]:
        """Executa uma rodada do jogo e retorna as ações e recompensas."""
        actions = []
        for i, player in enumerate(self.players):
            opponent_history = self.players[1-i].history if self.num_players == 2 else [] # Para 2 jogadores
            action = player.choose_action(opponent_history)
            actions.append(action)
        
        # Calcula o payoff para cada jogador
        # A matriz de payoff deve ser indexada por (ação_jogador1, ação_jogador2) -> (payoff_jogador1, payoff_jogador2)
        try:
            payoffs = self.payoff_matrix[tuple(actions)]
        except KeyError:
            logger.error(f"Combinação de ações {actions} não encontrada na matriz de payoff.")
            payoffs = (0.0, 0.0) # Penalidade por ação inválida

        for i, player in enumerate(self.players):
            player.update_score(payoffs[i])
        
        logger.info(f"Rodada: Ações={actions}, Payoffs={payoffs}")
        return {"actions": actions, "payoffs": payoffs}

    def run_simulation(self, num_rounds: int = 100) -> Dict[str, Any]:
        """Executa uma simulação completa do jogo."""
        logger.info(f"Iniciando simulação de Teoria dos Jogos por {num_rounds} rodadas.")
        for player in self.players:
            player.reset()

        for _ in range(num_rounds):
            self.run_round()
        
        final_scores = {player.player_id: player.score for player in self.players}
        logger.info(f"Simulação concluída. Scores finais: {final_scores}")
        return {"final_scores": final_scores, "player_histories": {p.player_id: p.history for p in self.players}}

# Estratégias de exemplo
def tit_for_tat(self_history: List[Any], opponent_history: List[Any]) -> Any:
    """Começa cooperando, depois copia a última ação do oponente."""
    if not opponent_history:
        return "Cooperate"
    return opponent_history[-1]

def always_defect(self_history: List[Any], opponent_history: List[Any]) -> Any:
    """Sempre deserta."""
    return "Defect"

def random_strategy(self_history: List[Any], opponent_history: List[Any]) -> Any:
    """Escolhe aleatoriamente."""
    return random.choice(["Cooperate", "Defect"])

# Exemplo de uso (para testes): Dilema do Prisioneiro
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    # Matriz de Payoff para o Dilema do Prisioneiro (Cooperate, Defect)
    # (Minha Ação, Sua Ação) -> (Meu Payoff, Seu Payoff)
    prisoner_payoff_matrix = {
        ("Cooperate", "Cooperate"): (3, 3),  # Recompensa mútua
        ("Cooperate", "Defect"):    (0, 5),  # Tentação
        ("Defect",    "Cooperate"): (5, 0),  # Otário
        ("Defect",    "Defect"):    (1, 1)   # Punição mútua
    }

    print("\n--- Simulação: Tit-for-Tat vs. Always Defect ---")
    player_tft = Player("TFT", tit_for_tat)
    player_ad = Player("AlwaysDefect", always_defect)
    simulator1 = GameTheorySimulator([player_tft, player_ad], prisoner_payoff_matrix)
    results1 = simulator1.run_simulation(num_rounds=10)
    print(f"Resultados TFT vs AD: {results1['final_scores']}")

    print("\n--- Simulação: Tit-for-Tat vs. Random ---")
    player_tft2 = Player("TFT", tit_for_tat)
    player_rand = Player("Random", random_strategy)
    simulator2 = GameTheorySimulator([player_tft2, player_rand], prisoner_payoff_matrix)
    results2 = simulator2.run_simulation(num_rounds=10)
    print(f"Resultados TFT vs Random: {results2['final_scores']}")
