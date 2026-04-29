"""
Configuração de fixtures compartilhadas para testes pytest.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, AsyncMock

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Cria diretório temporário para testes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_state_file(temp_dir: Path) -> Path:
    """Cria arquivo de estado mock."""
    state_file = temp_dir / "state.json"
    state_data = {
        "generation": 0,
        "best_score": 0.0,
        "timestamp": "2026-04-14T00:00:00"
    }
    state_file.write_text(json.dumps(state_data, indent=2))
    return state_file


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Mock de resposta de LLM."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1713100000,
        "model": "gpt-4-turbo-preview",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Esta é uma resposta de teste do LLM."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }


@pytest.fixture
def mock_openai_client():
    """Mock do cliente OpenAI."""
    client = MagicMock()
    
    # Mock para chat.completions.create
    async def mock_create(*args, **kwargs):
        return AsyncMock(
            choices=[
                AsyncMock(
                    message=AsyncMock(content="Resposta de teste"),
                    finish_reason="stop"
                )
            ],
            usage=AsyncMock(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30
            )
        )
    
    client.chat.completions.create = mock_create
    return client


@pytest.fixture
def mock_evolution_config() -> Dict[str, Any]:
    """Configuração mock para engine de evolução."""
    return {
        "population_size": 10,
        "mutation_rate": 0.1,
        "crossover_rate": 0.7,
        "max_generations": 100,
        "timeout": 30,
        "sandbox_enabled": True
    }


@pytest.fixture
def sample_code_valid() -> str:
    """Código Python válido para testes."""
    return '''
def add(a: int, b: int) -> int:
    """Soma dois números."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiplica dois números."""
    return a * b

# Teste
result = add(2, 3)
assert result == 5
'''


@pytest.fixture
def sample_code_invalid() -> str:
    """Código Python inválido (malicioso) para testes."""
    return '''
import os
import subprocess

# Tentativa de execução perigosa
os.system('rm -rf /')
subprocess.run(['curl', 'http://malicious.com'])
exec('print("danger")')
'''


@pytest.fixture
def mock_database_connection(temp_dir: Path):
    """Mock de conexão com banco de dados."""
    import sqlite3
    
    db_path = temp_dir / "test.db"
    conn = sqlite3.connect(str(db_path))
    
    # Criar tabelas de teste
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY,
            generation INTEGER,
            score REAL,
            timestamp TEXT,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE INDEX idx_generation ON results(generation)
    ''')
    conn.commit()
    
    yield conn
    
    conn.close()


@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes assíncronos."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_cache():
    """Mock de sistema de cache."""
    cache = {}
    
    class MockCache:
        def get(self, key: str) -> Any:
            return cache.get(key)
        
        def set(self, key: str, value: Any, ttl: int = 3600) -> None:
            cache[key] = value
        
        def delete(self, key: str) -> None:
            cache.pop(key, None)
        
        def clear(self) -> None:
            cache.clear()
    
    return MockCache()


@pytest.fixture
def mock_logger():
    """Mock de logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    logger.critical = MagicMock()
    return logger


@pytest.fixture
def sample_mission_config() -> Dict[str, Any]:
    """Configuração de missão para testes."""
    return {
        "mission_type": "test_mission",
        "timeout": 60,
        "priority": "high",
        "params": {
            "query": "Teste de missão",
            "max_iterations": 5
        },
        "validators": ["syntax", "security"],
        "callbacks": []
    }


# Hooks do pytest
def pytest_configure(config):
    """Configuração inicial do pytest."""
    config.addinivalue_line(
        "markers", "slow: marca testes lentos"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integração"
    )
    config.addinivalue_line(
        "markers", "unit: marca testes unitários"
    )


def pytest_collection_modifyitems(config, items):
    """Modifica items coletados."""
    for item in items:
        # Adiciona marker 'unit' por padrão se estiver em tests/unit/
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        # Adiciona marker 'integration' se estiver em tests/integration/
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


def pytest_pyfunc_call(pyfuncitem):
    """Executa testes async mesmo sem plugin pytest-asyncio."""
    test_func = pyfuncitem.obj
    if not asyncio.iscoroutinefunction(test_func):
        return None

    loop = pyfuncitem.funcargs.get("event_loop")
    if loop is None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(test_func(**pyfuncitem.funcargs))
        finally:
            loop.close()
        return True

    loop.run_until_complete(test_func(**pyfuncitem.funcargs))
    return True
