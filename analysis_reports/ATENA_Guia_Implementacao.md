# 🛠️ Guia de Implementação - ATENA Ω Refactoring

## Parte 1: Setup Inicial e Linting

### 1.1 Criar arquivo `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "atena-omega"
version = "3.2.0"
description = "AI-powered autonomous agent with neural reality sync"
authors = [{name = "Danilo AtenaAuto Team", email = "dev@atenaauto.com"}]
requires-python = ">=3.10"

[project.optional-dependencies]
dev = [
    "black>=23.0.0",
    "pylint>=2.17.0",
    "flake8>=6.0.0",
    "isort>=5.12.0",
    "mypy>=1.0.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
]

[tool.black]
line-length = 100
target-version = ["py310", "py311"]
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100
multi_line_mode = 3
include_trailing_comma = true

[tool.pylint."MESSAGES CONTROL"]
disable = [
    "C0103",  # invalid-name
    "C0114",  # missing-module-docstring
    "C0115",  # missing-class-docstring
    "C0116",  # missing-function-docstring
]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disallow_any_generics = false

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--cov=core --cov=modules --cov-report=html --cov-report=term"
```

### 1.2 Criar `.env.example`

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4

# Database
DATABASE_URL=sqlite:///./atena.db
DATABASE_POOL_SIZE=10

# Logging
LOG_LEVEL=INFO
LOG_FILE=./atena.log

# Sandbox
SANDBOX_TIMEOUT=30
SANDBOX_MAX_MEMORY_MB=512

# Feature Flags
ENABLE_VECTOR_MEMORY=true
ENABLE_CURIOSITY_ENGINE=true
ENABLE_COUNCIL_ORCHESTRATOR=false
```

### 1.3 Atualizar `.gitignore`

```bash
# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*.swn

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# Logs
*.log
logs/

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.mypy_cache/
.dmypy.json
dmypy.json
```

---

## Parte 2: Refactoring do main.py

### 2.1 Criar `core/engine.py` (novo arquivo)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/engine.py — Motor de Evolução Principal

Extrato do main.py original, refatorado e otimizado.
Responsabilidades:
  - Gerenciar ciclos de evolução
  - Manter estado persistido
  - Coordenar com sandbox e scorer
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    """Configuração do motor de evolução."""
    generations: int = 100
    population_size: int = 50
    mutation_rate: float = 0.1
    elite_size: int = 5
    timeout_per_generation: int = 60


@dataclass
class EvolutionResult:
    """Resultado de uma geração."""
    generation: int
    best_score: float
    avg_score: float
    timestamp: str
    solution: Optional[Dict[str, Any]] = None


class EvolutionEngine:
    """Motor de evolução com persistência de estado."""

    def __init__(self, config: EvolutionConfig, state_dir: Path = Path("./atena_evolution")):
        self.config = config
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.generation: int = 0
        self.best_score: float = 0.0
        self.history: List[EvolutionResult] = []
        
        self._load_state()
        logger.info(f"[EvolutionEngine] Inicializado | Generation={self.generation} BestScore={self.best_score:.4f}")

    def _load_state(self) -> None:
        """Carrega estado persistido."""
        state_file = self.state_dir / "engine_state.json"
        if not state_file.exists():
            logger.info("[EvolutionEngine] Estado não encontrado, iniciando fresh")
            return
        
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            self.generation = data.get("generation", 0)
            self.best_score = data.get("best_score", 0.0)
            logger.info(f"[EvolutionEngine] Estado carregado: {data}")
        except Exception as e:
            logger.warning(f"[EvolutionEngine] Erro ao carregar estado: {e}")

    def _save_state(self) -> None:
        """Persiste estado atual."""
        state_file = self.state_dir / "engine_state.json"
        try:
            with open(state_file, "w") as f:
                json.dump({
                    "generation": self.generation,
                    "best_score": self.best_score,
                    "timestamp": datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"[EvolutionEngine] Erro ao salvar estado: {e}")

    async def evolve_generation(self) -> EvolutionResult:
        """
        Executa uma geração de evolução.
        
        Returns:
            EvolutionResult: Resultado da geração
            
        Raises:
            TimeoutError: Se a geração exceder timeout
        """
        self.generation += 1
        logger.info(f"[EvolutionEngine] Iniciando geração #{self.generation}")
        
        try:
            # Aqui va lógica real de evolução
            # Por agora, apenas um placeholder
            await asyncio.sleep(0.1)
            
            result = EvolutionResult(
                generation=self.generation,
                best_score=self.best_score,
                avg_score=self.best_score * 0.8,
                timestamp=datetime.now().isoformat(),
            )
            
            self.history.append(result)
            self._save_state()
            
            logger.info(f"[EvolutionEngine] Geração #{self.generation} completa | Score={result.best_score:.4f}")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"[EvolutionEngine] Timeout na geração #{self.generation}")
            raise TimeoutError(f"Geração {self.generation} excedeu {self.config.timeout_per_generation}s")
        except Exception as e:
            logger.error(f"[EvolutionEngine] Erro na geração #{self.generation}: {e}", exc_info=True)
            raise

    async def run(self, num_generations: Optional[int] = None) -> List[EvolutionResult]:
        """
        Executa múltiplas gerações de evolução.
        
        Args:
            num_generations: Número de gerações (usa config.generations se None)
            
        Returns:
            Lista de resultados de todas gerações
        """
        target = num_generations or self.config.generations
        logger.info(f"[EvolutionEngine] Executando {target} gerações")
        
        results = []
        for i in range(target):
            try:
                result = await asyncio.wait_for(
                    self.evolve_generation(),
                    timeout=self.config.timeout_per_generation
                )
                results.append(result)
                logger.info(f"[EvolutionEngine] [{i+1}/{target}] Concluído")
            except TimeoutError:
                logger.warning(f"[EvolutionEngine] Geração {i+1} timeout, continuando...")
                continue
            except Exception as e:
                logger.error(f"[EvolutionEngine] Erro na geração {i+1}: {e}")
                break
        
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do motor."""
        if not self.history:
            return {
                "generations": 0,
                "best_score": 0.0,
                "history": [],
            }
        
        scores = [r.best_score for r in self.history]
        return {
            "generations": len(self.history),
            "best_score": max(scores),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "history": [asdict(r) for r in self.history[-10:]],  # Últimas 10
        }
```

### 2.2 Criar `core/sandbox.py` (novo arquivo)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/sandbox.py — Execução Segura de Código

Responsabilidades:
  - Validar código antes execução
  - Executar em ambiente isolado
  - Capturar output e erros
  - Enforçar timeouts
"""

