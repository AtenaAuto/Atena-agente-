#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modules/atena_langchain_bridge.py — Bridge LangGraph/LangChain para ATENA Ω

NOTA: langgraph e langchain_core são dependências opcionais.
      Se não estiverem instaladas, o módulo carrega em modo stub
      sem quebrar o sistema.
"""

import random
import operator
import logging
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List

logger = logging.getLogger("atena.langgraph")

# --- Importações opcionais de LangGraph / LangChain ---
try:
    from langgraph.graph import StateGraph, END
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    StateGraph = None
    END = "__end__"

    # Stubs mínimos para não quebrar o código que referencia essas classes
    class BaseMessage:  # type: ignore
        def __init__(self, content: str = ""):
            self.content = content

    class HumanMessage(BaseMessage):  # type: ignore
        pass

    class AIMessage(BaseMessage):  # type: ignore
        pass

    def tool(fn):  # type: ignore
        """Decorator stub quando langchain_core não está disponível."""
        return fn

    logger.warning(
        "langgraph/langchain_core não instalados — "
        "atena_langchain_bridge rodando em modo stub"
    )

# --- Importação do core da Atena (com fallback) ---
try:
    from atena_engine import AtenaCore, Config, MutationEngine, CodeEvaluator, Sandbox, EvolvableScorer
    from atena_engine import KnowledgeBase, AdaptiveChecker, MetaLearner
    HAS_ATENA_ENGINE = True
except ImportError:
    HAS_ATENA_ENGINE = False
    # Stub mínimo
    class AtenaCore:  # type: ignore
        def __init__(self):
            self.current_code = ""
            self.best_score = 0.0
            self.problem = None
            self.generation = 0

    logger.warning("atena_engine não disponível — usando stub")


# =============================================================================
# 1. DEFINIÇÃO DO ESTADO
# =============================================================================

class AtenaState(TypedDict):
    """Estado completo da evolução, mantido pelo LangGraph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    generation: int
    current_code: str
    best_code: str
    best_score: float
    problem_name: Optional[str]
    problem_description: Optional[str]
    mutation_history: List[Dict[str, Any]]
    last_mutation: Optional[str]
    last_score: float
    replaced: bool
    error: Optional[str]


# =============================================================================
# 2. FERRAMENTAS (stubs seguros quando langchain não está disponível)
# =============================================================================

@tool
def mutate_code(code: str, mutation_type: str, core: Any) -> str:
    """Aplica uma mutação ao código usando o MutationEngine da Atena."""
    if not HAS_ATENA_ENGINE:
        return code
    try:
        engine = MutationEngine(core)
        return engine.mutate(code, mutation_type) or code
    except Exception as e:
        logger.error(f"Erro em mutate_code: {e}")
        return code


@tool
def evaluate_in_sandbox(code: str, core: Any) -> Dict[str, Any]:
    """Avalia o código em sandbox e retorna métricas."""
    if not HAS_ATENA_ENGINE:
        return {"score": 0.0, "valid": False}
    try:
        evaluator = CodeEvaluator(core)
        return evaluator.evaluate(code)
    except Exception as e:
        logger.error(f"Erro em evaluate_in_sandbox: {e}")
        return {"score": 0.0, "valid": False, "error": str(e)}


# =============================================================================
# 3. NÓS DO GRAFO
# =============================================================================

def think_node(state: AtenaState, core: Any) -> Dict[str, Any]:
    """Nó de raciocínio: escolhe a próxima estratégia de mutação."""
    mutations = ["rename", "add_docstring", "optimize_loop", "refactor"]
    chosen = random.choice(mutations)
    logger.info(f"Nó think: escolheu mutação '{chosen}'")
    return {
        "last_mutation": chosen,
        "messages": [HumanMessage(content=f"Tentando mutação: {chosen}")],
    }


def mutate_node(state: AtenaState, core: Any) -> Dict[str, Any]:
    """Nó de mutação: aplica a mutação escolhida."""
    mutation_type = state.get("last_mutation")
    if not mutation_type:
        return {"error": "Nenhuma mutação escolhida"}
    mutated = mutate_code.invoke({
        "code": state["current_code"],
        "mutation_type": mutation_type,
        "core": core,
    })
    if mutated == state["current_code"]:
        return {"error": f"Falha na mutação '{mutation_type}' (nenhuma alteração)"}
    logger.info("Nó mutate: código mutado com sucesso")
    return {"current_code": mutated, "error": None}


def test_node(state: AtenaState, core: Any) -> Dict[str, Any]:
    """Nó de teste: avalia o código mutado e atualiza o estado."""
    code = state["current_code"]
    evaluation = evaluate_in_sandbox.invoke({"code": code, "core": core})
    score = evaluation.get("score", 0.0)
    valid = evaluation.get("valid", False)
    min_delta = getattr(Config, "MIN_IMPROVEMENT_DELTA", 0.001) if HAS_ATENA_ENGINE else 0.001

    replaced = valid and score > state["best_score"] + min_delta
    best_code = code if replaced else state["best_code"]
    best_score = score if replaced else state["best_score"]

    if replaced:
        logger.info(f"Nó test: nova melhor pontuação {score:.2f} (antes {state['best_score']:.2f})")

    return {
        "generation": state["generation"] + 1,
        "best_score": best_score,
        "best_code": best_code,
        "last_score": score,
        "replaced": replaced,
        "error": None,
        "messages": [AIMessage(content=f"Score: {score:.2f} | {'Aceita' if replaced else 'Rejeitada'}")],
    }


def should_continue(state: AtenaState) -> str:
    """Decide se o grafo deve continuar evoluindo ou terminar."""
    if state.get("replaced", False) and state["best_score"] < 95.0:
        return "mutate"
    return END


# =============================================================================
# 4. CONSTRUÇÃO DO GRAFO
# =============================================================================

def create_atena_graph(core: Any):
    """Cria o grafo LangGraph que orquestra o ciclo de evolução."""
    if not HAS_LANGCHAIN:
        logger.warning("LangGraph não disponível — create_atena_graph retorna None")
        return None

    graph = StateGraph(AtenaState)
    graph.add_node("think", lambda state: think_node(state, core))
    graph.add_node("mutate", lambda state: mutate_node(state, core))
    graph.add_node("test", lambda state: test_node(state, core))
    graph.set_entry_point("think")
    graph.add_edge("think", "mutate")
    graph.add_edge("mutate", "test")
    graph.add_conditional_edges("test", should_continue)
    return graph.compile()


# =============================================================================
# 5. EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":
    core = AtenaCore()
    initial_state: AtenaState = {
        "messages": [],
        "generation": 0,
        "current_code": core.current_code,
        "best_code": core.current_code,
        "best_score": core.best_score,
        "problem_name": core.problem.name if core.problem else None,
        "problem_description": core.problem.description if core.problem else None,
        "mutation_history": [],
        "last_mutation": None,
        "last_score": core.best_score,
        "replaced": False,
        "error": None,
    }
    app = create_atena_graph(core)
    if app:
        final_state = app.invoke(initial_state)
        logger.info(f"Evolução concluída. Melhor score: {final_state['best_score']:.2f}")
    else:
        logger.warning("Grafo não criado — LangGraph indisponível")
