#!/usr/bin/env python3
"""ATENA NeuroCausal Memory Fabric.

Protótipo determinístico de uma tecnologia futura para agentes de IA:
uma malha de memória causal que transforma observações em hipóteses,
simula cenários contrafactuais e aplica gates de governança antes de
recomendar ações autônomas.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = ROOT / "docs" / "ATENA_NEUROCAUSAL_MEMORY_FABRIC.md"


@dataclass(frozen=True)
class FabricSignal:
    """Observação que alimenta a malha causal."""

    name: str
    domain: str
    evidence: str
    strength: float
    risk: float
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class CausalHypothesis:
    """Hipótese causal derivada por sobreposição de capacidades."""

    cause: str
    effect: str
    shared_capabilities: tuple[str, ...]
    confidence: float
    safety_gate: str


@dataclass(frozen=True)
class CounterfactualScenario:
    """Cenário de simulação removendo uma capacidade da arquitetura."""

    removed_capability: str
    affected_signals: tuple[str, ...]
    predicted_impact: str
    mitigation: str


BASE_SIGNALS: tuple[FabricSignal, ...] = (
    FabricSignal(
        name="causal_memory",
        domain="memory",
        evidence="Eventos são armazenados com causa, efeito, incerteza e origem auditável.",
        strength=0.92,
        risk=0.18,
        capabilities=("provenance", "causal_graph", "long_horizon_learning"),
    ),
    FabricSignal(
        name="counterfactual_simulator",
        domain="reasoning",
        evidence="O agente testa o que mudaria se uma ação, ferramenta ou premissa fosse removida.",
        strength=0.88,
        risk=0.24,
        capabilities=("causal_graph", "simulation", "rollback_planning"),
    ),
    FabricSignal(
        name="constitutional_governance",
        domain="safety",
        evidence="Políticas verificáveis bloqueiam auto-modificação e ações externas sem trilha de auditoria.",
        strength=0.95,
        risk=0.12,
        capabilities=("policy_gate", "provenance", "rollback_planning"),
    ),
    FabricSignal(
        name="multi_agent_research_mesh",
        domain="collaboration",
        evidence="Subagentes especializados compartilham achados somente quando passam por verificação cruzada.",
        strength=0.84,
        risk=0.28,
        capabilities=("verification", "simulation", "long_horizon_learning"),
    ),
)


class NeuroCausalMemoryFabric:
    """Motor pequeno para projetar a tecnologia NeuroCausal Memory Fabric."""

    def __init__(self, signals: Sequence[FabricSignal] = BASE_SIGNALS) -> None:
        self.signals = tuple(signals)

    def infer_hypotheses(self) -> list[CausalHypothesis]:
        """Conecta sinais com capacidades compartilhadas e calcula confiança."""
        hypotheses: list[CausalHypothesis] = []
        for idx, cause in enumerate(self.signals):
            for effect in self.signals[idx + 1 :]:
                shared = tuple(sorted(set(cause.capabilities).intersection(effect.capabilities)))
                if not shared:
                    continue
                confidence = round(
                    ((cause.strength + effect.strength) / 2)
                    * (1 - max(cause.risk, effect.risk) / 2),
                    3,
                )
                safety_gate = (
                    "human_review" if max(cause.risk, effect.risk) >= 0.25 else "auto_governed"
                )
                hypotheses.append(
                    CausalHypothesis(
                        cause=cause.name,
                        effect=effect.name,
                        shared_capabilities=shared,
                        confidence=confidence,
                        safety_gate=safety_gate,
                    )
                )
        return hypotheses

    def simulate_counterfactual(self, removed_capability: str) -> CounterfactualScenario:
        """Simula impacto de remover uma capacidade da malha."""
        affected = tuple(
            signal.name for signal in self.signals if removed_capability in signal.capabilities
        )
        if not affected:
            return CounterfactualScenario(
                removed_capability=removed_capability,
                affected_signals=(),
                predicted_impact="baixo: capacidade não aparece nos sinais base",
                mitigation="registrar nova evidência antes de alterar a arquitetura",
            )
        severity = "alto" if len(affected) >= 3 else "médio"
        return CounterfactualScenario(
            removed_capability=removed_capability,
            affected_signals=affected,
            predicted_impact=f"{severity}: {len(affected)} subsistemas perderiam rastreabilidade ou adaptação",
            mitigation="ativar rollback planejado, congelar auto-modificação e exigir validação humana",
        )

    def build_blueprint(self, objective: str) -> dict[str, Any]:
        """Gera um blueprint versionável para uma tecnologia futura de IA."""
        hypotheses = self.infer_hypotheses()
        scenario = self.simulate_counterfactual("provenance")
        score = round(sum(item.confidence for item in hypotheses) / max(1, len(hypotheses)), 3)
        return {
            "status": "ok",
            "technology": "ATENA NeuroCausal Memory Fabric",
            "objective": objective,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "readiness_score": score,
            "core_idea": (
                "Uma camada de memória causal para agentes que conecta evidência, causa, efeito, "
                "simulação contrafactual e governança antes de qualquer ação autônoma."
            ),
            "architecture": [
                "Causal Event Ledger: registra observações com origem, confiança e risco.",
                "NeuroSymbolic Linker: cria hipóteses causais entre sinais e capacidades.",
                "Counterfactual Sandbox: testa impactos de remover premissas, ferramentas ou ações.",
                "Governance Gate: decide auto_governed, human_review ou rollback antes de executar.",
                "Learning Mesh: compartilha apenas aprendizados com evidência e trilha auditável.",
            ],
            "signals": [asdict(signal) for signal in self.signals],
            "causal_hypotheses": [asdict(item) for item in hypotheses],
            "counterfactual_demo": asdict(scenario),
            "future_milestones": [
                "MVP local com replay causal de decisões da ATENA.",
                "Benchmark antes/depois medindo redução de erro em tarefas longas.",
                "Integração com memory/RAG para recuperar causas, não só textos semelhantes.",
                "Auditoria externa de políticas antes de habilitar auto-evolução real.",
            ],
        }


def render_markdown(blueprint: dict[str, Any]) -> str:
    """Renderiza o blueprint em Markdown."""
    lines = [
        f"# {blueprint['technology']}",
        "",
        f"- Status: `{blueprint['status']}`",
        f"- Objetivo: {blueprint['objective']}",
        f"- Readiness score: `{blueprint['readiness_score']}`",
        "",
        "## Ideia central",
        blueprint["core_idea"],
        "",
        "## Arquitetura proposta",
    ]
    lines.extend(f"- {item}" for item in blueprint["architecture"])
    lines.extend(["", "## Hipóteses causais"])
    for item in blueprint["causal_hypotheses"]:
        caps = ", ".join(item["shared_capabilities"])
        lines.append(
            f"- `{item['cause']}` → `{item['effect']}` | confiança `{item['confidence']}` | gate `{item['safety_gate']}` | capacidades: {caps}"
        )
    demo = blueprint["counterfactual_demo"]
    lines.extend(
        [
            "",
            "## Simulação contrafactual",
            f"- Capacidade removida: `{demo['removed_capability']}`",
            f"- Sinais afetados: {', '.join(demo['affected_signals'])}",
            f"- Impacto previsto: {demo['predicted_impact']}",
            f"- Mitigação: {demo['mitigation']}",
            "",
            "## Próximos marcos",
        ]
    )
    lines.extend(f"- {item}" for item in blueprint["future_milestones"])
    lines.append("")
    return "\n".join(lines)


def write_blueprint_doc(blueprint: dict[str, Any], path: Path | str = DEFAULT_DOC_PATH) -> Path:
    """Escreve documentação da tecnologia futura."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(blueprint), encoding="utf-8")
    return output


def build_future_ai_technology(objective: str) -> dict[str, Any]:
    """Atalho público usado por testes e CLI."""
    return NeuroCausalMemoryFabric().build_blueprint(objective)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cria uma tecnologia futura de IA para a ATENA")
    parser.add_argument("objective", nargs="*", help="Objetivo da tecnologia futura")
    parser.add_argument(
        "--write-doc", action="store_true", help="Escreve docs/ATENA_NEUROCAUSAL_MEMORY_FABRIC.md"
    )
    parser.add_argument("--json", action="store_true", help="Imprime JSON completo")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    objective = " ".join(args.objective).strip() or "futuro das IAs autônomas seguras"
    blueprint = build_future_ai_technology(objective)
    if args.write_doc:
        blueprint["doc_path"] = str(write_blueprint_doc(blueprint))
    if args.json:
        print(json.dumps(blueprint, ensure_ascii=False, indent=2))
    else:
        print(
            f"{blueprint['technology']} status={blueprint['status']} score={blueprint['readiness_score']}"
        )
        if args.write_doc:
            print(f"Doc: {blueprint['doc_path']}")
        print(blueprint["core_idea"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
