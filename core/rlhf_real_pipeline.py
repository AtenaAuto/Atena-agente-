#!/usr/bin/env python3
"""Pipeline base para RLHF real (Reward Model + PPO).

Este módulo define um esqueleto funcional para:
1) Treinar reward model neural a partir de preferências humanas.
2) Otimizar uma política com PPO usando o reward model.

Observação: não executa treino completo sozinho sem dataset/modelo base.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    class _NNStub:
        class Module:  # noqa: D401
            """Stub base class quando torch não está disponível."""
            pass
    nn = _NNStub()  # type: ignore[assignment]
    F = None  # type: ignore[assignment]


@dataclass
class PreferenceSample:
    prompt: str
    chosen: str
    rejected: str


class RewardModel(nn.Module):
    """Reward model neural simples para ranking de respostas."""

    def __init__(self, hidden_size: int = 768):
        if torch is None:
            raise RuntimeError("PyTorch não instalado. Instale `torch` para usar RLHF real.")
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
        )
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.head(z).squeeze(-1)


def pairwise_preference_loss(chosen_reward: torch.Tensor, rejected_reward: torch.Tensor) -> torch.Tensor:
    """Loss padrão de preferência: -log(sigmoid(r_chosen - r_rejected))."""
    if F is None:
        raise RuntimeError("PyTorch não instalado. Instale `torch` para usar RLHF real.")
    return -F.logsigmoid(chosen_reward - rejected_reward).mean()


class PPOTrainer:
    """Treinador PPO mínimo para ajuste de política com reward model."""

    def __init__(
        self,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        kl_coef: float = 0.02,
    ):
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.kl_coef = kl_coef

    def ppo_objective(
        self,
        logp_new: torch.Tensor,
        logp_old: torch.Tensor,
        advantages: torch.Tensor,
        values: torch.Tensor,
        returns: torch.Tensor,
        entropy: torch.Tensor,
        kl: torch.Tensor | None = None,
    ) -> torch.Tensor:
        advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
        ratio = torch.exp(logp_new - logp_old)
        unclipped = ratio * advantages
        clipped = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * advantages
        policy_loss = -torch.min(unclipped, clipped).mean()
        value_loss = F.mse_loss(values, returns)
        entropy_bonus = entropy.mean()
        kl_term = (kl.mean() if kl is not None else torch.tensor(0.0, device=logp_new.device))
        return policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy_bonus + self.kl_coef * kl_term


def compute_gae(
    rewards: torch.Tensor,
    values: torch.Tensor,
    dones: torch.Tensor,
    gamma: float = 0.99,
    lam: float = 0.95,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Calcula GAE-Lambda e retornos para PPO."""
    if torch is None:
        raise RuntimeError("PyTorch não instalado. Instale `torch` para usar RLHF real.")
    T = rewards.shape[0]
    advantages = torch.zeros_like(rewards)
    gae = torch.tensor(0.0, device=rewards.device)
    for t in reversed(range(T)):
        next_value = values[t + 1] if t + 1 < T else torch.tensor(0.0, device=values.device)
        non_terminal = 1.0 - dones[t]
        delta = rewards[t] + gamma * next_value * non_terminal - values[t]
        gae = delta + gamma * lam * non_terminal * gae
        advantages[t] = gae
    returns = advantages + values
    return advantages, returns


def train_reward_model_step(
    reward_model: RewardModel,
    optimizer: torch.optim.Optimizer,
    chosen_embeddings: torch.Tensor,
    rejected_embeddings: torch.Tensor,
) -> float:
    if torch is None:
        raise RuntimeError("PyTorch não instalado. Instale `torch` para usar RLHF real.")
    reward_model.train()
    chosen_reward = reward_model(chosen_embeddings)
    rejected_reward = reward_model(rejected_embeddings)
    loss = pairwise_preference_loss(chosen_reward, rejected_reward)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()
    return float(loss.item())


def iterate_preference_batches(samples: Iterable[PreferenceSample]) -> Iterable[list[PreferenceSample]]:
    """Placeholder de batching; trocar por DataLoader real."""
    bucket: list[PreferenceSample] = []
    for sample in samples:
        bucket.append(sample)
        if len(bucket) >= 8:
            yield bucket
            bucket = []
    if bucket:
        yield bucket
