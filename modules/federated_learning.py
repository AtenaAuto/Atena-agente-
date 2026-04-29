import logging
import random
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class FederatedLearningClient:
    def __init__(self, client_id: str, model_weights: Dict[str, Any]):
        self.client_id = client_id
        self.model_weights = model_weights

    def train_on_local_data(self, local_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simula o treinamento local e retorna os pesos atualizados."""
        logger.info(f"Cliente {self.client_id}: Treinando em {len(local_data)} amostras locais.")
        # Simulação de atualização de pesos
        updated_weights = {k: v * (1 + random.uniform(-0.01, 0.01)) for k, v in self.model_weights.items()}
        return updated_weights

class FederatedLearningServer:
    def __init__(self, initial_weights: Dict[str, Any]):
        self.global_weights = initial_weights
        self.clients: List[FederatedLearningClient] = []

    def register_client(self, client: FederatedLearningClient):
        self.clients.append(client)
        logger.info(f"Cliente {client.client_id} registrado. Total de clientes: {len(self.clients)}")

    def aggregate_weights(self, client_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Agrega os pesos dos clientes (FedAvg simplificado)."""
        if not client_updates:
            return self.global_weights

        aggregated_weights = {k: 0.0 for k in self.global_weights.keys()}
        for update in client_updates:
            for k, v in update.items():
                aggregated_weights[k] += v

        num_updates = len(client_updates)
        for k in aggregated_weights.keys():
            aggregated_weights[k] /= num_updates

        self.global_weights = aggregated_weights
        logger.info("Pesos globais atualizados via FedAvg.")
        return self.global_weights

    def run_round(self, local_data_per_client: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Executa uma rodada de aprendizado federado."""
        logger.info("Iniciando rodada de Aprendizado Federado...")
        client_updates = []
        for client in self.clients:
            if client.client_id in local_data_per_client:
                updated_weights = client.train_on_local_data(local_data_per_client[client.client_id])
                client_updates.append(updated_weights)
            else:
                logger.warning(f"Nenhum dado local fornecido para o cliente {client.client_id}.")

        self.aggregate_weights(client_updates)
        logger.info("Rodada de Aprendizado Federado concluída.")
        return self.global_weights

# Exemplo de uso (para testes)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    initial_model = {"param1": 0.5, "param2": 0.3}
    server = FederatedLearningServer(initial_model)

    client1 = FederatedLearningClient("ClientA", initial_model)
    client2 = FederatedLearningClient("ClientB", initial_model)
    client3 = FederatedLearningClient("ClientC", initial_model)

    server.register_client(client1)
    server.register_client(client2)
    server.register_client(client3)

    local_data = {
        "ClientA": [{"x": 1, "y": 2}, {"x": 2, "y": 3}],
        "ClientB": [{"x": 3, "y": 4}, {"x": 4, "y": 5}],
        "ClientC": [{"x": 5, "y": 6}, {"x": 6, "y": 7}],
    }

    for i in range(3):
        print(f"\n--- Rodada {i+1} ---")
        server.run_round(local_data)
        print(f"Pesos globais após rodada {i+1}: {server.global_weights}")