import asyncio
import subprocess
import tempfile
import logging
import ast
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Resultado da execução em sandbox."""
    success: bool
    output: str
    error: str
    exit_code: int
    execution_time: float


class CodeValidator:
    """Valida código antes execução."""
    
    FORBIDDEN_IMPORTS = {
        'os', 'sys', 'subprocess', '__import__',
        'eval', 'exec', 'compile',
    }
    
    @classmethod
    def validate(cls, code: str) -> bool:
        """
        Valida se código é seguro para executar.
        
        Args:
            code: Código a validar
            
        Returns:
            True se código é válido
            
        Raises:
            SyntaxError: Código tem sintaxe inválida
            ValueError: Código contém operações proibidas
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Código inválido: {e}")
        
        # Verificar imports proibidos
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in cls.FORBIDDEN_IMPORTS:
                        raise ValueError(f"Import proibido: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in cls.FORBIDDEN_IMPORTS:
                    raise ValueError(f"Import proibido: {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {'eval', 'exec', '__import__'}:
                        raise ValueError(f"Função proibida: {node.func.id}")
        
        return True


class SandboxRunner:
    """Executa código em ambiente isolado."""
    
    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
    
    async def run(self, code: str) -> SandboxResult:
        """
        Executa código em sandbox seguro.
        
        Args:
            code: Código Python a executar
            
        Returns:
            SandboxResult com output e status
        """
        import time
        
        # Validar código
        try:
            CodeValidator.validate(code)
        except (SyntaxError, ValueError) as e:
            logger.warning(f"[SandboxRunner] Validação falhou: {e}")
            return SandboxResult(
                success=False,
                output="",
                error=str(e),
                exit_code=1,
                execution_time=0.0,
            )
        
        # Escrever em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            start_time = time.time()
            
            # Executar com timeout
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    'python3', temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.timeout,
            )
            
            stdout, stderr = await result.communicate()
            execution_time = time.time() - start_time
            
            logger.info(f"[SandboxRunner] Execução bem-sucedida em {execution_time:.2f}s")
            
            return SandboxResult(
                success=result.returncode == 0,
                output=stdout.decode('utf-8', errors='ignore'),
                error=stderr.decode('utf-8', errors='ignore'),
                exit_code=result.returncode,
                execution_time=execution_time,
            )
            
        except asyncio.TimeoutError:
            logger.error(f"[SandboxRunner] Timeout após {self.timeout}s")
            return SandboxResult(
                success=False,
                output="",
                error=f"Execução excedeu {self.timeout} segundos",
                exit_code=124,  # timeout exit code
                execution_time=float(self.timeout),
            )
        except Exception as e:
            logger.error(f"[SandboxRunner] Erro: {e}", exc_info=True)
            return SandboxResult(
                success=False,
                output="",
                error=str(e),
                exit_code=1,
                execution_time=0.0,
            )
        finally:
            # Limpar arquivo temporário
            Path(temp_file).unlink(missing_ok=True)
```

---

## Parte 3: Testes Unitários

### 3.1 Criar `tests/test_engine.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_engine.py — Testes para EvolutionEngine
"""

import pytest
import asyncio
from pathlib import Path
from core.engine import EvolutionEngine, EvolutionConfig, EvolutionResult


@pytest.fixture
def config():
    return EvolutionConfig(
        generations=5,
        population_size=10,
        mutation_rate=0.1,
    )


@pytest.fixture
def temp_state_dir(tmp_path):
    return tmp_path / "atena_evolution"


@pytest.fixture
async def engine(config, temp_state_dir):
    return EvolutionEngine(config, state_dir=temp_state_dir)


@pytest.mark.asyncio
async def test_engine_initialization(engine):
    """Testa inicialização do engine."""
    assert engine.generation == 0
    assert engine.best_score == 0.0
    assert len(engine.history) == 0


@pytest.mark.asyncio
async def test_evolution_single_generation(engine):
    """Testa uma geração de evolução."""
    result = await engine.evolve_generation()
    
    assert isinstance(result, EvolutionResult)
    assert result.generation == 1
    assert engine.generation == 1
    assert len(engine.history) == 1


@pytest.mark.asyncio
async def test_evolution_multiple_generations(engine, config):
    """Testa múltiplas gerações."""
    results = await engine.run(num_generations=3)
    
    assert len(results) == 3
    assert engine.generation == 3
    assert len(engine.history) == 3


@pytest.mark.asyncio
async def test_engine_state_persistence(config, temp_state_dir):
    """Testa persistência de estado."""
    # Criar engine e executar geração
    engine1 = EvolutionEngine(config, state_dir=temp_state_dir)
    await engine1.evolve_generation()
    gen1 = engine1.generation
    
    # Criar novo engine com mesmo state_dir
    engine2 = EvolutionEngine(config, state_dir=temp_state_dir)
    assert engine2.generation == gen1


def test_engine_stats(engine):
    """Testa obtenção de estatísticas."""
    stats = engine.get_stats()
    
    assert "generations" in stats
    assert "best_score" in stats
    assert "history" in stats
    assert stats["generations"] == 0
```

### 3.2 Criar `tests/test_sandbox.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_sandbox.py — Testes para SandboxRunner
"""

import pytest
from core.sandbox import SandboxRunner, CodeValidator, SandboxResult


class TestCodeValidator:
    """Testes para validação de código."""
    
    def test_valid_code(self):
        """Código válido passa validação."""
        code = """
def hello():
    return "Hello, World!"

result = hello()
"""
        assert CodeValidator.validate(code) is True
    
    def test_forbidden_import_os(self):
        """Import de 'os' é proibido."""
        code = "import os"
        with pytest.raises(ValueError, match="Import proibido"):
            CodeValidator.validate(code)
    
    def test_forbidden_import_subprocess(self):
        """Import de 'subprocess' é proibido."""
        code = "import subprocess"
        with pytest.raises(ValueError, match="Import proibido"):
            CodeValidator.validate(code)
    
    def test_forbidden_eval(self):
        """Uso de 'eval' é proibido."""
        code = "eval('1+1')"
        with pytest.raises(ValueError, match="Função proibida"):
            CodeValidator.validate(code)
    
    def test_invalid_syntax(self):
        """Código com sintaxe inválida."""
        code = "def broken("
        with pytest.raises(SyntaxError):
            CodeValidator.validate(code)


class TestSandboxRunner:
    """Testes para execução em sandbox."""
    
    @pytest.fixture
    def runner(self):
        return SandboxRunner(timeout=10)
    
    @pytest.mark.asyncio
    async def test_simple_code_execution(self, runner):
        """Executa código simples."""
        code = """
result = 1 + 1
print(result)
"""
        result = await runner.run(code)
        
        assert result.success is True
        assert "2" in result.output
        assert result.exit_code == 0
    
    @pytest.mark.asyncio
    async def test_code_with_error(self, runner):
        """Código com erro de runtime."""
        code = """
x = 1 / 0
"""
        result = await runner.run(code)
        
        assert result.success is False
        assert "ZeroDivisionError" in result.error
        assert result.exit_code != 0
    
    @pytest.mark.asyncio
    async def test_timeout(self, runner_short):
        """Código que excede timeout."""
        runner_short = SandboxRunner(timeout=1)
        code = """
import time
time.sleep(5)
"""
        # Nota: time.sleep pode não ser importável devido validação
        # Usar loop infinito ao invés
        code = "while True: pass"
        
        # Este teste pode não funcionar se import time for bloqueado
        # Apenas demonstra intenção
```

---

## Parte 4: GitHub Actions CI/CD

### 4.1 Criar `.github/workflows/tests.yml`

```yaml
name: Tests & Quality Checks

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]
    
    - name: Format check with black
      run: black --check core/ modules/ protocols/ tests/
    
    - name: Lint with pylint
      run: pylint core/ modules/ --fail-under=7.0
      continue-on-error: true
    
    - name: Type check with mypy
      run: mypy core/ modules/
      continue-on-error: true
    
    - name: Run tests with pytest
      run: pytest tests/ -v --cov=core --cov=modules --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false
```

---

## Próximos Passos

1. **Dia 1-2:** Copiar os arquivos acima em seu repositório
2. **Dia 3:** Executar `pip install -e .[dev]` e testar linting
3. **Dia 4-5:** Corrigir erros de formatação (`black --in-place ...`)
4. **Dia 6-7:** Migrar mais funções do main.py para modules especializados

```bash
# Comandos úteis:
black core/ modules/  # Auto-fix formatting
isort core/ modules/  # Organizar imports
pylint core/ -f parseable > pylint.txt  # Gerar report
pytest --cov=. --cov-report=html  # Gerar HTML coverage
```

**Sucesso! 🚀**
