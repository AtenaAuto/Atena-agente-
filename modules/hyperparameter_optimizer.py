import logging
import random
from typing import Dict, Any, Callable, Tuple

logger = logging.getLogger(__name__)

class HyperparameterOptimizer:
    def __init__(self, 
                 objective_function: Callable[[Dict[str, Any]], float], 
                 param_space: Dict[str, Tuple[Any, Any]],
                 optimization_type: str = "maximize"): # "maximize" ou "minimize"
        self.objective_function = objective_function
        self.param_space = param_space
        self.optimization_type = optimization_type
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_score: Optional[float] = None

    def _sample_params(self) -> Dict[str, Any]:
        """Amostra um conjunto aleatório de hiperparâmetros do espaço definido."""
        sampled_params = {}
        for param, (low, high) in self.param_space.items():
            if isinstance(low, (int, float)):
                if isinstance(low, int) and isinstance(high, int):
                    sampled_params[param] = random.randint(low, high)
                else:
                    sampled_params[param] = random.uniform(low, high)
            elif isinstance(low, list): # Para parâmetros categóricos
                sampled_params[param] = random.choice(low)
            else:
                raise ValueError(f"Tipo de parâmetro não suportado: {type(low)}")
        return sampled_params

    def optimize(self, num_iterations: int = 10) -> Tuple[Dict[str, Any], float]:
        """Executa a otimização de hiperparâmetros usando busca aleatória simples."""
        logger.info(f"Iniciando otimização de hiperparâmetros ({self.optimization_type}) por {num_iterations} iterações.")
        
        for i in range(num_iterations):
            params = self._sample_params()
            score = self.objective_function(params)
            logger.info(f"Iteração {i+1}: Parâmetros: {params}, Score: {score:.4f}")

            if self.best_score is None or \
               (self.optimization_type == "maximize" and score > self.best_score) or \
               (self.optimization_type == "minimize" and score < self.best_score):
                self.best_score = score
                self.best_params = params
                logger.info(f"  -> Novo melhor score: {self.best_score:.4f} com parâmetros: {self.best_params}")
        
        if self.best_params is None:
            raise RuntimeError("Otimização falhou: nenhum parâmetro válido encontrado.")

        logger.info(f"Otimização concluída. Melhor score: {self.best_score:.4f} com parâmetros: {self.best_params}")
        return self.best_params, self.best_score

# Exemplo de uso (para testes)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    # Função objetivo de exemplo: simula o treinamento de um modelo
    # Queremos maximizar o "accuracy"
    def train_model_and_evaluate(params: Dict[str, Any]) -> float:
        learning_rate = params["learning_rate"]
        batch_size = params["batch_size"]
        num_layers = params["num_layers"]
        
        # Simulação de um treinamento e avaliação
        # Modelos com learning_rate entre 0.001 e 0.01 e batch_size de 32 a 64 tendem a ser melhores
        # Mais camadas nem sempre é melhor
        simulated_accuracy = 0.7 + (learning_rate * 100) - (batch_size / 1000) + (num_layers * 0.01)
        simulated_accuracy += random.uniform(-0.05, 0.05) # Adiciona ruído
        return max(0.0, min(1.0, simulated_accuracy)) # Garante que esteja entre 0 e 1

    # Espaço de busca de hiperparâmetros
    param_space = {
        "learning_rate": (0.0001, 0.1),  # float
        "batch_size": ([16, 32, 64, 128]), # categórico
        "num_layers": (1, 5)             # int
    }

    optimizer = HyperparameterOptimizer(
        objective_function=train_model_and_evaluate,
        param_space=param_space,
        optimization_type="maximize"
    )

    best_params, best_score = optimizer.optimize(num_iterations=20)
    print(f"\nMelhores parâmetros encontrados: {best_params}")
    print(f"Melhor score (accuracy): {best_score:.4f}")
