"""
🔱 ATENA Ω — Fixtures compartilhadas para testes pytest (v4.0)

Hierarquia de fixtures:
  Infra:     temp_dir, tmp_db, tmp_config
  Mocks LLM: mock_llm_response, mock_openai_client, mock_grok_response
  Mocks KB:  mock_kb, mock_state_file
  Core:      fake_evaluator, fake_sandbox, fake_mutation_engine
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Infra
# =============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """Usa SelectorEventLoop no Windows para compatibilidade."""
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Diretório temporário isolado por teste."""
    with tempfile.TemporaryDirectory(prefix="atena_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tmp_db(temp_dir: Path) -> sqlite3.Connection:
    """Banco SQLite em memória com schema básico para testes rápidos."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    # Tabelas mínimas para não quebrar imports de KnowledgeBase
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS learned_functions (
            id INTEGER PRIMARY KEY, source TEXT, function_name TEXT,
            code TEXT, hash TEXT UNIQUE, complexity REAL, lines INTEGER,
            first_seen TEXT, last_used TEXT, usage_count INTEGER DEFAULT 0,
            embedding BLOB, purpose TEXT
        );
        CREATE TABLE IF NOT EXISTS objectives (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT,
            weight REAL DEFAULT 1.0, current_value REAL, target_value REAL,
            active BOOLEAN DEFAULT 1, created TEXT, last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS evolution_metrics (
            id INTEGER PRIMARY KEY, timestamp TEXT, generation INTEGER,
            mutation TEXT, old_score REAL, new_score REAL,
            replaced BOOLEAN, features TEXT, test_results TEXT
        );
        CREATE TABLE IF NOT EXISTS eval_cache (
            code_hash TEXT PRIMARY KEY, result_json TEXT, created TEXT
        );
        CREATE TABLE IF NOT EXISTS lang_vocabulary (
            word TEXT PRIMARY KEY, frequency INTEGER DEFAULT 1, last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS episodic_memory (
            id INTEGER PRIMARY KEY, generation INTEGER, timestamp TEXT,
            mutation TEXT, score REAL, score_delta REAL, replaced INTEGER,
            complexity REAL, num_functions INTEGER, lines INTEGER,
            code_snapshot TEXT, context_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS episodic_patterns (
            id INTEGER PRIMARY KEY, pattern TEXT UNIQUE,
            occurrences INTEGER DEFAULT 1, avg_delta REAL, last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS scorer_population (
            id TEXT PRIMARY KEY, source_code TEXT, generation INTEGER,
            fitness REAL DEFAULT 0, long_term_score REAL DEFAULT 0,
            applied_count INTEGER DEFAULT 0, created_at TEXT, active INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS checker_rules (
            name TEXT PRIMARY KEY, pattern TEXT, rule_type TEXT,
            active INTEGER DEFAULT 1, confidence REAL DEFAULT 1.0,
            false_positive_rate REAL DEFAULT 0.0, description TEXT,
            mutable INTEGER DEFAULT 1, created_at TEXT, last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS checker_block_history (
            id INTEGER PRIMARY KEY, rule_name TEXT, code_hash TEXT,
            was_false_positive INTEGER DEFAULT 0, timestamp TEXT
        );
        CREATE TABLE IF NOT EXISTS reward_history (
            id INTEGER PRIMARY KEY, generation INTEGER, timestamp TEXT,
            base_score REAL, custom_score REAL, criteria_scores TEXT
        );
        CREATE TABLE IF NOT EXISTS meta_causal_models (
            mutation_type TEXT PRIMARY KEY, conditions_json TEXT,
            anti_conditions_json TEXT, causal_chain_json TEXT,
            confidence REAL, sample_count INTEGER, last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS meta_rule_fitness (
            rule_name TEXT PRIMARY KEY, fitness REAL,
            last_updated TEXT, description TEXT
        );
        CREATE TABLE IF NOT EXISTS meta_hypotheses (
            id INTEGER PRIMARY KEY, hypothesis TEXT,
            evidence_for INTEGER DEFAULT 0, evidence_against INTEGER DEFAULT 0,
            confirmed INTEGER DEFAULT 0, created TEXT, last_tested TEXT
        );
        CREATE TABLE IF NOT EXISTS intelligence_snapshots (
            id INTEGER PRIMARY KEY, timestamp TEXT, generation INTEGER,
            best_score REAL, score_delta REAL, stagnation_cycles INTEGER,
            adaptive_delta REAL, vocabulary_size INTEGER,
            curiosity_topics INTEGER, rlhf_patterns INTEGER,
            success_ratio REAL, replaced INTEGER
        );
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_state_file(temp_dir: Path) -> Path:
    """Arquivo de estado JSON com valores iniciais válidos."""
    state_file = temp_dir / "atena_state.json"
    state_file.write_text(json.dumps({
        "generation":  0,
        "best_score":  0.0,
        "timestamp":   "2026-01-01T00:00:00",
        "is_ci":       True,
    }, indent=2))
    return state_file


@pytest.fixture
def tmp_config(temp_dir: Path) -> Dict[str, Any]:
    """Configuração mínima com caminhos temporários para testes."""
    dirs = {
        "BASE_DIR":     temp_dir / "atena_evolution",
        "CODE_DIR":     temp_dir / "atena_evolution" / "code",
        "BACKUP_DIR":   temp_dir / "atena_evolution" / "backups",
        "KNOWLEDGE_DIR": temp_dir / "atena_evolution" / "knowledge",
        "SANDBOX_DIR":  temp_dir / "atena_evolution" / "sandbox",
        "MODEL_DIR":    temp_dir / "atena_evolution" / "models",
        "LOG_DIR":      temp_dir / "atena_evolution" / "logs",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return {
        **dirs,
        "CURRENT_CODE_FILE": dirs["CODE_DIR"] / "atena_current.py",
        "STATE_FILE": temp_dir / "atena_state.json",
        "KNOWLEDGE_DB": dirs["KNOWLEDGE_DIR"] / "knowledge.db",
        "EVALUATION_TIMEOUT": 5,
        "PARALLEL_WORKERS": 1,
        "CANDIDATES_PER_CYCLE": 1,
    }


# =============================================================================
# Mock LLM / API responses
# =============================================================================

@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Resposta padrão de LLM (compatível com formato OpenAI/Grok)."""
    return {
        "id": "chatcmpl-test-atena-001",
        "object": "chat.completion",
        "created": 1713100000,
        "model": "grok-4-1-fast",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "def test_function(a: int, b: int) -> int:\n    return a + b\n",
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        },
    }


