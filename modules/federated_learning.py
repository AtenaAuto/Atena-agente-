#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Federated Learning v2.0
Aprendizado federado REAL usando SGDClassifier (sklearn).

Cada cliente treina um modelo local com gradiente incremental (partial_fit).
O servidor agrega os coeficientes reais via FedAvg e redistribui.
Nenhuma simulação — pesos reais convergem com os dados.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def samples_to_arrays(
    local_data: List[Dict[str, Any]],
    feature_keys: List[str],
    label_key: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """Converte lista de dicts em arrays X, y para sklearn."""
    X = np.array([[s[k] for k in feature_keys] for s in local_data], dtype=float)
    y = np.array([s[label_key] for s in local_data])
    return X, y


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FederatedLearningClient:
    """
    Cliente de aprendizado federado com modelo SGD real.

    Treina localmente com partial_fit (gradiente incremental) e
    retorna os coeficientes reais para o servidor agregar.
    """

    def __init__(
        self,
        client_id: str,
        feature_keys: List[str],
        label_key: str,
        classes: List[Any],
        global_coef: Optional[np.ndarray] = None,
        global_intercept: Optional[np.ndarray] = None,
    ):
        if not HAS_SKLEARN:
            raise RuntimeError("scikit-learn não instalado. Execute: pip install scikit-learn")

        self.client_id = client_id
        self.feature_keys = feature_keys
        self.label_key = label_key
        self.classes = classes
        self.scaler = StandardScaler()

        self.model = SGDClassifier(
            loss="log_loss",
            max_iter=1,
            warm_start=True,
            random_state=42,
            learning_rate="adaptive",
            eta0=0.01,
        )

        if global_coef is not None and global_intercept is not None:
            self._set_weights(global_coef, global_intercept)

    def _set_weights(self, coef: np.ndarray, intercept: np.ndarray) -> None:
        self.model.coef_ = coef.copy()
        self.model.intercept_ = intercept.copy()
        self.model.classes_ = np.array(self.classes)

    def receive_global_weights(self, coef: np.ndarray, intercept: np.ndarray) -> None:
        self._set_weights(coef, intercept)
        logger.debug("[%s] Pesos globais recebidos. coef_norm=%.4f", self.client_id, np.linalg.norm(coef))

    def train_on_local_data(
        self, local_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Treina o modelo nos dados locais e retorna os pesos atualizados.
        Usa partial_fit — gradiente real, sem simulação.
        """
        X, y = samples_to_arrays(local_data, self.feature_keys, self.label_key)
        X = self.scaler.fit_transform(X)
        self.model.partial_fit(X, y, classes=self.classes)

        acc = accuracy_score(y, self.model.predict(X))
        logger.info(
            "[%s] Treino local: %d amostras | acc=%.3f | coef_norm=%.4f",
            self.client_id, len(local_data), acc, np.linalg.norm(self.model.coef_),
        )
        return {
            "coef": self.model.coef_.copy(),
            "intercept": self.model.intercept_.copy(),
            "n_samples": len(local_data),
            "accuracy": acc,
        }


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@dataclass
class RoundResult:
    round_num: int
    global_coef_norm: float
    avg_client_accuracy: float
    n_clients: int
    coef: np.ndarray
    intercept: np.ndarray


class FederatedLearningServer:
    """
    Servidor de aprendizado federado com FedAvg real.

    Agrega coeficientes ponderados pelo número de amostras de cada cliente
    (FedAvg weighted — McMahan et al. 2017).
    """

    def __init__(self, n_features: int, n_classes: int = 2):
        if not HAS_SKLEARN:
            raise RuntimeError("scikit-learn não instalado. Execute: pip install scikit-learn")

        self.n_features = n_features
        self.n_classes = n_classes
        n_coef_rows = 1 if n_classes == 2 else n_classes

        self.global_coef = np.zeros((n_coef_rows, n_features))
        self.global_intercept = np.zeros(n_coef_rows)

        self.clients: List[FederatedLearningClient] = []
        self.history: List[RoundResult] = []

    def register_client(self, client: FederatedLearningClient) -> None:
        client.receive_global_weights(self.global_coef, self.global_intercept)
        self.clients.append(client)
        logger.info("Cliente '%s' registrado. Total: %d", client.client_id, len(self.clients))

    def _fedavg(self, updates: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """FedAvg ponderado pelo número de amostras (McMahan et al., 2017)."""
        total_samples = sum(u["n_samples"] for u in updates)
        agg_coef = np.zeros_like(self.global_coef)
        agg_intercept = np.zeros_like(self.global_intercept)
        for u in updates:
            weight = u["n_samples"] / total_samples
            agg_coef += weight * u["coef"]
            agg_intercept += weight * u["intercept"]
        return agg_coef, agg_intercept

    def run_round(
        self,
        local_data_per_client: Dict[str, List[Dict[str, Any]]],
    ) -> RoundResult:
        """Executa uma rodada completa de aprendizado federado."""
        round_num = len(self.history) + 1
        logger.info("── Rodada %d iniciada ──", round_num)

        updates = []
        for client in self.clients:
            data = local_data_per_client.get(client.client_id)
            if not data:
                logger.warning("Sem dados para cliente '%s'.", client.client_id)
                continue
            updates.append(client.train_on_local_data(data))

        if not updates:
            raise ValueError("Nenhum cliente enviou atualização.")

        self.global_coef, self.global_intercept = self._fedavg(updates)

        for client in self.clients:
            client.receive_global_weights(self.global_coef, self.global_intercept)

        avg_acc = float(np.mean([u["accuracy"] for u in updates]))
        result = RoundResult(
            round_num=round_num,
            global_coef_norm=float(np.linalg.norm(self.global_coef)),
            avg_client_accuracy=avg_acc,
            n_clients=len(updates),
            coef=self.global_coef.copy(),
            intercept=self.global_intercept.copy(),
        )
        self.history.append(result)
        logger.info(
            "── Rodada %d concluída | acc_média=%.3f | coef_norm=%.4f ──",
            round_num, avg_acc, result.global_coef_norm,
        )
        return result

    def get_global_weights(self) -> Dict[str, np.ndarray]:
        return {"coef": self.global_coef.copy(), "intercept": self.global_intercept.copy()}


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    random.seed(0)
    np.random.seed(0)

    def make_data(n: int, x_range, y_range):
        data = []
        for _ in range(n):
            x = random.uniform(*x_range)
            y = random.uniform(*y_range)
            label = 1 if (x + y) > 5 else 0
            data.append({"x": x, "y": y, "label": label})
        return data

    FEATURE_KEYS = ["x", "y"]
    LABEL_KEY = "label"
    CLASSES = [0, 1]

    server = FederatedLearningServer(n_features=2, n_classes=2)

    clients_data = {
        "ClientA": make_data(80,  (0, 4), (0, 4)),
        "ClientB": make_data(60,  (2, 6), (2, 6)),
        "ClientC": make_data(100, (4, 8), (4, 8)),
    }

    for cid, data in clients_data.items():
        client = FederatedLearningClient(cid, FEATURE_KEYS, LABEL_KEY, CLASSES)
        server.register_client(client)

    print("\n🔱 Iniciando Aprendizado Federado REAL (FedAvg)\n")
    for _ in range(5):
        result = server.run_round(clients_data)
        print(f"  Rodada {result.round_num}: acc_média={result.avg_client_accuracy:.3f} | coef_norm={result.global_coef_norm:.4f}")

    print("\n✅ Pesos globais finais:")
    weights = server.get_global_weights()
    print(f"  coef      = {weights['coef']}")
    print(f"  intercept = {weights['intercept']}")
