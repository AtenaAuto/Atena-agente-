import pytest

from core import rlhf_real_pipeline as rlhf

try:
    import torch  # type: ignore
    HAS_TORCH = True
except Exception:
    torch = None  # type: ignore[assignment]
    HAS_TORCH = False


def test_module_imports_without_torch():
    # Garante que o módulo carrega mesmo sem torch no ambiente.
    assert hasattr(rlhf, "PPOTrainer")
    assert hasattr(rlhf, "compute_gae")


def test_preference_loss_positive():
    if not HAS_TORCH:
        pytest.skip("torch indisponível no ambiente")
    a = torch.tensor([1.0, 0.5])
    b = torch.tensor([0.2, -0.1])
    loss = rlhf.pairwise_preference_loss(a, b)
    assert loss.item() > 0


def test_compute_gae_shapes():
    if not HAS_TORCH:
        pytest.skip("torch indisponível no ambiente")
    rewards = torch.tensor([1.0, 0.0, 1.0])
    values = torch.tensor([0.1, 0.2, 0.3])
    dones = torch.tensor([0.0, 0.0, 1.0])
    adv, ret = rlhf.compute_gae(rewards, values, dones)
    assert adv.shape == rewards.shape
    assert ret.shape == rewards.shape


def test_ppo_objective_scalar():
    if not HAS_TORCH:
        pytest.skip("torch indisponível no ambiente")
    trainer = rlhf.PPOTrainer()
    obj = trainer.ppo_objective(
        logp_new=torch.randn(5),
        logp_old=torch.randn(5),
        advantages=torch.randn(5),
        values=torch.randn(5),
        returns=torch.randn(5),
        entropy=torch.rand(5),
        kl=torch.rand(5),
    )
    assert obj.ndim == 0