@pytest.fixture
def mock_grok_response(mock_llm_response: Dict) -> MagicMock:
    """GrokGenerator com API mockada para não fazer chamadas reais."""
    mock = MagicMock()
    mock.api_key = "xai-test-key-0000"
    mock.generate_function.return_value = (
        "def soma(a: int, b: int) -> int:\n    return a + b\n"
    )
    mock.generate_optimized_function.return_value = (
        "def soma(a: int, b: int) -> int:\n    return a + b  # otimizado\n"
    )
    return mock


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Cliente OpenAI/Grok totalmente mockado."""
    client = MagicMock()

    async def _create(*args, **kwargs):
        return AsyncMock(
            choices=[AsyncMock(
                message=AsyncMock(content="def resp(x): return x"),
                finish_reason="stop",
            )],
            usage=AsyncMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    client.chat.completions.create = _create
    return client


# =============================================================================
# Mock Sandbox & Evaluator
# =============================================================================

@pytest.fixture
def fake_sandbox() -> MagicMock:
    """Sandbox que retorna sucesso sem executar subprocesso."""
    sb = MagicMock()
    sb.run.return_value = (True, "PASS: test passed\n", 0.05)
    return sb


@pytest.fixture
def fake_evaluator() -> MagicMock:
    """CodeEvaluator que retorna resultado fixo sem sandbox real."""
    ev = MagicMock()
    ev.evaluate.return_value = {
        "valid":       True,
        "syntax_error": None,
        "runtime_error": None,
        "execution_time": 0.05,
        "lines":       30,
        "complexity":  2.0,
        "num_functions": 5,
        "comment_ratio": 0.1,
        "tests":       {},
        "tests_passed": 0,
        "tests_total":  0,
        "coverage":    0.0,
        "score":       55.0,
    }
    return ev


@pytest.fixture
def sample_python_code() -> str:
    """Código Python válido e simples para usar em testes de mutação."""
    return '''#!/usr/bin/env python3
"""Módulo de utilitários para testes."""

def main() -> int:
    """Ponto de entrada principal."""
    resultado = util_soma(3, 4)
    fatorial  = util_fatorial(5)
    print(f"Soma: {resultado}, Fatorial: {fatorial}")
    return 0

def util_soma(a: int, b: int) -> int:
    """Soma dois números."""
    return a + b

def util_fatorial(n: int) -> int:
    """Fatorial iterativo de n."""
    resultado = 1
    for i in range(2, n + 1):
        resultado *= i
    return resultado

def util_fibonacci(n: int) -> int:
    """n-ésimo Fibonacci em O(n)."""
    if n <= 0: return 0
    if n == 1: return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def util_eh_primo(n: int) -> bool:
    """Teste de primalidade em O(√n)."""
    if n < 2: return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

if __name__ == "__main__":
    raise SystemExit(main())
'''


# =============================================================================
# Helpers para testes assíncronos
# =============================================================================

@pytest.fixture
def run_async():
    """Executa coroutine dentro de um event loop isolado."""
    def _runner(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return _runner


# =============================================================================
# Markers de performance (para benchmarks)
# =============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: teste lento (>1s)")
    config.addinivalue_line("markers", "integration: teste de integração")
    config.addinivalue_line("markers", "unit: teste unitário")
    config.addinivalue_line("markers", "security: teste de segurança")
    config.addinivalue_line("markers", "performance: benchmark de performance")
    config.addinivalue_line("markers", "smoke: smoke test rápido")
