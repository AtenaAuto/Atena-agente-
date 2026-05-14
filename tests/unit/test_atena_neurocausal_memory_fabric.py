from __future__ import annotations

import json

from core.atena_neurocausal_memory_fabric import (
    NeuroCausalMemoryFabric,
    build_future_ai_technology,
    write_blueprint_doc,
)


def test_future_ai_technology_blueprint_has_causal_and_counterfactual_layers():
    blueprint = build_future_ai_technology("criar tecnologia de IA para o futuro")

    assert blueprint["status"] == "ok"
    assert blueprint["technology"] == "ATENA NeuroCausal Memory Fabric"
    assert blueprint["readiness_score"] > 0.6
    assert blueprint["causal_hypotheses"]
    assert blueprint["counterfactual_demo"]["removed_capability"] == "provenance"
    assert "Governance Gate" in " ".join(blueprint["architecture"])


def test_counterfactual_unknown_capability_is_low_impact():
    scenario = NeuroCausalMemoryFabric().simulate_counterfactual("unknown_capability")

    assert scenario.affected_signals == ()
    assert scenario.predicted_impact.startswith("baixo")


def test_write_blueprint_doc(tmp_path):
    blueprint = build_future_ai_technology("documentar futuro das IAs")
    path = write_blueprint_doc(blueprint, tmp_path / "fabric.md")

    content = path.read_text(encoding="utf-8")
    assert "ATENA NeuroCausal Memory Fabric" in content
    assert "Simulação contrafactual" in content
    assert json.loads(json.dumps(blueprint))["status"] == "ok"
