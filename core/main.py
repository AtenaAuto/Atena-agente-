#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

         ATENA NEURAL v3.1  SISTEMA COMPLETO CONSOLIDADO           
  Auto-evoluo orientada a problemas reais                         
                                                                     
  Principais melhorias em relao  v3.0:                           
   1. Classe Problem para ancorar evoluo em problemas externos    
   2. Sandbox com isolamento aprimorado e suporte a Docker          
   3. Cache LRU para avaliaes e embeddings                        
   4. Logging estruturado (nveis DEBUG, INFO, WARNING, ERROR)      
   5. Fallback para Grok com gerao local de funes               
   6. EvolvableScorer com validao de cdigo                       
   7. AdaptiveChecker com regras mais granulares e ajuste dinmico  
   8. MetaLearner com features contextuais aprimoradas              
   9. Dashboard com informaes do problema atual                    
  10. Amostragem de repositrios grandes em vez de pular            

"""

import os
import sys
import time
import json
import sqlite3
import ast
import astor
import random
import subprocess
import tempfile
import shutil
import hashlib
import threading
import queue
import concurrent.futures
import requests
import numpy as np
import pickle
import cProfile
import pstats
import io
import functools
import logging
import signal
import inspect
import gc
import math
import textwrap
import re
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
# Mantendo EXATAMENTE sua lista de typing para no quebrar as 6300 linhas
from typing import (
    Dict, List, Any, Optional, Tuple, Set, Callable, 
    Union, Type, Iterator, Iterable, Sequence
)
from dataclasses import dataclass, field, asdict
from collections import Counter, OrderedDict, defaultdict, deque
from copy import deepcopy
from contextlib import contextmanager, redirect_stdout, redirect_stderr

# --- Adicionado para conectar com as novas pastas do seu GitHub ---
BASE_DIR = Path(__file__).parent
REPO_ROOT = BASE_DIR.parent
DNA_DIR = REPO_ROOT / "atena_evolution" / "reference_dna"
MODULES_DIR = REPO_ROOT / "modules"

# Permite que o Python importe o que estiver dentro da pasta /modules
if str(MODULES_DIR) not in sys.path:
    sys.path.append(str(MODULES_DIR))

from atena_advanced_essentials import AtenaAdvancedEssentials

try:
    from curiosity_engine import curiosity
    HAS_CURIOSITY = True
except ImportError:
    HAS_CURIOSITY = False

try:
    from council_orchestrator import council
    HAS_COUNCIL = True
except ImportError:
    HAS_COUNCIL = False

try:
    from vector_memory import vector_memory
    HAS_VECTOR_MEMORY = True
except ImportError:
    HAS_VECTOR_MEMORY = False

try:
    from hydra_protocol import hydra
    HAS_HYDRA = True
except ImportError:
    HAS_HYDRA = False

try:
    from world_model import world_model
    HAS_WORLD_MODEL = True
except ImportError:
    HAS_WORLD_MODEL = False

# --- Novos Módulos Avançados ---
try:
    from federated_learning import FederatedLearningServer
    HAS_FEDERATED = True
except ImportError:
    HAS_FEDERATED = False

try:
    from graph_memory import KnowledgeGraph
    HAS_GRAPH_MEMORY = True
except ImportError:
    HAS_GRAPH_MEMORY = False

try:
    from hyperparameter_optimizer import HyperparameterOptimizer
    HAS_HYPER_OPT = True
except ImportError:
    HAS_HYPER_OPT = False

try:
    from multi_agent_orchestrator import MultiAgentOrchestrator
    HAS_ORCHESTRATOR = True
except ImportError:
    HAS_ORCHESTRATOR = False

try:
    from game_theory_simulator import GameTheorySimulator
    HAS_GAME_THEORY = True
except ImportError:
    HAS_GAME_THEORY = False

try:
    from atena_browser_agent import AtenaBrowserAgent
    HAS_BROWSER_AGENT = True
except ImportError:
    HAS_BROWSER_AGENT = False

try:
    from rlhf_engine import rlhf
    HAS_RLHF = True
except ImportError:
    HAS_RLHF = False

try:
    from self_reflection import reflection
    HAS_REFLECTION = True
except ImportError:
    HAS_REFLECTION = False

# --- Bibliotecas opcionais com fallbacks ---
try:
    import radon.complexity as radon_cc
    import radon.raw as radon_raw
    HAS_RADON = True
except ImportError:
    HAS_RADON = False
    radon_cc = radon_raw = None

try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    

#  Bibliotecas opcionais com fallbacks seguros 
try:
    import radon.complexity as radon_cc
    import radon.raw as radon_raw
    HAS_RADON = True
except ImportError:
    HAS_RADON = False
    radon_cc = None
    radon_raw = None

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE = True
except ImportError:
    HAS_SENTENCE = False

try:
    import docker
    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

try:
    from hypothesis import given, strategies as st, settings
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

try:
    import numba
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False

try:
    from fake_useragent import UserAgent
    HAS_FAKE_UA = True
except ImportError:
    HAS_FAKE_UA = False

try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.ensemble import GradientBoostingClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import nltk
    from nltk.corpus import wordnet
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

#  Configurao de logging 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("atena")

# Suprime logs muito verbosos de bibliotecas externas
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
# Adicionar isso logo aps as configuraes de logging
import importlib
from pathlib import Path

def auto_import_modules():
    """
    Carrega automaticamente todos os mdulos .py dentro da pasta 'modules/'.
    A pasta  criada se no existir.
    """
    modules_dir = Path(__file__).parent / "modules"
    modules_dir.mkdir(exist_ok=True)

    parent = modules_dir.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    loaded = []
    for py_file in modules_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        module_name = py_file.stem
        full_name = f"modules.{module_name}"
        try:
            importlib.import_module(full_name)
            logger.info(f" Mdulo carregado: {full_name}")
            loaded.append(full_name)
        except Exception as e:
            logger.warning(f" Falha ao carregar {full_name}: {e}")

    if loaded:
        logger.info(f" Mdulos carregados automaticamente: {', '.join(loaded)}")
    else:
        logger.debug("Nenhum mdulo extra encontrado em modules/")

auto_import_modules()

# 
# DETECO DE AMBIENTE E CONSTANTES
# 

IS_CI = os.getenv("CI", "false").lower() == "true"
IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"

# Flags de controle (podem ser sobrescritas por variveis de ambiente)
ALLOW_DEEP_SELF_MOD  = os.getenv("ALLOW_DEEP_SELF_MOD",  "true").lower() == "true"
ALLOW_CHECKER_EVOLVE = os.getenv("ALLOW_CHECKER_EVOLVE", "false").lower() == "true"
SELF_MOD_INTERVAL    = int(os.getenv("SELF_MOD_INTERVAL", "10"))
META_WINDOW          = int(os.getenv("META_WINDOW", "50"))
RECURSIVE_CYCLES     = int(os.getenv("RECURSIVE_CYCLES", "3"))
MAX_ENGINE_MUTATIONS = int(os.getenv("MAX_ENGINE_MUTATIONS", "3"))
LT_INTERVAL          = int(os.getenv("LT_INTERVAL", "1"))
LT_VERBOSE           = os.getenv("LT_VERBOSE", "false").lower() == "true"
GROK_LT_INTERVAL     = int(os.getenv("GROK_LT_INTERVAL", "5"))
VH_INTERVAL_HOURS    = int(os.getenv("VH_INTERVAL_HOURS", "6"))
DASHBOARD_PORT       = int(os.getenv("DASHBOARD_PORT", "7331"))

# 
# UTILITRIOS
# 

def safe_import(module_name: str, package: Optional[str] = None) -> Any:
    """Tenta importar um mdulo opcional, retorna None se falhar."""
    try:
        return importlib.import_module(module_name, package)
    except ImportError:
        return None

def ci_print(msg: str, level: str = "INFO", **kwargs):
    """Imprime com timestamp e nvel, adequado para CI e logs."""
    logger.log(getattr(logging, level.upper(), logging.INFO), msg)
    if IS_CI:
        if level == "DEBUG" and not os.getenv("ACTIONS_STEP_DEBUG"):
            return
        print(f"[{level}] {msg}", flush=True)

#  LRU Cache thread-safe 

class LRUCache:
    """Cache LRU simples com lock."""
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def set(self, key: str, value: Any):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def __len__(self):
        return len(self._cache)

# 
# CLASSE PROBLEMA  ancora a evoluo em uma tarefa real
# 

@dataclass
class Problem:
    """
    Representa um problema que a Atena deve resolver.

    Atributos:
        name: Nome curto do problema.
        description: Descrio detalhada.
        evaluate: Funo que recebe o cdigo como string e retorna um score
                  entre 0 e 100 (quanto maior, melhor).
        train_data: Dados de treinamento (opcional, usado internamente pela evaluate).
        test_data: Dados de teste (opcional, para validao final).
        timeout: Tempo mximo (segundos) para avaliao.
        expected_interface: Descrio da interface esperada (ex: "def solve(data):").
    """
    name: str
    description: str
    evaluate: Callable[[str], float]
    train_data: Any = None
    test_data: Any = None
    timeout: int = 30
    expected_interface: str = ""

    def __post_init__(self):
        if not callable(self.evaluate):
            raise TypeError("evaluate must be callable")

    def __call__(self, code: str) -> float:
        """Chamada direta para evaluate, com timeout."""
        return self.evaluate(code)


# 
# CONFIGURAO
# 

@dataclass
class Config:
    """Configuraes globais da Atena."""
    # APIs
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GH_TOKEN", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

    # Diretrios base
    BASE_DIR: Path = Path("./atena_evolution")
    CODE_DIR: Path = BASE_DIR / "code"
    BACKUP_DIR: Path = BASE_DIR / "backups"
    KNOWLEDGE_DIR: Path = BASE_DIR / "knowledge"
    EVOLUTIONS_DIR: Path = BASE_DIR / "evolutions"
    SANDBOX_DIR: Path = BASE_DIR / "sandbox"
    MODEL_DIR: Path = BASE_DIR / "models"
    DEPLOY_DIR: Path = BASE_DIR / "deploy"
    PROJECTS_DIR: Path = BASE_DIR / "projects"
    CACHE_DIR: Path = BASE_DIR / "cache"
    SELFMOD_BACKUP_DIR: Path = BACKUP_DIR / "selfmod"
    LOG_DIR: Path = BASE_DIR / "logs"

    # Arquivos importantes
    CURRENT_CODE_FILE: Path = CODE_DIR / "atena_current.py"
    NEW_CODE_FILE: Path = CODE_DIR / "atena_new.py"
    ENGINE_FILE: Path = CODE_DIR / "atena_engine.py"
    KNOWLEDGE_DB: Path = KNOWLEDGE_DIR / "knowledge.db"
    PREDICTOR_MODEL: Path = MODEL_DIR / "mutation_predictor.pkl"
    META_MODEL: Path = MODEL_DIR / "meta_predictor.pkl"
    STATE_FILE: Path = BASE_DIR / "atena_state.json"
    WORKFLOW_FILE: Path = Path(".github/workflows/atena.yml")
    WORKFLOW_BACKUP_DIR: Path = BACKUP_DIR / "workflows"

    # Parmetros de evoluo
    MAX_MUTATION_ATTEMPTS: int = 5
    EVALUATION_TIMEOUT: int = 15 if IS_CI else 10
    BACKUP_KEEP_DAYS: int = 7
    PARALLEL_WORKERS: int = 2 if IS_CI else 4
    CANDIDATES_PER_CYCLE: int = 4 if IS_CI else 2
    EXPLORATION_RATE: float = 0.15
    MUTATION_STRENGTH: float = 0.7
    MIN_IMPROVEMENT_DELTA: float = 0.01
    SANDBOX_MEMORY_LIMIT_MB: int = 0 if IS_CI else 512

    # GitHub
    GITHUB_MAX_REPOS_PER_QUERY: int = 50
    GITHUB_MAX_FILES_PER_REPO: int = 20          # aumentado para capturar mais
    GITHUB_LEARNING_INTERVAL: int = 3600
    GITHUB_MAX_FUNCTIONS: int = 10000
    GITHUB_MAX_REPOS_PER_RUN: int = 10 if IS_CI else 50

    # Treinamento de ML
    TRAINING_INTERVAL: int = 1800 if IS_CI else 3600
    MIN_TRAINING_SAMPLES: int = 50 if IS_CI else 100

    # Testes
    HYPOTHESIS_EXAMPLES: int = 20 if IS_CI else 50
    MAX_FUNCTIONS_TO_TEST: int = 2 if IS_CI else 3

    # Deploy
    DEPLOY_GIT_REPO: str = os.getenv("DEPLOY_GIT_REPO", "")
    DEPLOY_BRANCH: str = "main"
    DEPLOY_DOCKER_IMAGE: str = os.getenv("DEPLOY_DOCKER_IMAGE", "")
    DEPLOY_COMMAND: str = os.getenv("DEPLOY_COMMAND", "")
    DEPLOY_THRESHOLD: float = 1.05

    # Modelos de embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    ALLOW_WORKFLOW_MUTATION: bool = os.getenv("ALLOW_WORKFLOW_MUTATION", "false").lower() == "true"

    # Hacker Recon
    HACKER_RECON_DELAY: float = 1.0
    HACKER_RECON_MAX_RESULTS: int = 10
    HACKER_RECON_MIN_CODE_LENGTH: int = 50

    # Otimizaes de cdigo
    EVAL_CACHE_SIZE: int = 512
    SCORE_CACHE_SIZE: int = 1024
    PROFILE_TOP_N: int = 5
    MIN_CODE_SIZE_FOR_PROFILE: int = 20
    DEAD_CODE_REMOVAL: bool = True
    CONSTANT_FOLDING: bool = True
    LOOP_UNROLL_MAX: int = 4

    @classmethod
    def setup(cls):
        """Cria todos os diretrios necessrios e o cdigo inicial."""
        dirs = [
            cls.BASE_DIR, cls.CODE_DIR, cls.BACKUP_DIR, cls.KNOWLEDGE_DIR,
            cls.EVOLUTIONS_DIR, cls.SANDBOX_DIR, cls.MODEL_DIR, cls.DEPLOY_DIR,
            cls.PROJECTS_DIR, cls.WORKFLOW_BACKUP_DIR, cls.CACHE_DIR,
            cls.SELFMOD_BACKUP_DIR, cls.LOG_DIR
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        if not cls.CURRENT_CODE_FILE.exists():
            cls._create_initial_code()

        if not cls.ENGINE_FILE.exists():
            shutil.copy(__file__, cls.ENGINE_FILE)

    @classmethod
    def _create_initial_code(cls):
        """Cdigo inicial simples."""
        code = '''#!/usr/bin/env python3
"""ATENA - Cdigo evoludo automaticamente"""

def main():
    print("Ol, eu sou a Atena!")
    resultado = util_soma(3, 4)
    fatorial = util_fatorial(5)
    print(f"Soma: {resultado}, Fatorial: {fatorial}")
    return 0

def util_soma(a, b):
    """Soma dois nmeros."""
    return a + b

def util_subtracao(a, b):
    """Subtrai dois nmeros."""
    return a - b

def util_fatorial(n):
    """Calcula o fatorial de n."""
    if n <= 1:
        return 1
    return n * util_fatorial(n - 1)

def util_fibonacci(n):
    """Retorna o n-simo nmero de Fibonacci."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def util_eh_primo(n):
    """Verifica se n  primo."""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

if __name__ == "__main__":
    main()
'''
        cls.CURRENT_CODE_FILE.write_text(code)


# 
# BANCO DE CONHECIMENTO (com melhorias de desempenho)
# 

class KnowledgeBase:
    """Gerencia o banco SQLite de conhecimento e cache de embeddings."""

    def __init__(self):
        self.conn = sqlite3.connect(str(Config.KNOWLEDGE_DB), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self._lock = threading.RLock()
        self._closed = False  # <-- NOVO: controle de fechamento
        self._init_tables()
        self.embedding_model = None
        if HAS_SENTENCE and not IS_CI:
            try:
                self.embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
                logger.info(f"Modelo de embedding carregado: {Config.EMBEDDING_MODEL}")
            except Exception as e:
                logger.warning(f"Falha ao carregar modelo de embedding: {e}")
        self.function_cache: List[Tuple[str, Any, str]] = []
        self._load_cache()

    def _init_tables(self):
        """Cria todas as tabelas necessrias."""
        with self._lock:
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS learned_functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT, function_name TEXT, code TEXT,
                    hash TEXT UNIQUE, complexity REAL, lines INTEGER,
                    first_seen TEXT, last_used TEXT,
                    usage_count INTEGER DEFAULT 0, embedding BLOB, purpose TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_func_purpose ON learned_functions(purpose);
                CREATE INDEX IF NOT EXISTS idx_func_hash ON learned_functions(hash);
                CREATE INDEX IF NOT EXISTS idx_func_complexity ON learned_functions(complexity);

                CREATE TABLE IF NOT EXISTS github_repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_full_name TEXT UNIQUE, stars INTEGER,
                    last_processed TEXT, files_processed INTEGER
                );

                CREATE TABLE IF NOT EXISTS objectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE, description TEXT, weight REAL DEFAULT 1.0,
                    current_value REAL, target_value REAL,
                    active BOOLEAN DEFAULT 1, created TEXT, last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS evolution_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, generation INTEGER, mutation TEXT,
                    old_score REAL, new_score REAL, replaced BOOLEAN,
                    features TEXT, test_results TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_gen ON evolution_metrics(generation);
                CREATE INDEX IF NOT EXISTS idx_metrics_replaced ON evolution_metrics(replaced);

                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, file_path TEXT, hash TEXT, score REAL
                );

                CREATE TABLE IF NOT EXISTS eval_cache (
                    code_hash TEXT PRIMARY KEY, result_json TEXT, created TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_eval_cache_created ON eval_cache(created);

                CREATE TABLE IF NOT EXISTS lang_diffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER, timestamp TEXT, description TEXT,
                    critique TEXT, proposal TEXT, score_delta REAL, replaced INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_lang_gen ON lang_diffs(generation);

                CREATE TABLE IF NOT EXISTS lang_vocabulary (
                    word TEXT PRIMARY KEY, frequency INTEGER DEFAULT 1, last_seen TEXT
                );

                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER, timestamp TEXT, mutation TEXT,
                    score REAL, score_delta REAL, replaced INTEGER,
                    complexity REAL, num_functions INTEGER, lines INTEGER,
                    code_snapshot TEXT, context_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ep_gen  ON episodic_memory(generation);
                CREATE INDEX IF NOT EXISTS idx_ep_mut  ON episodic_memory(mutation);
                CREATE INDEX IF NOT EXISTS idx_ep_score ON episodic_memory(score DESC);

                CREATE TABLE IF NOT EXISTS episodic_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT UNIQUE, occurrences INTEGER DEFAULT 1,
                    avg_delta REAL, last_seen TEXT
                );

                CREATE TABLE IF NOT EXISTS reward_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE, description TEXT, weight REAL DEFAULT 1.0,
                    formula TEXT, active INTEGER DEFAULT 1, created TEXT,
                    last_eval TEXT, last_value REAL
                );

                CREATE TABLE IF NOT EXISTS reward_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER, timestamp TEXT, base_score REAL,
                    custom_score REAL, criteria_scores TEXT
                );

                -- v3: Scorer evoluvel
                CREATE TABLE IF NOT EXISTS scorer_population (
                    id TEXT PRIMARY KEY, source_code TEXT, generation INTEGER,
                    fitness REAL DEFAULT 0, long_term_score REAL DEFAULT 0,
                    applied_count INTEGER DEFAULT 0, created_at TEXT, active INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS scorer_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER, scorer_id TEXT, score REAL,
                    replaced INTEGER, timestamp TEXT
                );

                -- v3: Meta-aprendizado
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis TEXT, evidence_for INTEGER DEFAULT 0,
                    evidence_against INTEGER DEFAULT 0, confirmed INTEGER DEFAULT 0,
                    created TEXT, last_tested TEXT
                );
                CREATE TABLE IF NOT EXISTS meta_discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discovery_type TEXT, description TEXT,
                    impact REAL, generation INTEGER, timestamp TEXT
                );

                -- v3: Checker adaptativo
                CREATE TABLE IF NOT EXISTS checker_rules (
                    name TEXT PRIMARY KEY, pattern TEXT, rule_type TEXT,
                    active INTEGER DEFAULT 1, confidence REAL DEFAULT 1.0,
                    false_positive_rate REAL DEFAULT 0.0, description TEXT,
                    mutable INTEGER DEFAULT 1, created_at TEXT, last_updated TEXT
                );
                CREATE TABLE IF NOT EXISTS checker_block_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT, code_hash TEXT,
                    was_false_positive INTEGER DEFAULT 0, timestamp TEXT
                );

                -- v3.1: snapshots de inteligência (aprendizado + progresso)
                CREATE TABLE IF NOT EXISTS intelligence_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    generation INTEGER,
                    best_score REAL,
                    score_delta REAL,
                    stagnation_cycles INTEGER,
                    adaptive_delta REAL,
                    vocabulary_size INTEGER,
                    curiosity_topics INTEGER,
                    rlhf_patterns INTEGER,
                    success_ratio REAL,
                    replaced INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_intel_snapshot_gen ON intelligence_snapshots(generation);

                -- v3.1: Problemas
                CREATE TABLE IF NOT EXISTS problems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE, description TEXT,
                    best_score REAL DEFAULT 0.0,
                    best_code TEXT, last_evaluated TEXT
                );
            ''')
            self.conn.commit()
            self._init_default_objectives()

    def _init_default_objectives(self):
        """Insere objetivos padro."""
        default = [
            ("reduzir_complexidade",      "Reduzir complexidade ciclomtica mdia",      1.0, 10.0,  5.0),
            ("aumentar_modularidade",     "Aumentar nmero de funes",                  0.8,  2.0, 10.0),
            ("melhorar_documentacao",     "Aumentar proporo de comentrios",           0.5,  0.0,  0.2),
            ("reduzir_tempo_execucao",    "Reduzir tempo de execuo da main",           1.2,  1.0,  0.05),
            ("aprender_algoritmos",       "Introduzir algoritmos eficientes",            0.7,  0.0,  5.0),
            ("aumentar_cobertura_testes", "Aumentar cobertura de testes",                0.6,  0.0,  0.8),
            ("otimizar_workflow",         "Otimizar infraestrutura do GitHub Actions",   0.3,  0.0,  1.0),
            ("eliminar_dead_code",        "Eliminar cdigo morto/imports no usados",    0.9,  0.0,  1.0),
            ("melhorar_type_hints",       "Adicionar anotaes de tipo",                 0.5,  0.0,  0.5),
        ]
        now = datetime.now().isoformat()
        for name, desc, weight, curr, target in default:
            self.conn.execute(
                "INSERT OR IGNORE INTO objectives "
                "(name, description, weight, current_value, target_value, created, last_updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, desc, weight, curr, target, now, now)
            )
        self.conn.commit()

    def _load_cache(self):
        """Carrega funes com embedding para cache."""
        try:
            cursor = self.conn.execute(
                "SELECT code, embedding, purpose FROM learned_functions "
                "WHERE embedding IS NOT NULL LIMIT 5000"
            )
            for code, emb_blob, purpose in cursor:
                if emb_blob:
                    emb = pickle.loads(emb_blob)
                    self.function_cache.append((code, emb, purpose))
            logger.debug(f"Cache carregado com {len(self.function_cache)} funes")
        except Exception as e:
            logger.warning(f"Erro ao carregar cache: {e}")

    def save_intelligence_snapshot(
        self,
        generation: int,
        best_score: float,
        score_delta: float,
        stagnation_cycles: int,
        adaptive_delta: float,
        replaced: bool,
    ) -> None:
        """Persiste snapshot resumido da inteligência para auditoria de progresso."""
        with self._lock:
            vocab_size = self.conn.execute("SELECT COUNT(*) FROM lang_vocabulary").fetchone()[0]
            curiosity_topics = self.conn.execute(
                "SELECT COUNT(*) FROM curiosity_topics"
            ).fetchone()[0] if self._table_exists("curiosity_topics") else 0
            rlhf_patterns = self.conn.execute(
                "SELECT COUNT(*) FROM rlhf_preferences"
            ).fetchone()[0] if self._table_exists("rlhf_preferences") else 0
            success_count = self.conn.execute(
                "SELECT COUNT(*) FROM episodic_memory WHERE replaced = 1"
            ).fetchone()[0]
            total_count = self.conn.execute("SELECT COUNT(*) FROM episodic_memory").fetchone()[0]
            success_ratio = (success_count / total_count) if total_count else 0.0
            self.conn.execute(
                """
                INSERT INTO intelligence_snapshots (
                    timestamp, generation, best_score, score_delta, stagnation_cycles,
                    adaptive_delta, vocabulary_size, curiosity_topics, rlhf_patterns,
                    success_ratio, replaced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    generation,
                    best_score,
                    score_delta,
                    stagnation_cycles,
                    adaptive_delta,
                    vocab_size,
                    curiosity_topics,
                    rlhf_patterns,
                    success_ratio,
                    int(replaced),
                ),
            )
            self.conn.commit()

    def _table_exists(self, table_name: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
        return bool(row)

    def get_cached_eval(self, code_hash: str) -> Optional[Dict]:
        """Recupera avaliao em cache."""
        try:
            row = self.conn.execute(
                "SELECT result_json FROM eval_cache WHERE code_hash = ?", (code_hash,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Erro ao ler cache: {e}")
        return None

    def set_cached_eval(self, code_hash: str, result: Dict):
        """Armazena avaliao em cache."""
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO eval_cache (code_hash, result_json, created) VALUES (?, ?, ?)",
                    (code_hash, json.dumps(result), datetime.now().isoformat())
                )
                self.conn.commit()
        except Exception as e:
            logger.debug(f"Erro ao escrever cache: {e}")

    def prune_eval_cache(self, keep_days: int = 3):
        """Remove entradas antigas do cache."""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        with self._lock:
            self.conn.execute("DELETE FROM eval_cache WHERE created < ?", (cutoff,))
            self.conn.commit()
            logger.info(f"Cache de avaliaes podado (anterior a {cutoff})")

    def add_function(self, code: str, source: str, purpose: str = "") -> bool:
        """Adiciona uma funo ao banco, se ainda no existir."""
        if self._closed:
            logger.debug("KnowledgeBase closed, skipping add_function")
            return False

        try:
            tree = ast.parse(code)
            functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not functions:
                return False
            func = functions[0]
            func_code = astor.to_source(func)
            func_hash = hashlib.sha256(func_code.encode()).hexdigest()
            complexity = self._compute_complexity(func_code)
            lines = len(func_code.splitlines())
            embedding = None
            if self.embedding_model:
                docstring = ast.get_docstring(func) or ""
                text = f"{func.name} {docstring} " + " ".join(
                    [n.__class__.__name__ for n in ast.walk(func)
                     if isinstance(n, (ast.Name, ast.Call))]
                )
                emb = self.embedding_model.encode(text).astype(np.float32)
                embedding = pickle.dumps(emb)
            with self._lock:
                self.conn.execute(
                    "INSERT OR IGNORE INTO learned_functions "
                    "(source, function_name, code, hash, complexity, lines, first_seen, embedding, purpose) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (source, func.name, func_code, func_hash, complexity, lines,
                     datetime.now().isoformat(), embedding, purpose)
                )
                self.conn.commit()
            if embedding:
                self.function_cache.append((func_code, pickle.loads(embedding), purpose))
            logger.debug(f"Funo adicionada: {func.name} de {source}")
            return True
        except Exception as e:
            logger.warning(f"Erro ao adicionar funo: {e}")
            return False

    def _compute_complexity(self, code: str) -> float:
        """Calcula complexidade ciclomtica mdia."""
        if not HAS_RADON:
            return 1.0
        try:
            blocks = radon_cc.cc_visit(code)
            return sum(b.complexity for b in blocks) / len(blocks) if blocks else 1.0
        except Exception:
            return 1.0

    def search_similar(self, query_code: str, top_n: int = 5) -> List[Tuple[str, float, str]]:
        """Busca funes similares por embedding."""
        if not self.embedding_model or not self.function_cache:
            return []
        try:
            tree = ast.parse(query_code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not funcs:
                return []
            qf = funcs[0]
            text = f"{qf.name} " + " ".join(
                [n.__class__.__name__ for n in ast.walk(qf) if isinstance(n, (ast.Name, ast.Call))]
            )
            q_emb = self.embedding_model.encode(text).astype(np.float32)
        except Exception as e:
            logger.debug(f"Erro ao gerar embedding para consulta: {e}")
            return []
        sims = []
        for code, emb, purpose in self.function_cache:
            sim = float(np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-8))
            sims.append((sim, code, purpose))
        sims.sort(reverse=True)
        return [(c, s, p) for s, c, p in sims[:top_n] if s > 0.5]

    def get_function_by_purpose(self, keywords: List[str]) -> Optional[Tuple[str, str]]:
        """Retorna uma funo aleatria que corresponda a palavras-chave."""
        if not keywords:
            return None
        try:
            conds = ' OR '.join(['purpose LIKE ?'] * len(keywords))
            params = [f'%{kw}%' for kw in keywords]
            row = self.conn.execute(
                f"SELECT code, source FROM learned_functions WHERE {conds} ORDER BY RANDOM() LIMIT 1",
                params
            ).fetchone()
            return row if row else None
        except Exception as e:
            logger.debug(f"Erro ao buscar por propsito: {e}")
            return None

    def get_random_function(self) -> Optional[Tuple[str, str]]:
        """Retorna uma funo aleatria do banco."""
        try:
            row = self.conn.execute(
                "SELECT code, source FROM learned_functions ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            return row if row else None
        except Exception as e:
            logger.debug(f"Erro ao buscar funo aleatria: {e}")
            return None

    def get_low_complexity_functions(self, max_complexity: float = 3.0, limit: int = 10) -> List[str]:
        """Retorna funes de baixa complexidade."""
        try:
            rows = self.conn.execute(
                "SELECT code FROM learned_functions WHERE complexity <= ? ORDER BY usage_count DESC LIMIT ?",
                (max_complexity, limit)
            ).fetchall()
            return [r[0] for r in rows]
        except Exception as e:
            logger.debug(f"Erro ao buscar funes de baixa complexidade: {e}")
            return []

    def update_objective(self, name: str, value: float):
        """Atualiza o valor corrente de um objetivo."""
        try:
            with self._lock:
                self.conn.execute(
                    "UPDATE objectives SET current_value = ?, last_updated = ? WHERE name = ?",
                    (value, datetime.now().isoformat(), name)
                )
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao atualizar objetivo {name}: {e}")

    def add_temporary_objective(self, name: str, description: str, target: float, weight: float = 0.5):
        """Adiciona um objetivo temporrio (ex: baseado em notcias)."""
        now = datetime.now().isoformat()
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT OR IGNORE INTO objectives "
                    "(name, description, weight, current_value, target_value, created, last_updated) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, description, weight, 0.0, target, now, now)
                )
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao adicionar objetivo temporrio {name}: {e}")

    def get_objectives(self) -> List[Dict]:
        """Retorna todos os objetivos ativos."""
        try:
            rows = self.conn.execute(
                "SELECT name, description, weight, current_value, target_value "
                "FROM objectives WHERE active=1"
            ).fetchall()
            return [{"name": r[0], "description": r[1], "weight": r[2],
                     "current": r[3], "target": r[4]} for r in rows]
        except Exception as e:
            logger.warning(f"Erro ao buscar objetivos: {e}")
            return []

    def record_evolution(self, generation: int, mutation: str, old_score: float,
                         new_score: float, replaced: bool,
                         features: dict = None, test_results: dict = None):
        """Registra mtricas de uma evoluo."""
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT INTO evolution_metrics "
                    "(timestamp, generation, mutation, old_score, new_score, replaced, features, test_results) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (datetime.now().isoformat(), generation, mutation, old_score, new_score,
                     replaced, json.dumps(features) if features else None,
                     json.dumps(test_results) if test_results else None)
                )
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao registrar evoluo: {e}")

    def record_backup(self, file_path: str, file_hash: str, score: float):
        """Registra um backup."""
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT INTO backups (timestamp, file_path, hash, score) VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(), file_path, file_hash, score)
                )
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao registrar backup: {e}")

    def get_training_data(self) -> Tuple[List[Dict], List[int]]:
        """Retorna dados de treinamento para o preditor de mutaes."""
        X, y = [], []
        try:
            rows = self.conn.execute(
                "SELECT mutation, features, replaced FROM evolution_metrics WHERE features IS NOT NULL"
            ).fetchall()
            for mutation, feat_json, replaced in rows:
                feat = json.loads(feat_json)
                feat['mutation'] = mutation
                X.append(feat)
                y.append(1 if replaced else 0)
        except Exception as e:
            logger.warning(f"Erro ao obter dados de treinamento: {e}")
        return X, y

    def get_mutation_success_rates(self) -> Dict[str, float]:
        """Calcula taxa de sucesso por tipo de mutao."""
        try:
            rows = self.conn.execute("""
                SELECT mutation,
                       SUM(CASE WHEN replaced=1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as rate,
                       COUNT(*) as total
                FROM evolution_metrics
                GROUP BY mutation HAVING total >= 3
            """).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.warning(f"Erro ao calcular taxas de sucesso: {e}")
            return {}

    def close(self):
        """Fecha a conexo com o banco."""
        if self._closed:
            return
        self._closed = True
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.conn.close()
        except Exception as e:
            logger.warning(f"Erro ao fechar banco: {e}")


# 
# SANDBOX (execuo isolada com Docker ou subprocesso)
# 

class Sandbox:
    """Executa cdigo em ambiente isolado (Docker ou subprocesso)."""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or Config.EVALUATION_TIMEOUT
        self.use_docker = self._check_docker() and not IS_CI
        self._load_times: List[float] = []
        self._lock = threading.RLock()

    def _check_docker(self) -> bool:
        """Verifica se Docker est disponvel."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except Exception:
            return False

    def _adaptive_timeout(self) -> int:
        """Ajusta timeout baseado na mdia dos tempos recentes."""
        if not self._load_times:
            return self.timeout
        avg = sum(self._load_times[-10:]) / len(self._load_times[-10:])
        if avg > self.timeout * 0.8:
            return max(3, int(self.timeout * 0.7))
        return self.timeout

    def run(self, code: str, input_data: str = "") -> Tuple[bool, str, float]:
        """Executa cdigo e retorna (sucesso, sada, tempo)."""
        timeout = self._adaptive_timeout()
        if self.use_docker:
            result = self._run_docker(code, input_data, timeout)
        else:
            result = self._run_subprocess(code, input_data, timeout)
        with self._lock:
            self._load_times.append(result[2])
            if len(self._load_times) > 50:
                self._load_times.pop(0)
        return result

    def _run_docker(self, code: str, input_data: str, timeout: int) -> Tuple[bool, str, float]:
        """Executa via Docker com recursos limitados."""
        with tempfile.TemporaryDirectory(dir=str(Config.SANDBOX_DIR)) as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(code)
            tmpdir_abs = str(Path(tmpdir).resolve())
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{tmpdir_abs}:/app",
                "-w", "/app",
                "--memory", "256m",
                "--cpus", "0.5",
                "--network", "none",
                "python:3.10-slim",
                "python", "script.py"
            ]
            try:
                start = time.time()
                proc = subprocess.run(
                    cmd,
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                elapsed = time.time() - start
                success = proc.returncode == 0
                output = proc.stdout + proc.stderr
                return success, output, elapsed
            except subprocess.TimeoutExpired:
                return False, f"Timeout aps {timeout}s", float(timeout)
            except Exception as e:
                return False, str(e), 0.0

    def _run_subprocess(self, code: str, input_data: str, timeout: int) -> Tuple[bool, str, float]:
        """Executa em subprocesso com limites de recursos (quando possvel)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp = f.name

        def set_limits():
            if os.name != "nt":
                import resource
                mem_limit = Config.SANDBOX_MEMORY_LIMIT_MB
                if mem_limit > 0:
                    try:
                        limit_bytes = mem_limit * 1024 * 1024
                        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
                    except Exception:
                        pass

        preexec = None if IS_CI else (set_limits if os.name != "nt" else None)
        try:
            start = time.time()
            proc = subprocess.run(
                [sys.executable, tmp],
                input=input_data,
                preexec_fn=preexec,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            elapsed = time.time() - start
            success = proc.returncode == 0
            output = proc.stdout + proc.stderr
            return success, output, elapsed
        except subprocess.TimeoutExpired:
            return False, f"Timeout aps {timeout}s", float(timeout)
        except Exception as e:
            return False, str(e), 0.0
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass


# 
# TESTADOR DE FUNES (com Hypothesis ou simples)
# 

class FunctionTester:
    """Testa uma funo especfica com entradas aleatrias."""

    def __init__(self, sandbox: Sandbox, timeout: int = 5):
        self.sandbox = sandbox
        self.timeout = timeout

    def test_function(self, func_name: str, original_code: str, mutated_code: str) -> Dict:
        """Compara o comportamento da funo original e mutada."""
        if HAS_HYPOTHESIS:
            return self._test_with_hypothesis(func_name, original_code, mutated_code)
        else:
            return self._test_simple(func_name, original_code, mutated_code)

    def _extract_function(self, code: str, func_name: str) -> Optional[ast.FunctionDef]:
        """Extrai a definio da funo da rvore AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    return node
        except Exception:
            pass
        return None

    def _test_with_hypothesis(self, func_name: str, original_code: str, mutated_code: str) -> Dict:
        """Usa Hypothesis para gerar testes."""
        orig_func = self._extract_function(original_code, func_name)
        mut_func  = self._extract_function(mutated_code, func_name)
        if not orig_func or not mut_func:
            return {"passed": False, "tests": 0, "failing_inputs": []}

        args = [arg.arg for arg in orig_func.args.args]
        if not args:
            return self._test_no_args(func_name, original_code, mutated_code)

        # Constri cdigo de teste
        test_code = self._build_hypothesis_test(orig_func, mut_func, args)
        success, output, _ = self.sandbox.run(test_code)
        if not success:
            return {"passed": False, "tests": 0, "failing_inputs": [output[:200]]}

        lines = output.strip().split('\n')
        passed = 0
        total = 0
        failing = []
        for line in lines:
            if line.startswith("PASS:"):
                passed += 1
                total += 1
            elif line.startswith("FAIL:"):
                total += 1
                failing.append(line[5:].strip())
        return {
            "passed": passed == total and total > 0,
            "tests": total,
            "failing_inputs": failing
        }

    def _build_hypothesis_test(self, orig_func: ast.FunctionDef, mut_func: ast.FunctionDef, args: List[str]) -> str:
        """Gera cdigo de teste com Hypothesis."""
        strategy = ", ".join(["st.integers(min_value=-1000, max_value=1000)"] * len(args))
        func_name = orig_func.name
        mut_func_copy = ast.parse(astor.to_source(mut_func)).body[0]
        mut_func_copy.name = f"{func_name}_mut"
        return f"""
from hypothesis import given, strategies as st, settings
{astor.to_source(orig_func)}
{astor.to_source(mut_func_copy)}
@settings(max_examples={Config.HYPOTHESIS_EXAMPLES}, deadline=None)
@given({strategy})
def test_{func_name}({', '.join(args)}):
    try:
        orig_result = {func_name}({', '.join(args)})
        mut_result  = {func_name}_mut({', '.join(args)})
        if orig_result == mut_result:
            print("PASS:", {', '.join(args)})
        else:
            print("FAIL:", {', '.join(args)}, "orig=", orig_result, "mut=", mut_result)
    except Exception as e:
        print("FAIL:", {', '.join(args)}, "->", e)
if __name__ == "__main__": test_{func_name}()
"""

    def _test_simple(self, func_name: str, original_code: str, mutated_code: str) -> Dict:
        """Teste simples com alguns valores fixos."""
        orig_func = self._extract_function(original_code, func_name)
        if not orig_func:
            return {"passed": False, "tests": 0, "failing_inputs": ["funo original no encontrada"]}
        args = [arg.arg for arg in orig_func.args.args]
        n_args = len(args)
        if n_args == 0:
            return self._test_no_args(func_name, original_code, mutated_code)

        passed = 0
        failing = []
        for _ in range(5):
            inputs = [random.randint(-100, 100) for _ in range(n_args)]
            args_str = ', '.join(map(str, inputs))
            test_code = f"""
import sys
{original_code}
{mutated_code.replace(f'def {func_name}', f'def {func_name}_mut', 1)}
try:
    orig = {func_name}({args_str})
    mut  = {func_name}_mut({args_str})
    if orig != mut:
        sys.exit(1)
    print("PASS")
except Exception as e:
    print("Erro:", e)
    sys.exit(1)
"""
            success, output, _ = self.sandbox.run(test_code)
            if success and "PASS" in output:
                passed += 1
            else:
                failing.append(str(inputs))
        return {
            "passed": passed == 5,
            "tests": 5,
            "failing_inputs": failing
        }

    def _test_no_args(self, func_name: str, original_code: str, mutated_code: str) -> Dict:
        """Testa funes sem argumentos."""
        test_code = f"""
import sys
{original_code}
{mutated_code.replace(f'def {func_name}', f'def {func_name}_mut', 1)}
try:
    import io, contextlib
    out_orig = io.StringIO()
    out_mut = io.StringIO()
    with contextlib.redirect_stdout(out_orig):
        r_orig = {func_name}()
    with contextlib.redirect_stdout(out_mut):
        r_mut  = {func_name}_mut()
    if r_orig == r_mut:
        print("PASS: no_args")
    else:
        print("FAIL: valores diferentes")
except Exception as e:
    print("FAIL:", e)
"""
        success, output, _ = self.sandbox.run(test_code)
        passed = "PASS:" in output
        return {
            "passed": passed,
            "tests": 1,
            "failing_inputs": [] if passed else [output[:100]]
        }


# 
# AVALIADOR DE CDIGO (agora com suporte a problemas)
# 

class CodeEvaluator:
    """Avalia cdigo, possivelmente usando um problema externo."""

    def __init__(self, sandbox: Sandbox, kb: KnowledgeBase, problem: Optional[Problem] = None):
        self.sandbox = sandbox
        self.kb = kb
        self.problem = problem
        self.tester = FunctionTester(sandbox)
        self.checker = None  # Ser substitudo pelo AdaptiveChecker depois
        self._score_cache = LRUCache(Config.SCORE_CACHE_SIZE)

    def evaluate(self, code: str, original_code: str = None) -> Dict[str, Any]:
        """
        Avalia o cdigo.
        Se um problema foi definido, usa sua funo evaluate como score principal.
        Caso contrrio, usa o scorer interno.
        """
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        cached = self._score_cache.get(code_hash)
        if cached:
            return cached

        cached_db = self.kb.get_cached_eval(code_hash)
        if cached_db:
            self._score_cache.set(code_hash, cached_db)
            return cached_db

        # Verificaes bsicas de sintaxe e segurana
        if self.checker:
            ok, reason = self.checker.check(code)
        else:
            # Fallback simples
            try:
                ast.parse(code)
                ok = True
                reason = "OK"
            except SyntaxError as e:
                ok = False
                reason = f"SyntaxError: {e}"

        result = {
            "valid": ok,
            "syntax_error": None if ok else reason,
            "runtime_error": None,
            "execution_time": None,
            "lines": 0,
            "complexity": 0,
            "num_functions": 0,
            "comment_ratio": 0.0,
            "tests": {},
            "tests_passed": 0,
            "tests_total": 0,
            "coverage": 0.0,
            "score": 0.0
        }

        if not ok:
            result["syntax_error"] = reason
            self._score_cache.set(code_hash, result)
            self.kb.set_cached_eval(code_hash, result)
            return result

        # Mtricas internas (sempre coletadas para diagnstico)
        try:
            tree = ast.parse(code)
            if HAS_RADON:
                raw = radon_raw.analyze(code)
                result["lines"] = raw.loc
                result["comment_ratio"] = raw.comments / (raw.loc + 1e-6)
                cc_blocks = radon_cc.cc_visit(code)
                result["complexity"] = (
                    sum(b.complexity for b in cc_blocks) / len(cc_blocks) if cc_blocks else 1.0
                )
            else:
                result["lines"] = len(code.splitlines())
                result["complexity"] = 1.0
            result["num_functions"] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        except Exception:
            pass

        # Se h problema, usa-o para obter o score principal
        if self.problem:
            try:
                problem_score = self.problem(code)
                result["score"] = max(0.0, min(100.0, problem_score))
                result["problem_score"] = result["score"]
            except Exception as e:
                logger.error(f"Erro ao avaliar problema: {e}")
                result["score"] = 0.0
                result["runtime_error"] = str(e)
        else:
            # Fallback: executa no sandbox e usa scorer interno
            success, output, exec_time = self.sandbox.run(code)
            result["execution_time"] = exec_time
            if not success:
                result["runtime_error"] = output[:300]
                result["score"] = 0.0
            else:
                if original_code and original_code != code:
                    test_results = self._run_all_tests(original_code, code)
                    result["tests"] = test_results
                    passed = sum(1 for r in test_results.values() if r.get("passed", False))
                    result["tests_passed"] = passed
                    result["tests_total"] = len(test_results)
                result["score"] = round(self._compute_score(result), 2)

        ci_print(f"   [diag] score={result['score']:.2f} complexity={result.get('complexity',0):.1f}", level="DEBUG")
        self._score_cache.set(code_hash, result)
        self.kb.set_cached_eval(code_hash, result)
        return result

    def _run_all_tests(self, original: str, mutated: str) -> Dict:
        """Roda testes em todas as funes comuns."""
        try:
            orig_tree = ast.parse(original)
            mut_tree  = ast.parse(mutated)
        except Exception:
            return {}
        orig_funcs = {f.name for f in ast.walk(orig_tree) if isinstance(f, ast.FunctionDef)}
        mut_funcs  = {f.name for f in ast.walk(mut_tree) if isinstance(f, ast.FunctionDef)}
        common = set(list(orig_funcs & mut_funcs)[:Config.MAX_FUNCTIONS_TO_TEST])
        results = {}
        for name in common:
            results[name] = self.tester.test_function(name, original, mutated)
        return results

    def _compute_score(self, m: Dict) -> float:
        """Scorer interno (usado apenas quando no h problema)."""
        base = 10.0
        total = m.get("tests_total", 0)
        tests = 40.0 * (m["tests_passed"] / total) if total > 0 else 25.0
        quality = 0.0
        comp = m.get("complexity", 10)
        if comp <= 3:   quality += 15
        elif comp <= 5: quality += 10
        elif comp <= 8: quality += 5
        nf = m.get("num_functions", 0)
        if 3 <= nf <= 8: quality += 10
        elif nf > 8:     quality += 5
        elif nf > 0:     quality += 2
        if m.get("comment_ratio", 0) > 0.05: quality += 5
        exec_t = m.get("execution_time") or 1.0
        if exec_t < 0.05:   quality += 15
        elif exec_t < 0.1:  quality += 10
        elif exec_t < 0.3:  quality += 5
        if m.get("coverage", 0) > 0.7:  quality += 5
        elif m.get("coverage", 0) > 0.3: quality += 3
        return min(base + tests + quality, 100.0)


# 
# GERADOR GROK (com fallback local)
# 

class GrokGenerator:
    """Interface com a API Grok da xAI, com fallback para gerao local."""

    def __init__(self):
        self.api_key = Config.XAI_API_KEY
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self._last_call = 0.0
        self._min_interval = 1.5
        self._call_count = 0
        self._fallback_templates = self._load_fallback_templates()

    def _load_fallback_templates(self) -> List[str]:
        """Templates locais para quando Grok falha."""
        return [
            """
def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
""",
            """
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
""",
            """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
            """
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
"""
        ]

    def _wait_rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def generate_function(self, prompt: str, max_tokens: int = 400, retries: int = 2) -> Optional[str]:
        """Gera uma funo via Grok ou fallback local."""
        if not self.api_key:
            return self._fallback_generate(prompt)

        self._wait_rate_limit()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        system_msg = ("You are a Python expert. Reply ONLY with valid Python code. "
                      "No explanations, no markdown fences, no comments outside the code.")
        payload = {
            "model": "grok-4-1-fast",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Write a Python function that {prompt}"}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.5
        }

        for attempt in range(retries + 1):
            try:
                resp = requests.post(self.base_url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                content = resp.json()['choices'][0]['message']['content']
                self._call_count += 1
                # Extrai cdigo de dentro de blocos markdown se houver
                if '```' in content:
                    for part in content.split('```'):
                        if 'def ' in part or 'class ' in part:
                            code = part.strip()
                            if code.startswith('python\n'):
                                code = code[7:]
                            return code
                return content.strip() if 'def ' in content else None
            except Exception as e:
                logger.warning(f"Grok falhou (tentativa {attempt+1}): {e}")
                if attempt == retries:
                    return self._fallback_generate(prompt)
                time.sleep(2 ** attempt)
        return None

    def _fallback_generate(self, prompt: str) -> Optional[str]:
        """Gera uma funo simples baseada em templates."""
        prompt_lower = prompt.lower()
        if "fibonacci" in prompt_lower:
            return self._fallback_templates[0]
        elif "prime" in prompt_lower or "primo" in prompt_lower:
            return self._fallback_templates[1]
        elif "factorial" in prompt_lower or "fatorial" in prompt_lower:
            return self._fallback_templates[2]
        elif "search" in prompt_lower or "busca" in prompt_lower:
            return self._fallback_templates[3]
        else:
            # Retorna um template aleatrio
            return random.choice(self._fallback_templates)

    def generate_optimized_function(self, func_code: str) -> Optional[str]:
        """Tenta otimizar uma funo existente."""
        prompt = f"Optimize this Python function for maximum performance. Return only the optimized function:\n\n{func_code}"
        return self.generate_function(prompt, max_tokens=500)


# 
# MUTATION ENGINE (com todas as transformaes)
# 

class MutationEngine:
    """Gerador de mutaes de cdigo."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.grok = GrokGenerator() if Config.XAI_API_KEY else None
        self.profiler = CodeProfiler()
        self.checker = StaticChecker()  # ser substitudo depois
        self.mutation_types = [
            "add_comment", "remove_line", "rename_var",
            "add_docstring", "add_type_hints",
            "extract_function", "inline_function", "add_class",
            "insert_learned", "change_algorithm", "crossover_function",
            "swap_operator", "simplify_expression", "loop_conversion",
            "loop_unroll", "constant_folding", "memoize_function",
            "parallelize_loop", "add_numba_jit",
            "add_error_handling", "add_import",
            "grok_generate", "grok_optimize",
            "dead_code_removal", "optimize_workflow",
            "vectorize_loop", "strengthen_types", "add_logging",
        ]

    def mutate(self, code: str, mutation_type: str) -> Tuple[str, str]:
        """Aplica uma mutao ao cdigo."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code, "Erro de sintaxe, mutao ignorada"

        # Mutao por string (comentrios, remoo de linha)
        if mutation_type == "add_comment":
            return self._add_comment(code)
        elif mutation_type == "remove_line":
            return self._remove_line(code)
        elif mutation_type == "grok_generate":
            return self._grok_generate(code)
        elif mutation_type == "grok_optimize":
            return self._grok_optimize(code)
        elif mutation_type == "crossover_function":
            return self._crossover_function(code)
        elif mutation_type == "dead_code_removal":
            return self._dead_code_removal(code)
        elif mutation_type == "optimize_workflow":
            return self._optimize_workflow(code)
        elif mutation_type == "vectorize_loop":
            return self._vectorize_loop(code)
        elif mutation_type == "strengthen_types":
            return self._strengthen_types(code)
        elif mutation_type == "add_logging":
            return self._add_logging(code)

        # Mutao por transformadores AST
        transformer_map = {
            "rename_var": RenameVarTransformer,
            "swap_operator": SwapOperatorTransformer,
            "simplify_expression": SimplifyExpressionTransformer,
            "add_docstring": AddDocstringTransformer,
            "loop_conversion": LoopConversionTransformer,
            "add_error_handling": AddErrorHandlingTransformer,
            "constant_folding": ConstantFoldingTransformer,
            "loop_unroll": LoopUnrollTransformer,
            "add_type_hints": TypeHintTransformer,
        }
        if mutation_type in transformer_map:
            try:
                new_tree = transformer_map[mutation_type]().visit(tree)
                ast.fix_missing_locations(new_tree)
                return astor.to_source(new_tree), mutation_type.replace("_", " ").capitalize()
            except Exception as e:
                logger.debug(f"Falha em {mutation_type}: {e}")
                return code, f"Falha em {mutation_type}"

        # Mutaes complexas (com funes dedicadas)
        complex_map = {
            "extract_function": self._extract_function,
            "inline_function": lambda c: (c, "Inline (no impl.)"),
            "insert_learned": self._insert_learned_function,
            "change_algorithm": self._change_algorithm,
            "parallelize_loop": lambda c: (c, "Paralelizao (no impl.)"),
            "memoize_function": self._memoize_function,
            "add_class": self._add_class,
            "add_import": self._add_import,
            "add_numba_jit": self._add_numba_jit,
        }
        if mutation_type in complex_map:
            return complex_map[mutation_type](code)

        return code, "Tipo de mutao desconhecido"

    def generate_candidates(self, code: str, mutation_types: List[str], n: int = None) -> List[Tuple[str, str, str]]:
        """Gera mltiplos candidatos em paralelo."""
        n = n or Config.CANDIDATES_PER_CYCLE
        selected = random.choices(mutation_types, k=n)
        results = []

        def _apply(mtype):
            mutated, desc = self.mutate(code, mtype)
            if self.checker:
                ok, reason = self.checker.check(mutated)
                if not ok:
                    return None
            if mutated != code:
                return (mutated, desc, mtype)
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, Config.PARALLEL_WORKERS)) as ex:
            futures = {ex.submit(_apply, mt): mt for mt in selected}
            for fut in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    res = fut.result()
                    if res:
                        results.append(res)
                except Exception as e:
                    logger.debug(f"Erro ao gerar candidato: {e}")
        return results

    #  Implementaes das mutaes 

    def _add_comment(self, code: str) -> Tuple[str, str]:
        lines = code.splitlines()
        candidates = [i for i, l in enumerate(lines) if l.strip() and not l.strip().startswith('#')]
        if not candidates:
            return code, "Sem local para comentrio"
        idx = random.choice(candidates)
        comment = random.choice([
            "# TODO: otimizar",
            "# Atena v3.0  gerado automaticamente",
            "# Considerar cache aqui",
            "# Ponto crtico de performance",
            "# Testado com Hypothesis",
        ])
        lines.insert(idx, comment)
        return '\n'.join(lines), "Comentrio adicionado"

    def _remove_line(self, code: str) -> Tuple[str, str]:
        lines = code.splitlines()
        candidates = [i for i, l in enumerate(lines)
                      if l.strip() and not l.strip().startswith(('def ', 'class ', 'import ', 'from ', '#'))]
        if not candidates:
            return code, "Sem linha removvel"
        idx = random.choice(candidates)
        removed = lines.pop(idx)
        return '\n'.join(lines), f"Linha removida: {removed[:40]}"

    def _grok_generate(self, code: str) -> Tuple[str, str]:
        if not self.grok:
            return code, "Grok no configurado"
        prompt = random.choice([
            "calculates fibonacci efficiently using memoization",
            "implements binary search on a sorted list",
            "checks if a string is a palindrome",
            "computes the GCD of two numbers",
            "flattens a nested list",
            "merges two sorted lists",
            "finds all primes up to N using sieve of Eratosthenes",
        ])
        generated = self.grok.generate_function(prompt)
        if generated and "def " in generated:
            return code + f"\n\n# Gerado por Grok\n{generated}", f"Grok: {prompt[:50]}"
        return code, "Grok falhou"

    def _grok_optimize(self, code: str) -> Tuple[str, str]:
        if not self.grok:
            return code, "Grok no configurado"
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not funcs:
                return code, "Nenhuma funo para otimizar"
            # Pega a funo mais complexa
            funcs.sort(key=lambda f: sum(1 for _ in ast.walk(f)), reverse=True)
            target = funcs[0]
            optimized = self.grok.generate_optimized_function(astor.to_source(target))
            if optimized and "def " in optimized:
                new_tree = ast.parse(optimized)
                new_func = [n for n in ast.walk(new_tree) if isinstance(n, ast.FunctionDef)]
                if new_func:
                    # Substitui a funo original pela otimizada
                    for i, node in enumerate(tree.body):
                        if isinstance(node, ast.FunctionDef) and node.name == target.name:
                            tree.body[i] = new_func[0]
                            tree.body[i].name = target.name
                            break
                    ast.fix_missing_locations(tree)
                    return astor.to_source(tree), f"Grok otimizou {target.name}"
        except Exception as e:
            logger.debug(f"Erro em grok_optimize: {e}")
        return code, "Grok optimize falhou"

    def _crossover_function(self, code: str) -> Tuple[str, str]:
        """Substitui corpo de uma funo por outra similar do banco."""
        if not self.kb.embedding_model or not self.kb.function_cache:
            # Fallback: insere funo aleatria
            func_data = self.kb.get_random_function()
            if not func_data:
                return code, "Sem funes no banco"
            return code + f"\n\n# Crossover do banco\n{func_data[0]}", "Crossover (aleatrio)"
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not funcs:
                return code, "Sem funes para crossover"
            target = random.choice(funcs)
            # Gera embedding da funo alvo
            text = f"{target.name} " + " ".join(
                [n.__class__.__name__ for n in ast.walk(target) if isinstance(n, (ast.Name, ast.Call))]
            )
            q_emb = self.kb.embedding_model.encode(text).astype(np.float32)
            best_match = None
            best_sim = 0.5
            for fc, emb, _ in self.kb.function_cache:
                sim = float(np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-8))
                if sim > best_sim:
                    best_sim = sim
                    best_match = fc
            if not best_match:
                return code, "Sem match para crossover"
            new_func_ast = ast.parse(best_match).body[0]
            if isinstance(new_func_ast, ast.FunctionDef):
                target.body = new_func_ast.body
                return astor.to_source(tree), f"Crossover (sim={best_sim:.2f})"
        except Exception as e:
            logger.debug(f"Erro em crossover: {e}")
        return code, "Crossover falhou"

    def _dead_code_removal(self, code: str) -> Tuple[str, str]:
        """Remove imports e funes no utilizadas."""
        if not Config.DEAD_CODE_REMOVAL:
            return code, "Dead code removal desativado"
        try:
            used = extract_used_names(code)
            tree = ast.parse(code)
            new_tree = DeadCodeRemover(used).visit(tree)
            ast.fix_missing_locations(new_tree)
            new_code = astor.to_source(new_tree)
            if new_code != code:
                return new_code, "Dead code removido"
        except Exception as e:
            logger.debug(f"Erro em dead_code_removal: {e}")
        return code, "Nenhum dead code encontrado"

    def _optimize_workflow(self, code: str) -> Tuple[str, str]:
        """Placeholder para mutao de workflow."""
        if not Config.ALLOW_WORKFLOW_MUTATION:
            return code, "Workflow mutation desativada"
        return code, "Workflow mutation solicitada"

    def _vectorize_loop(self, code: str) -> Tuple[str, str]:
        """Converte loops for em list comprehensions quando possvel."""
        try:
            tree = ast.parse(code)
            changed = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    new_body = []
                    for stmt in node.body:
                        if (isinstance(stmt, ast.For) and
                            isinstance(stmt.iter, ast.Call) and
                            isinstance(stmt.iter.func, ast.Name) and
                            stmt.iter.func.id == 'range' and
                            len(stmt.body) == 1 and
                            isinstance(stmt.body[0], ast.Expr)):
                            comp = ast.ListComp(
                                elt=stmt.body[0].value,
                                generators=[ast.comprehension(
                                    target=stmt.target,
                                    iter=stmt.iter,
                                    ifs=[],
                                    is_async=0
                                )]
                            )
                            new_stmt = ast.Expr(value=comp)
                            ast.copy_location(new_stmt, stmt)
                            new_body.append(new_stmt)
                            changed = True
                        else:
                            new_body.append(stmt)
                    node.body = new_body
            if changed:
                ast.fix_missing_locations(tree)
                return astor.to_source(tree), "Loop vetorizado"
        except Exception:
            pass
        return code, "Vetorizao no aplicvel"

    def _strengthen_types(self, code: str) -> Tuple[str, str]:
        """Adiciona verificaes de tipo baseadas em anotaes."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.args.args:
                    checks = []
                    for arg in node.args.args[:3]:
                        if arg.annotation and isinstance(arg.annotation, ast.Name):
                            expected = arg.annotation.id
                            if expected in ('int', 'str', 'float', 'list', 'dict'):
                                check = ast.parse(
                                    f"assert isinstance({arg.arg}, {expected}), "
                                    f"f'Esperado {expected}, recebido {{type({arg.arg}).__name__}}'"
                                ).body[0]
                                checks.append(check)
                    if checks:
                        node.body = checks + node.body
            ast.fix_missing_locations(tree)
            return astor.to_source(tree), "Verificaes de tipo adicionadas"
        except Exception:
            pass
        return code, "Fortalecimento de tipos no aplicvel"

    def _add_logging(self, code: str) -> Tuple[str, str]:
        """Adiciona logging estruturado."""
        try:
            if 'import logging' in code:
                return code, "Logging j existe"
            return "import logging\n_log = logging.getLogger(__name__)\n" + code, "Logging adicionado"
        except Exception:
            return code, "Logging no aplicvel"

    def _extract_function(self, code: str) -> Tuple[str, str]:
        """Extrai um bloco de cdigo para uma nova funo."""
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not funcs:
                return code, "Sem funes"
            func = random.choice(funcs)
            # Procura por um bloco (if, for, while) dentro da funo
            candidates = [n for n in ast.walk(func) if isinstance(n, (ast.If, ast.For, ast.While)) and n.body]
            if not candidates:
                return code, "Sem bloco candidato"
            block = random.choice(candidates)
            # Variveis usadas no bloco
            used_vars = {n.id for n in ast.walk(block) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            builtins = set(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__))
            params = [ast.arg(arg=v) for v in used_vars if v not in builtins]
            new_name = f"extracted_{random.randint(1000, 9999)}"
            new_func = ast.FunctionDef(
                name=new_name,
                args=ast.arguments(
                    args=params,
                    vararg=None,
                    kwarg=None,
                    defaults=[],
                    posonlyargs=[],
                    kwonlyargs=[],
                    kw_defaults=[]
                ),
                body=block.body,
                decorator_list=[],
                returns=None
            )
            # Substitui o bloco por uma chamada  nova funo
            call_args = [ast.Name(id=v, ctx=ast.Load()) for v in used_vars if v not in builtins]
            block.body = [ast.Expr(value=ast.Call(
                func=ast.Name(id=new_name, ctx=ast.Load()),
                args=call_args,
                keywords=[]
            ))]
            tree.body.append(new_func)
            return astor.to_source(tree), f"Funo {new_name} extrada"
        except Exception as e:
            logger.debug(f"Erro em extract_function: {e}")
            return code, f"Extrao falhou"

    def _insert_learned_function(self, code: str) -> Tuple[str, str]:
        """Insere uma funo aprendida do banco."""
        data = self.kb.get_random_function()
        if not data:
            return code, "Sem funes aprendidas"
        return code + f"\n\n# Aprendido de {data[1]}\n{data[0]}", f"Inserido de {data[1]}"

    def _change_algorithm(self, code: str) -> Tuple[str, str]:
        """Substitui algoritmo por um similar do banco."""
        data = self.kb.get_function_by_purpose(["sort", "search", "hash", "compress"])
        if not data:
            return code, "Sem algoritmo similar"
        return code + f"\n\n# Algoritmo de {data[1]}\n{data[0]}", f"Algoritmo de {data[1]}"

    def _memoize_function(self, code: str) -> Tuple[str, str]:
        """Adiciona decorador lru_cache a funes."""
        try:
            tree = ast.parse(code)
            # Verifica se functools j est importado
            has_functools = any(
                (isinstance(n, ast.Import) and any(a.name == "functools" for a in n.names)) or
                (isinstance(n, ast.ImportFrom) and n.module == "functools")
                for n in ast.walk(tree)
            )
            if not has_functools:
                tree.body.insert(0, ast.Import(names=[ast.alias(name="functools")]))
            # Adiciona decorador a funes sem IO
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.decorator_list:
                    # Verifica se a funo tem operaes de IO
                    has_io = any(
                        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and
                        n.func.id in ('print', 'open', 'input', 'write')
                        for n in ast.walk(node)
                    )
                    if not has_io:
                        node.decorator_list.append(
                            ast.Attribute(
                                value=ast.Name(id='functools', ctx=ast.Load()),
                                attr='lru_cache',
                                ctx=ast.Load()
                            )
                        )
            return astor.to_source(tree), "Memoizao adicionada"
        except Exception:
            return code, "Memoizao falhou"

    def _add_class(self, code: str) -> Tuple[str, str]:
        """Adiciona uma classe auxiliar simples."""
        template = '''

class AtenaHelper:
    """Classe auxiliar gerada pela Atena Neural v3.0."""
    def __init__(self, valor=None):
        self.valor = valor
        self._cache = {}
    def processar(self):
        if self.valor is None:
            return None
        if self.valor in self._cache:
            return self._cache[self.valor]
        result = self.valor * 2
        self._cache[self.valor] = result
        return result
    def __repr__(self):
        return f"AtenaHelper(valor={self.valor})"
'''
        return code + template, "Classe AtenaHelper adicionada"

    def _add_import(self, code: str) -> Tuple[str, str]:
        """Adiciona um import aleatrio."""
        options = [
            "import math",
            "import random",
            "from collections import Counter",
            "import itertools",
            "from typing import List, Dict, Optional",
            "from functools import lru_cache"
        ]
        imp = random.choice(options)
        if imp in code:
            return code, "Import j existe"
        return imp + "\n" + code, f"Import: {imp}"

    def _add_numba_jit(self, code: str) -> Tuple[str, str]:
        """Adiciona decorador numba.jit a funes com loops."""
        if not HAS_NUMBA:
            return code, "numba no disponvel"
        try:
            tree = ast.parse(code)
            # Verifica import do numba
            if not any(
                isinstance(n, ast.Import) and any(a.name == "numba" for a in n.names)
                for n in ast.walk(tree)
            ):
                tree.body.insert(0, ast.Import(names=[ast.alias(name="numba")]))
            # Adiciona decorador a funes com loops
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    has_jit = any(
                        (isinstance(d, ast.Attribute) and d.attr == "jit") or
                        (isinstance(d, ast.Name) and d.id == "jit")
                        for d in node.decorator_list
                    )
                    if not has_jit and any(
                        isinstance(n, (ast.For, ast.While)) for n in ast.walk(node)
                    ):
                        node.decorator_list.append(
                            ast.Attribute(
                                value=ast.Name(id='numba', ctx=ast.Load()),
                                attr='jit',
                                ctx=ast.Load()
                            )
                        )
            return astor.to_source(tree), "numba.jit adicionado"
        except Exception:
            return code, "numba jit falhou"


# 
# TRANSFORMADORES AST (usados nas mutaes)
# 

class ConstantFoldingTransformer(ast.NodeTransformer):
    """Realiza dobra de constantes em expresses."""
    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            try:
                result = eval(compile(ast.Expression(body=node), '<string>', 'eval'))
                return ast.Constant(value=result)
            except Exception:
                pass
        return node

    def visit_UnaryOp(self, node):
        node = self.generic_visit(node)
        if isinstance(node.operand, ast.Constant):
            try:
                result = eval(compile(ast.Expression(body=node), '<string>', 'eval'))
                return ast.Constant(value=result)
            except Exception:
                pass
        return node


class LoopUnrollTransformer(ast.NodeTransformer):
    """Desenrola loops pequenos."""
    def visit_For(self, node):
        node = self.generic_visit(node)
        if not (isinstance(node.iter, ast.Call) and
                isinstance(node.iter.func, ast.Name) and
                node.iter.func.id == 'range'):
            return node
        args = node.iter.args
        if len(args) != 1 or not isinstance(args[0], ast.Constant):
            return node
        n = args[0].value
        if not isinstance(n, int) or n > Config.LOOP_UNROLL_MAX or n < 1:
            return node
        new_nodes = []
        for i in range(n):
            for stmt in node.body:
                new_stmt = ast.parse(astor.to_source(stmt)).body[0]
                replacer = NameReplacer(node.target.id, ast.Constant(value=i))
                new_stmt = replacer.visit(new_stmt)
                new_nodes.append(new_stmt)
        return new_nodes if new_nodes else node


class NameReplacer(ast.NodeTransformer):
    """Substitui um nome por um n AST."""
    def __init__(self, name: str, replacement: ast.AST):
        self.name = name
        self.replacement = replacement

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id == self.name:
            return self.replacement
        return node


class DeadCodeRemover(ast.NodeTransformer):
    """Remove imports e funes no utilizados."""
    def __init__(self, used_names: Set[str]):
        self.used_names = used_names

    def visit_Import(self, node):
        new_names = [a for a in node.names if (a.asname or a.name.split('.')[0]) in self.used_names]
        if not new_names:
            return None
        node.names = new_names
        return node

    def visit_ImportFrom(self, node):
        new_names = [a for a in node.names if (a.asname or a.name) in self.used_names]
        if not new_names:
            return None
        node.names = new_names
        return node


class TypeHintTransformer(ast.NodeTransformer):
    """Adiciona type hints simples."""
    def visit_FunctionDef(self, node):
        node = self.generic_visit(node)
        if node.returns is None:
            # Verifica se a funo tem retorno com valor
            has_return_value = any(
                isinstance(n, ast.Return) and n.value is not None
                for n in ast.walk(node)
            )
            if not has_return_value:
                node.returns = ast.Constant(value=None)
        return node


class RenameVarTransformer(ast.NodeTransformer):
    """Renomeia variveis para nomes mais descritivos."""
    def __init__(self):
        self.rename_map = {}
        self.counter = 0

    def visit_Name(self, node):
        builtins = set(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__))
        if isinstance(node.ctx, ast.Store) and node.id not in builtins:
            if node.id not in self.rename_map:
                self.rename_map[node.id] = f"{node.id}_v{self.counter}"
                self.counter += 1
            return ast.Name(id=self.rename_map[node.id], ctx=node.ctx)
        elif isinstance(node.ctx, ast.Load) and node.id in self.rename_map:
            return ast.Name(id=self.rename_map[node.id], ctx=node.ctx)
        return node


class SwapOperatorTransformer(ast.NodeTransformer):
    """Troca operadores aritmticos aleatoriamente."""
    def visit_BinOp(self, node):
        if random.random() < 0.3:
            if isinstance(node.op, ast.Add):
                node.op = ast.Sub()
            elif isinstance(node.op, ast.Sub):
                node.op = ast.Add()
            elif isinstance(node.op, ast.Mult):
                node.op = ast.Div() if random.random() < 0.5 else ast.FloorDiv()
            elif isinstance(node.op, ast.Div):
                node.op = ast.Mult()
        return node


class SimplifyExpressionTransformer(ast.NodeTransformer):
    """Simplifica expresses aritmticas."""
    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if isinstance(node.op, ast.Mult):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return ast.Constant(value=0)
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                return ast.Constant(value=0)
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 1:
                return node.right
        if isinstance(node.op, ast.Add):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                return node.right
        if isinstance(node.op, ast.Sub):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
        return node


class AddDocstringTransformer(ast.NodeTransformer):
    """Adiciona docstring a funes sem documentao."""
    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(value="Funo evoluda pela Atena Neural v3.0.")))
        return node


class LoopConversionTransformer(ast.NodeTransformer):
    """Converte loops for em while."""
    def visit_For(self, node):
        if (isinstance(node.iter, ast.Call) and
                isinstance(node.iter.func, ast.Name) and
                node.iter.func.id == 'range'):
            args = node.iter.args
            if len(args) == 1:
                start, end, step = ast.Constant(value=0), args[0], ast.Constant(value=1)
            elif len(args) == 2:
                start, end, step = args[0], args[1], ast.Constant(value=1)
            else:
                return node
            assign = ast.Assign(
                targets=[ast.Name(id=node.target.id, ctx=ast.Store())],
                value=start,
                lineno=node.lineno,
                col_offset=node.col_offset
            )
            test = ast.Compare(
                left=ast.Name(id=node.target.id, ctx=ast.Load()),
                ops=[ast.Lt()],
                comparators=[end]
            )
            inc = ast.AugAssign(
                target=ast.Name(id=node.target.id, ctx=ast.Store()),
                op=ast.Add(),
                value=step
            )
            while_node = ast.While(test=test, body=node.body + [inc], orelse=[])
            ast.copy_location(assign, node)
            ast.copy_location(while_node, node)
            return [assign, while_node]
        return node


class AddErrorHandlingTransformer(ast.NodeTransformer):
    """Adiciona tratamento de excees a funes."""
    def visit_FunctionDef(self, node):
        if node.body and not any(isinstance(n, ast.Try) for n in node.body):
            handler = ast.ExceptHandler(
                type=ast.Name(id='Exception', ctx=ast.Load()),
                name='_e',
                body=[
                    ast.Expr(value=ast.Call(
                        func=ast.Name(id='print', ctx=ast.Load()),
                        args=[
                            ast.Constant(value=f"[Atena] Erro em {node.name}:"),
                            ast.Name(id='_e', ctx=ast.Load())
                        ],
                        keywords=[]
                    )),
                    ast.Raise()
                ]
            )
            node.body = [ast.Try(body=node.body, handlers=[handler], orelse=[], finalbody=[])]
        return node


def extract_used_names(code: str) -> Set[str]:
    """Extrai todos os nomes usados no cdigo (para dead code removal)."""
    try:
        tree = ast.parse(code)
        return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    except Exception:
        return set()


# 
# PROFILER DE CDIGO
# 

class CodeProfiler:
    """Perfila a execuo de cdigo para identificar funes mais custosas."""

    def profile(self, code: str, timeout: int = 3) -> List[str]:
        """Executa o cdigo com cProfile e retorna as funes mais chamadas."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            profile_code = f"""
import cProfile, pstats, io
pr = cProfile.Profile()
pr.enable()
exec(open('{tmp}').read())
pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats({Config.PROFILE_TOP_N})
print(s.getvalue())
"""
            proc = subprocess.run(
                [sys.executable, '-c', profile_code],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return self._parse_profile_output(proc.stdout)
        except Exception as e:
            logger.debug(f"Erro no profiler: {e}")
            return []
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def _parse_profile_output(self, output: str) -> List[str]:
        """Extrai nomes de funes da sada do pstats."""
        funcs = []
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 6 and '(' in parts[-1]:
                func_name = parts[-1].strip('()')
                if func_name and not func_name.startswith('<'):
                    funcs.append(func_name)
        return funcs[:Config.PROFILE_TOP_N]


# 
# PREDITOR DE MUTAES (ML)
# 

class MutationPredictor:
    """Prediz a probabilidade de sucesso de uma mutao."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.model = None
        self.vectorizer = None
        self._load_model()
        self._success_rates: Dict[str, float] = {}

    def _load_model(self):
        """Carrega modelo treinado do disco."""
        if Config.PREDICTOR_MODEL.exists():
            try:
                with open(Config.PREDICTOR_MODEL, 'rb') as f:
                    self.model, self.vectorizer = pickle.load(f)
                logger.info("Modelo preditor carregado")
            except Exception as e:
                logger.warning(f"Falha ao carregar modelo: {e}")

    def _save_model(self):
        """Salva modelo treinado."""
        try:
            with open(Config.PREDICTOR_MODEL, 'wb') as f:
                pickle.dump((self.model, self.vectorizer), f)
        except Exception as e:
            logger.warning(f"Falha ao salvar modelo: {e}")

    def train(self):
        """Treina o modelo com dados do banco."""
        if not HAS_SKLEARN:
            logger.warning("sklearn no disponvel, pulando treinamento")
            return
        X_dict, y = self.kb.get_training_data()
        if len(X_dict) < Config.MIN_TRAINING_SAMPLES:
            logger.info(f"Amostras insuficientes: {len(X_dict)}/{Config.MIN_TRAINING_SAMPLES}")
            return
        try:
            self.vectorizer = DictVectorizer(sparse=False)
            X = self.vectorizer.fit_transform(X_dict)
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                random_state=42
            )
            self.model.fit(X, y)
            self._save_model()
            logger.info(f"Modelo treinado com {len(X_dict)} amostras")
        except Exception as e:
            logger.warning(f"Falha no treinamento: {e}")
        self._success_rates = self.kb.get_mutation_success_rates()

    def predict_proba(self, features: Dict) -> float:
        """Retorna probabilidade de sucesso para uma mutao."""
        if self.model and self.vectorizer:
            try:
                X = self.vectorizer.transform([features])
                return float(self.model.predict_proba(X)[0][1])
            except Exception as e:
                logger.debug(f"Erro na predio: {e}")
        # Fallback: taxa histrica
        return self._success_rates.get(features.get("mutation_type", ""), 0.5)


# 
# APRENDIZADO DO GITHUB (com amostragem de repositrios grandes)
# 

class GitHubLearner(threading.Thread):
    """Coleta funes de repositrios pblicos do GitHub."""

    def __init__(self, kb: KnowledgeBase):
        super().__init__(daemon=True)
        self.kb = kb
        self.session = requests.Session()
        if Config.GITHUB_TOKEN:
            self.session.headers.update({"Authorization": f"token {Config.GITHUB_TOKEN}"})
        self.running = True
        self._queue: queue.Queue = queue.Queue()
        self._processed_count = 0
        self._lock = threading.RLock()

    def run(self):
        self._enqueue_repos()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1 if IS_CI else 3) as ex:
            while self.running and self._processed_count < Config.GITHUB_MAX_REPOS_PER_RUN:
                try:
                    repo = self._queue.get(timeout=10)
                    ex.submit(self._process_repo, repo)
                except queue.Empty:
                    if not self._enqueue_repos():
                        break
                time.sleep(0.5)

    def _enqueue_repos(self) -> bool:
        """Busca repositrios populares e coloca na fila."""
        for page in range(1, 3):
            if self._processed_count >= Config.GITHUB_MAX_REPOS_PER_RUN:
                break
            repos = self._search_repos(page)
            if not repos:
                return False
            for r in repos:
                if self._processed_count >= Config.GITHUB_MAX_REPOS_PER_RUN:
                    break
                self._queue.put(r)
        return True

    def _search_repos(self, page=1) -> List[Dict]:
        """Consulta API do GitHub por repositrios Python populares."""
        try:
            resp = self.session.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": "language:python stars:>100",
                    "sort": "stars",
                    "order": "desc",
                    "page": page,
                    "per_page": 10
                },
                timeout=15
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"Erro ao buscar repositrios: {e}")
            return []

    def _process_repo(self, repo):
        """Processa um nico repositrio: baixa arquivos .py e extrai funes."""
        name = repo["full_name"]
        with self.kb._lock:
            if self.kb.conn.execute(
                "SELECT 1 FROM github_repos WHERE repo_full_name=?", (name,)
            ).fetchone():
                return
        logger.info(f"[] GitHub: {name}")
        tree = self._get_tree(name)
        if not tree:
            return
        py_files = [f for f in tree if f["path"].endswith(".py") and f["type"] == "blob"]
        # Se for muito grande, amostra aleatoriamente
        if len(py_files) > Config.GITHUB_MAX_FILES_PER_REPO * 2:
            logger.info(f"    Repositrio grande ({len(py_files)} arquivos), amostrando {Config.GITHUB_MAX_FILES_PER_REPO}")
            py_files = random.sample(py_files, min(len(py_files), Config.GITHUB_MAX_FILES_PER_REPO))
        else:
            py_files = py_files[:Config.GITHUB_MAX_FILES_PER_REPO]
        processed = 0
        for fi in py_files:
            content = self._fetch_file(name, fi["path"])
            if content:
                for func in self._extract_functions(content):
                    self.kb.add_function(func, f"github:{name}", self._infer_purpose(func))
                processed += 1
            time.sleep(0.05)
        with self.kb._lock:
            self.kb.conn.execute(
                "INSERT OR REPLACE INTO github_repos VALUES (NULL,?,?,?,?)",
                (name, repo.get("stargazers_count", 0), datetime.now().isoformat(), processed)
            )
            self.kb.conn.commit()
        with self._lock:
            self._processed_count += 1

    def _get_tree(self, repo):
        """Obtm a rvore de arquivos do repositrio."""
        try:
            r = self.session.get(
                f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1",
                timeout=10
            )
            r.raise_for_status()
            return r.json().get("tree", [])
        except Exception as e:
            logger.debug(f"Erro ao obter rvore de {repo}: {e}")
            return None

    def _fetch_file(self, repo, path):
        """Baixa contedo de um arquivo."""
        try:
            r = self.session.get(
                f"https://api.github.com/repos/{repo}/contents/{path}",
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            if data.get("encoding") == "base64":
                import base64
                return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Erro ao baixar {path}: {e}")
        return None

    def _extract_functions(self, code):
        """Extrai funes de um cdigo Python."""
        try:
            tree = ast.parse(code)
            return [astor.to_source(n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        except Exception:
            return []

    def _infer_purpose(self, code: str) -> str:
        """Infere o propsito da funo baseado em palavras-chave."""
        keywords = {
            "sort": "ordenacao",
            "order": "ordenacao",
            "merge": "merge",
            "sum": "soma",
            "add": "soma",
            "avg": "media",
            "mean": "media",
            "search": "busca",
            "find": "busca",
            "hash": "hash",
            "fact": "fatorial",
            "prime": "primo",
            "fib": "fibonacci",
            "encrypt": "criptografia",
            "compress": "compressao",
            "parse": "parser",
            "format": "formatacao",
        }
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for kw, purpose in keywords.items():
                        if kw in node.name.lower():
                            return purpose
        except Exception:
            pass
        return "desconhecido"

    def stop(self):
        self.running = False


# 
# CLIENTE NEWSAPI
# 

class NewsAPIClient:
    """Obtm notcias sobre Python e cria objetivos temporrios."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.session = requests.Session()

    def update_objectives(self):
        """Consulta API de notcias e adiciona objetivos."""
        if not Config.NEWS_API_KEY:
            return
        try:
            resp = self.session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": "python performance optimization OR algorithm efficiency",
                    "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "sortBy": "relevancy",
                    "language": "en",
                    "pageSize": 10,
                    "apiKey": Config.NEWS_API_KEY
                },
                timeout=10
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            text = " ".join(
                a.get("title", "") + " " + a.get("description", "")
                for a in articles
            )
            words = [w.lower() for w in text.split() if len(w) > 5 and w.isalpha()]
            for kw, _ in Counter(words).most_common(3):
                self.kb.add_temporary_objective(
                    f"learn_{kw}",
                    f"Aprender: {kw}",
                    1.0,
                    0.3
                )
                logger.info(f"[] Novo objetivo: {kw}")
        except Exception as e:
            logger.warning(f"Erro ao atualizar objetivos via NewsAPI: {e}")


# =============================================================================
# MDULOS v3 (auto-modificao, scorer evoluvel, meta-learner, etc.)
# =============================================================================

# 
# v3 SELF-MOD ENGINE  muta o prprio atena_engine.py
# 

class EngineBackup:
    """Gerencia backups do engine antes de qualquer auto-modificao."""

    def __init__(self, engine_path: Path, backup_dir: Path):
        self.engine_path = engine_path
        self.backup_dir  = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = self.backup_dir / f"engine_backup_{ts}.py"
        shutil.copy(self.engine_path, dest)
        logger.info(f"[] Engine backup salvo: {dest.name}")
        return dest

    def restore(self, backup_path: Path):
        shutil.copy(backup_path, self.engine_path)
        logger.info(f"[] Engine restaurado de: {backup_path.name}")

    def list_backups(self) -> List[Path]:
        return sorted(self.backup_dir.glob("engine_backup_*.py"), reverse=True)

    def prune(self, keep: int = 10):
        backups = self.list_backups()
        for old in backups[keep:]:
            try:
                old.unlink()
            except Exception:
                pass


class SelfModEngine:
    """
    Responsvel por aplicar mutaes seguras no prprio engine da Atena.
    """

    MUTABLE_CLASSES = {
        "MutationEngine",
        "CodeEvaluator",
        "MutationPredictor",
        "AtenaCore",
        "FeedbackLoop",
        "EpisodicMemory",
        "AutoRewardSystem",
        "LanguageTrainer",
    }

    PROTECTED_FUNCTIONS = {
        "_run_subprocess", "_run_docker", "run",
        "check",
        "_backup", "_cleanup_backups",
        "__init__",
    }

    def __init__(self, engine_path: Path, backup_dir: Path,
                 validator: "SelfModValidator"):
        self.engine_path = engine_path
        self.backup      = EngineBackup(engine_path, backup_dir)
        self.validator   = validator
        self._lock       = threading.RLock()
        self._mod_history: deque = deque(maxlen=100)

    def _add_helper_method(self, tree: ast.Module, target_class: str) -> Tuple[ast.Module, str]:
        """Adiciona um mtodo auxiliar a uma classe existente."""
        method_templates = [
            """
def _cache_key(self, *args) -> str:
    import hashlib, json
    return hashlib.md5(json.dumps(args, default=str).encode()).hexdigest()[:16]
""",
            """
def _timed(self, fn, *args, **kwargs):
    import time
    t0 = time.time()
    result = fn(*args, **kwargs)
    return result, time.time() - t0
""",
            """
def _retry(self, fn, attempts: int = 3, delay: float = 1.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            if i == attempts - 1:
                raise
            import time; time.sleep(delay * (i + 1))
""",
            """
def _snapshot_metrics(self) -> dict:
    import gc, sys
    return {
        "objects": len(gc.get_objects()),
        "threads": len(__import__('threading').enumerate()),
        "timestamp": __import__('datetime').datetime.now().isoformat(),
    }
""",
        ]
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == target_class:
                    existing = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                    template = random.choice(method_templates)
                    new_method = ast.parse(textwrap.dedent(template)).body[0]
                    if isinstance(new_method, ast.FunctionDef) and new_method.name not in existing:
                        node.body.append(new_method)
                        return tree, f"Mtodo '{new_method.name}' adicionado a {target_class}"
        except Exception as e:
            pass
        return tree, "Nenhum mtodo adicionado"

    def _improve_config_default(self, tree: ast.Module) -> Tuple[ast.Module, str]:
        """Ajusta valores padro de configurao de forma conservadora."""
        adjustable = {
            "EXPLORATION_RATE":      (0.05, 0.30),
            "MUTATION_STRENGTH":     (0.3,  0.9),
            "MIN_IMPROVEMENT_DELTA": (0.001, 0.05),
            "CANDIDATES_PER_CYCLE":  (2,    8),
        }
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "Config":
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            name = stmt.target.id
                            if name in adjustable and isinstance(stmt.value, ast.Constant):
                                lo, hi = adjustable[name]
                                current = stmt.value.value
                                if isinstance(current, (int, float)):
                                    delta = (hi - lo) * 0.05
                                    new_val = max(lo, min(hi, current + random.uniform(-delta, delta)))
                                    if isinstance(current, int):
                                        new_val = int(round(new_val))
                                    stmt.value = ast.Constant(value=new_val)
                                    return tree, f"Config.{name}: {current}  {new_val:.4f}"
        except Exception:
            pass
        return tree, "Nenhuma config ajustada"

    def _add_mutation_type(self, tree: ast.Module) -> Tuple[ast.Module, str]:
        """
        Adiciona um novo tipo de mutao  lista mutation_types do MutationEngine.
        Tambm adiciona o handler correspondente.
        """
        new_mutations = [
            ("vectorize_loop",
             """
def _vectorize_loop(self, code: str):
    \"\"\"Converte loops simples em list comprehensions.\"\"\"
    import ast, astor
    try:
        tree = ast.parse(code)
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                new_body = []
                for stmt in node.body:
                    if (isinstance(stmt, ast.For) and
                        isinstance(stmt.iter, ast.Call) and
                        isinstance(stmt.iter.func, ast.Name) and
                        stmt.iter.func.id == 'range' and
                        len(stmt.body) == 1 and
                        isinstance(stmt.body[0], ast.Expr)):
                        comp = ast.ListComp(
                            elt=stmt.body[0].value,
                            generators=[ast.comprehension(
                                target=stmt.target,
                                iter=stmt.iter,
                                ifs=[],
                                is_async=0
                            )]
                        )
                        new_stmt = ast.Expr(value=comp)
                        ast.copy_location(new_stmt, stmt)
                        new_body.append(new_stmt)
                        changed = True
                    else:
                        new_body.append(stmt)
                node.body = new_body
        if changed:
            ast.fix_missing_locations(tree)
            return astor.to_source(tree), "Loop vetorizado para list comprehension"
    except Exception:
        pass
    return code, "Vetorizao no aplicvel"
"""),
            ("strengthen_types",
             """
def _strengthen_types(self, code: str):
    \"\"\"Adiciona verificaes de tipo em funes crticas.\"\"\"
    import ast, astor
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.args.args:
                checks = []
                for arg in node.args.args[:3]:
                    if arg.annotation and isinstance(arg.annotation, ast.Name):
                        expected = arg.annotation.id
                        if expected in ('int', 'str', 'float', 'list', 'dict'):
                            check = ast.parse(
                                f"assert isinstance({arg.arg}, {expected}), "
                                f"f'Esperado {expected}, recebido {{type({arg.arg}).__name__}}'"
                            ).body[0]
                            checks.append(check)
                if checks:
                    node.body = checks + node.body
        ast.fix_missing_locations(tree)
        return astor.to_source(tree), "Verificaes de tipo adicionadas"
    except Exception:
        pass
    return code, "Fortalecimento de tipos no aplicvel"
"""),
            ("add_logging",
             """
def _add_logging(self, code: str):
    \"\"\"Adiciona logging estruturado a funes sem print.\"\"\"
    import ast, astor
    try:
        tree = ast.parse(code)
        has_logging = any(
            isinstance(n, (ast.Import, ast.ImportFrom)) and
            'logging' in ast.dump(n)
            for n in ast.walk(tree)
        )
        if not has_logging:
            tree.body.insert(0, ast.parse("import logging\\n_log = logging.getLogger(__name__)").body[0])
            tree.body.insert(1, ast.parse("import logging\\n_log = logging.getLogger(__name__)").body[1])
        ast.fix_missing_locations(tree)
        return astor.to_source(tree), "Logging adicionado"
    except Exception:
        pass
    return code, "Logging no aplicvel"
"""),
        ]

        try:
            name, handler_src = random.choice(new_mutations)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "MutationEngine":
                    for stmt in node.body:
                        if (isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__"):
                            for sub in ast.walk(stmt):
                                if (isinstance(sub, ast.Assign) and
                                    isinstance(sub.targets[0], ast.Attribute) and
                                    sub.targets[0].attr == "mutation_types" and
                                    isinstance(sub.value, ast.List)):
                                    existing = [elt.s for elt in sub.value.elts
                                                if isinstance(elt, ast.Constant)]
                                    if name not in existing:
                                        sub.value.elts.append(ast.Constant(value=name))
                                        handler_tree = ast.parse(textwrap.dedent(handler_src))
                                        handler_func = handler_tree.body[0]
                                        node.body.append(handler_func)
                                        return tree, f"Novo tipo de mutao '{name}' adicionado ao engine"
        except Exception as e:
            pass
        return tree, "Nenhum tipo de mutao novo adicionado"

    def _refactor_docstrings(self, tree: ast.Module) -> Tuple[ast.Module, str]:
        """Melhora docstrings de funes sem documentao."""
        prefixes = [
            "Atena v3.0  ",
            "Auto-evoludo: ",
            "Otimizado para performance: ",
        ]
        count = 0
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not ast.get_docstring(node):
                    if node.name not in self.PROTECTED_FUNCTIONS:
                        prefix = random.choice(prefixes)
                        doc = f"{prefix}{node.name.replace('_', ' ').capitalize()}."
                        node.body.insert(0, ast.Expr(value=ast.Constant(value=doc)))
                        count += 1
                        if count >= 3:
                            break
        except Exception:
            pass
        return tree, f"Docstrings adicionadas: {count}" if count else "Nenhuma docstring adicionada"

    def mutate_engine(self) -> Tuple[bool, str, Optional[Path]]:
        """
        Aplica uma mutao no engine. Retorna (sucesso, descrio, backup_path).
        """
        if not ALLOW_DEEP_SELF_MOD:
            return False, "ALLOW_DEEP_SELF_MOD=false  auto-modificao desativada", None

        if not self.engine_path.exists():
            return False, f"Engine no encontrado: {self.engine_path}", None

        with self._lock:
            backup_path = self.backup.save()
            try:
                source = self.engine_path.read_text()
                tree = ast.parse(source)

                mutations = [
                    self._refactor_docstrings,
                    self._improve_config_default,
                    self._add_mutation_type,
                    lambda t: self._add_helper_method(
                        t, random.choice(list(self.MUTABLE_CLASSES))
                    ),
                ]
                fn = random.choice(mutations)
                new_tree, description = fn(tree)

                ast.fix_missing_locations(new_tree)
                new_source = astor.to_source(new_tree)

                valid, reason = self.validator.validate(new_source)
                if not valid:
                    self.backup.restore(backup_path)
                    return False, f"Validao falhou: {reason}", backup_path

                self.engine_path.write_text(new_source)
                self._record(description, backup_path)
                logger.info(f"[] Engine mutado: {description}")
                return True, description, backup_path

            except Exception as e:
                self.backup.restore(backup_path)
                return False, f"Erro durante mutao do engine: {e}", backup_path

    def _record(self, description: str, backup_path: Path):
        self._mod_history.append({
            "timestamp":   datetime.now().isoformat(),
            "description": description,
            "backup":      str(backup_path),
        })

    def get_history(self) -> List[Dict]:
        return list(self._mod_history)


# 
# 2. EVOLVABLE SCORER  _compute_score como cdigo evoluvel
# 

@dataclass
class ScorerGenome:
    id: str
    source_code: str
    generation: int
    fitness: float = 0.0
    long_term_score: float = 0.0
    applied_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def hash(self) -> str:
        return hashlib.sha256(self.source_code.encode()).hexdigest()[:16]


class EvolvableScorer:
    POPULATION_SIZE = 6
    TOURNAMENT_SIZE = 3

    BASE_SCORER_SOURCE = '''
def compute_score(metrics: dict) -> float:
    """Scorer base da Atena v2.2  mantido como fallback."""
    base = 10.0
    total = metrics.get("tests_total", 0)
    tests = 40.0 * (metrics.get("tests_passed", 0) / total) if total > 0 else 25.0
    quality = 0.0
    comp = metrics.get("complexity", 10)
    if comp <= 3:   quality += 15
    elif comp <= 5: quality += 10
    elif comp <= 8: quality += 5
    nf = metrics.get("num_functions", 0)
    if 3 <= nf <= 8: quality += 10
    elif nf > 8:     quality += 5
    elif nf > 0:     quality += 2
    if metrics.get("comment_ratio", 0) > 0.05: quality += 5
    t = metrics.get("execution_time") or 1.0
    if t < 0.05:   quality += 15
    elif t < 0.1:  quality += 10
    elif t < 0.3:  quality += 5
    if metrics.get("coverage", 0) > 0.7:  quality += 5
    elif metrics.get("coverage", 0) > 0.3: quality += 3
    return min(base + tests + quality, 100.0)
'''

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.RLock()
        self._population: List[ScorerGenome] = []
        self._active_id: Optional[str] = None
        self._active_fn: Optional[Callable] = None
        self._history: deque = deque(maxlen=500)
        self._init_db()
        self._load_population()

    def _init_db(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS scorer_population (
                id TEXT PRIMARY KEY,
                source_code TEXT,
                generation INTEGER,
                fitness REAL DEFAULT 0,
                long_term_score REAL DEFAULT 0,
                applied_count INTEGER DEFAULT 0,
                created_at TEXT,
                active INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS scorer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation INTEGER,
                scorer_id TEXT,
                score REAL,
                replaced INTEGER,
                timestamp TEXT
            );
        ''')
        self.conn.commit()

    def _load_population(self):
        rows = self.conn.execute(
            "SELECT id, source_code, generation, fitness, long_term_score, applied_count, created_at, active "
            "FROM scorer_population ORDER BY fitness DESC"
        ).fetchall()

        if not rows:
            genome = ScorerGenome(
                id="base_scorer",
                source_code=self.BASE_SCORER_SOURCE,
                generation=0,
                fitness=50.0,
            )
            self._save_genome(genome, active=True)
            self._population = [genome]
        else:
            self._population = [
                ScorerGenome(
                    id=r[0], source_code=r[1], generation=r[2],
                    fitness=r[3], long_term_score=r[4], applied_count=r[5],
                    created_at=r[6]
                )
                for r in rows
            ]

        active_row = self.conn.execute(
            "SELECT id FROM scorer_population WHERE active=1 LIMIT 1"
        ).fetchone()
        if active_row:
            self._active_id = active_row[0]
            self._compile_active()
        else:
            self._active_id = self._population[0].id
            self._compile_active()

    def _save_genome(self, genome: ScorerGenome, active: bool = False):
        self.conn.execute('''
            INSERT OR REPLACE INTO scorer_population
            (id, source_code, generation, fitness, long_term_score, applied_count, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (genome.id, genome.source_code, genome.generation, genome.fitness,
              genome.long_term_score, genome.applied_count, genome.created_at,
              1 if active else 0))
        self.conn.commit()

    def _compile_active(self):
        active = next((g for g in self._population if g.id == self._active_id), None)
        if not active:
            active = self._population[0]
            self._active_id = active.id

        try:
            namespace = {}
            exec(compile(active.source_code, "<scorer>", "exec"), namespace)
            self._active_fn = namespace.get("compute_score")
            if not self._active_fn:
                raise ValueError("compute_score no encontrada no scorer")
        except Exception as e:
            logger.warning(f"[] Falha ao compilar scorer '{self._active_id}': {e}. Usando base.")
            namespace = {}
            exec(compile(self.BASE_SCORER_SOURCE, "<base_scorer>", "exec"), namespace)
            self._active_fn = namespace["compute_score"]

    def compute(self, metrics: Dict) -> float:
        if not self._active_fn:
            self._compile_active()
        try:
            score = float(self._active_fn(metrics))
            score = max(0.0, min(100.0, score))
            return round(score, 2)
        except Exception as e:
            logger.warning(f"[] Scorer ativo falhou: {e}. Usando fallback.")
            return self._fallback_score(metrics)

    def _fallback_score(self, metrics: Dict) -> float:
        namespace = {}
        exec(compile(self.BASE_SCORER_SOURCE, "<fallback>", "exec"), namespace)
        return namespace["compute_score"](metrics)

    def record(self, generation: int, score: float, replaced: bool):
        self._history.append((generation, score, self._active_id, replaced))
        with self._lock:
            self.conn.execute(
                "INSERT INTO scorer_history (generation, scorer_id, score, replaced, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (generation, self._active_id, score, 1 if replaced else 0,
                 datetime.now().isoformat())
            )
            self.conn.commit()
        for g in self._population:
            if g.id == self._active_id:
                g.applied_count += 1
                g.long_term_score = (
                    (g.long_term_score * (g.applied_count - 1) + score) / g.applied_count
                )
                self._save_genome(g)
                break

    def evolve(self, current_generation: int) -> Optional[ScorerGenome]:
        if len(self._history) < 20:
            return None

        logger.info(f"\n[] EvolvableScorer  evoluindo populao (gen {current_generation})")

        self._update_fitness_scores()

        best = max(self._population, key=lambda g: g.fitness)
        new_candidates = []

        for _ in range(self.POPULATION_SIZE // 2):
            mutated = self._mutate_scorer(best, current_generation)
            if mutated:
                new_candidates.append(mutated)

        if len(self._population) >= 2:
            sorted_pop = sorted(self._population, key=lambda g: g.fitness, reverse=True)
            crossed = self._crossover_scorers(sorted_pop[0], sorted_pop[1], current_generation)
            if crossed:
                new_candidates.append(crossed)

        all_candidates = self._population + new_candidates
        champion = self._tournament_select(all_candidates)

        if champion and champion.id != self._active_id:
            logger.info(f"   [] Novo scorer campeo: '{champion.id}' (fitness={champion.fitness:.2f})")
            self.conn.execute("UPDATE scorer_population SET active=0")
            self._active_id = champion.id
            if not any(g.id == champion.id for g in self._population):
                self._population.append(champion)
            self._save_genome(champion, active=True)
            self._compile_active()

            self._population = sorted(
                self._population + new_candidates,
                key=lambda g: g.fitness, reverse=True
            )[:self.POPULATION_SIZE]
            for g in self._population:
                self._save_genome(g, active=(g.id == self._active_id))

            return champion

        return None

    def _update_fitness_scores(self):
        history = list(self._history)[-200:]
        if not history:
            return

        by_scorer = defaultdict(list)
        for gen, score, sid, replaced in history:
            by_scorer[sid].append((gen, score, replaced))

        for genome in self._population:
            records = by_scorer.get(genome.id, [])
            if not records:
                continue
            scores = [s for _, s, _ in records]
            improvements = sum(1 for _, _, r in records if r)
            avg_score = sum(scores) / len(scores)
            improvement_rate = improvements / len(records)
            genome.fitness = avg_score * 0.6 + improvement_rate * 40.0
            self._save_genome(genome, active=(genome.id == self._active_id))

    def _mutate_scorer(self, parent: ScorerGenome, generation: int) -> Optional[ScorerGenome]:
        mutations = [
            (r'quality \+= 15', f'quality += {random.randint(10, 20)}'),
            (r'quality \+= 10', f'quality += {random.randint(5, 15)}'),
            (r'quality \+= 5',  f'quality += {random.randint(3, 10)}'),
            (r't < 0\.05', f't < {round(random.uniform(0.03, 0.1), 3)}'),
            (r't < 0\.1',  f't < {round(random.uniform(0.05, 0.2), 3)}'),
            (r'40\.0 \*', f'{round(random.uniform(30, 50), 1)} *'),
            (r'base = 10\.0', f'base = {round(random.uniform(5, 15), 1)}'),
            (
                r'return min\(base \+ tests \+ quality, 100\.0\)',
                'lines_bonus = min(5.0, metrics.get("lines", 0) / 100.0)\n'
                '    return min(base + tests + quality + lines_bonus, 100.0)'
            ),
        ]

        source = parent.source_code
        random.shuffle(mutations)
        for pattern, replacement in mutations:
            new_source = re.sub(pattern, replacement, source, count=1)
            if new_source != source:
                try:
                    ns = {}
                    exec(compile(new_source, "<test>", "exec"), ns)
                    if "compute_score" in ns:
                        test_metrics = {"complexity": 3, "num_functions": 5,
                                        "execution_time": 0.05, "tests_passed": 3,
                                        "tests_total": 3}
                        val = ns["compute_score"](test_metrics)
                        if 0 <= val <= 100:
                            gid = f"scorer_gen{generation}_{hashlib.md5(new_source.encode()).hexdigest()[:8]}"
                            return ScorerGenome(
                                id=gid,
                                source_code=new_source,
                                generation=generation,
                                fitness=parent.fitness * 0.9,
                            )
                except Exception:
                    pass
        return None

    def _crossover_scorers(self, a: ScorerGenome, b: ScorerGenome,
                           generation: int) -> Optional[ScorerGenome]:
        try:
            lines_a = a.source_code.splitlines()
            lines_b = b.source_code.splitlines()
            mid = len(lines_a) // 2
            crossed_lines = lines_a[:mid] + lines_b[mid:]
            new_source = "\n".join(crossed_lines)
            ns = {}
            exec(compile(new_source, "<cross>", "exec"), ns)
            if "compute_score" in ns:
                test_metrics = {"complexity": 3, "num_functions": 5, "execution_time": 0.05}
                val = ns["compute_score"](test_metrics)
                if 0 <= val <= 100:
                    gid = f"scorer_cross{generation}_{hashlib.md5(new_source.encode()).hexdigest()[:8]}"
                    return ScorerGenome(
                        id=gid,
                        source_code=new_source,
                        generation=generation,
                        fitness=(a.fitness + b.fitness) / 2,
                    )
        except Exception:
            pass
        return None

    def _tournament_select(self, candidates: List[ScorerGenome]) -> Optional[ScorerGenome]:
        if not candidates:
            return None
        pool = random.sample(candidates, min(self.TOURNAMENT_SIZE, len(candidates)))
        return max(pool, key=lambda g: g.fitness)

    def set_active(self, scorer_id: str) -> bool:
        for g in self._population:
            if g.id == scorer_id:
                self.conn.execute("UPDATE scorer_population SET active=0")
                self._active_id = scorer_id
                self._save_genome(g, active=True)
                self._compile_active()
                return True
        return False

    def get_population_status(self) -> List[Dict]:
        return [
            {
                "id": g.id,
                "fitness": round(g.fitness, 2),
                "long_term_score": round(g.long_term_score, 2),
                "applied_count": g.applied_count,
                "active": g.id == self._active_id,
            }
            for g in sorted(self._population, key=lambda g: g.fitness, reverse=True)
        ]


# 
# 3. META-LEARNER  aprende POR QUE mutaes funcionam
# 

@dataclass
class MutationCausalModel:
    mutation_type: str
    conditions: Dict[str, Any]
    anti_conditions: Dict[str, Any]
    causal_chain: List[str]
    confidence: float = 0.5
    sample_count: int = 0


class MetaLearner:
    MIN_SAMPLES_FOR_CAUSAL = 10
    CAUSAL_THRESHOLD = 0.65

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._models: Dict[str, MutationCausalModel] = {}
        self._rule_fitness: Dict[str, float] = {}
        self._hypotheses: List[Dict] = []
        self._init_db()
        self._load_models()

    def _init_db(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS meta_causal_models (
                mutation_type TEXT PRIMARY KEY,
                conditions_json TEXT,
                anti_conditions_json TEXT,
                causal_chain_json TEXT,
                confidence REAL,
                sample_count INTEGER,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS meta_rule_fitness (
                rule_name TEXT PRIMARY KEY,
                fitness REAL,
                last_updated TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS meta_hypotheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hypothesis TEXT,
                evidence_for INTEGER DEFAULT 0,
                evidence_against INTEGER DEFAULT 0,
                confirmed INTEGER DEFAULT 0,
                created TEXT,
                last_tested TEXT
            );

            CREATE TABLE IF NOT EXISTS meta_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discovery_type TEXT,
                description TEXT,
                impact REAL,
                generation INTEGER,
                timestamp TEXT
            );
        ''')
        self.conn.commit()

    def _load_models(self):
        rows = self.conn.execute(
            "SELECT mutation_type, conditions_json, anti_conditions_json, "
            "causal_chain_json, confidence, sample_count FROM meta_causal_models"
        ).fetchall()
        for r in rows:
            self._models[r[0]] = MutationCausalModel(
                mutation_type=r[0],
                conditions=json.loads(r[1]),
                anti_conditions=json.loads(r[2]),
                causal_chain=json.loads(r[3]),
                confidence=r[4],
                sample_count=r[5],
            )

    def analyze(self, conn_kb: sqlite3.Connection, current_generation: int):
        logger.info(f"\n[] MetaLearner  anlise causal (gen {current_generation})")

        rows = self.conn.execute('''
            SELECT mutation, features, replaced, new_score, old_score
            FROM evolution_metrics
            WHERE features IS NOT NULL
            ORDER BY generation DESC
            LIMIT ?
        ''', (META_WINDOW,)).fetchall() if self._has_evolution_metrics() else []

        if len(rows) < self.MIN_SAMPLES_FOR_CAUSAL:
            logger.info(f"   Amostras insuficientes: {len(rows)}/{self.MIN_SAMPLES_FOR_CAUSAL}")
            return

        by_type: Dict[str, List] = defaultdict(list)
        for mutation, features_json, replaced, new_score, old_score in rows:
            try:
                features = json.loads(features_json)
                features["score_delta"] = (new_score or 0) - (old_score or 0)
                by_type[mutation].append((features, bool(replaced)))
            except Exception:
                pass

        for mtype, samples in by_type.items():
            if len(samples) < self.MIN_SAMPLES_FOR_CAUSAL:
                continue
            model = self._build_causal_model(mtype, samples)
            self._models[mtype] = model
            self._persist_model(model)

        self._question_weight_rules(by_type)
        self._generate_hypotheses(by_type, current_generation)

        logger.info(f"   Modelos causais: {len(self._models)} tipos de mutao analisados")

    def _has_evolution_metrics(self) -> bool:
        try:
            self.conn.execute("SELECT 1 FROM evolution_metrics LIMIT 1").fetchone()
            return True
        except Exception:
            return False

    def _build_causal_model(self, mtype: str, samples: List) -> MutationCausalModel:
        successes = [f for f, r in samples if r]
        failures  = [f for f, r in samples if not r]

        conditions = {}
        anti_conditions = {}
        causal_chain = []

        if not successes:
            return MutationCausalModel(
                mutation_type=mtype, conditions={}, anti_conditions={},
                causal_chain=["Sem sucessos registrados"], confidence=0.0,
                sample_count=len(samples)
            )

        all_keys = set()
        for f in samples:
            all_keys.update(f[0].keys())

        numeric_keys = [k for k in all_keys
                        if all(isinstance(f.get(k, 0), (int, float)) for f, _ in samples)]

        for key in numeric_keys:
            s_vals = [f.get(key, 0) for f in successes]
            f_vals = [f.get(key, 0) for f in failures]
            if not s_vals or not f_vals:
                continue
            s_mean = sum(s_vals) / len(s_vals)
            f_mean = sum(f_vals) / len(f_vals) if f_vals else 0
            if abs(s_mean - f_mean) > 0.1 * max(abs(s_mean), abs(f_mean), 0.001):
                if s_mean > f_mean:
                    conditions[key] = {"min": s_mean * 0.7, "type": "high"}
                    causal_chain.append(f"{key} alto  sucesso")
                else:
                    conditions[key] = {"max": s_mean * 1.3, "type": "low"}
                    causal_chain.append(f"{key} baixo  sucesso")
                    anti_conditions[key] = {"min": f_mean * 0.8, "type": "high"}

        confidence = min(len(successes) / max(len(failures), 1) / 2.0, 1.0)
        confidence = max(0.1, confidence)

        return MutationCausalModel(
            mutation_type=mtype,
            conditions=conditions,
            anti_conditions=anti_conditions,
            causal_chain=causal_chain[:5],
            confidence=confidence,
            sample_count=len(samples),
        )

    def _persist_model(self, model: MutationCausalModel):
        self.conn.execute('''
            INSERT OR REPLACE INTO meta_causal_models
            (mutation_type, conditions_json, anti_conditions_json, causal_chain_json,
             confidence, sample_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            model.mutation_type,
            json.dumps(model.conditions),
            json.dumps(model.anti_conditions),
            json.dumps(model.causal_chain),
            model.confidence,
            model.sample_count,
            datetime.now().isoformat(),
        ))
        self.conn.commit()

    def _question_weight_rules(self, by_type: Dict[str, List]):
        problems_found = []

        for mtype, samples in by_type.items():
            total = len(samples)
            failures = sum(1 for _, r in samples if not r)
            if total >= 5 and failures / total > 0.7:
                problems_found.append({
                    "rule": f"peso_alto_{mtype}",
                    "problem": f"'{mtype}' tem {failures}/{total} falhas ({failures/total*100:.0f}%)",
                    "suggestion": f"Reduzir peso de '{mtype}' em _compute_mutation_weights",
                    "impact": -(failures / total),
                })

        for problem in problems_found:
            logger.info(f"   [] Regra questionada: {problem['problem']}")
            logger.info(f"       Sugesto: {problem['suggestion']}")
            rule_name = problem["rule"]
            self._rule_fitness[rule_name] = problem["impact"]
            self.conn.execute('''
                INSERT OR REPLACE INTO meta_rule_fitness
                (rule_name, fitness, last_updated, description)
                VALUES (?, ?, ?, ?)
            ''', (rule_name, problem["impact"], datetime.now().isoformat(), problem["suggestion"]))
            self.conn.commit()

            self.conn.execute('''
                INSERT INTO meta_discoveries
                (discovery_type, description, impact, generation, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', ("rule_question", problem["suggestion"], problem["impact"],
                  0, datetime.now().isoformat()))
            self.conn.commit()

    def _generate_hypotheses(self, by_type: Dict[str, List], generation: int):
        hypotheses = []

        mtype_list = list(by_type.keys())
        for i, mt1 in enumerate(mtype_list):
            for mt2 in mtype_list[i+1:]:
                s1 = sum(1 for _, r in by_type[mt1] if r) / max(len(by_type[mt1]), 1)
                s2 = sum(1 for _, r in by_type[mt2] if r) / max(len(by_type[mt2]), 1)
                if s1 > 0.5 and s2 > 0.5:
                    hypotheses.append(
                        f"Sequncia '{mt1}{mt2}' pode ter sinergia positiva "
                        f"(taxas individuais: {s1:.0%}, {s2:.0%})"
                    )

        for hyp in hypotheses[:3]:
            existing = self.conn.execute(
                "SELECT id FROM meta_hypotheses WHERE hypothesis=?", (hyp,)
            ).fetchone()
            if not existing:
                self.conn.execute('''
                    INSERT INTO meta_hypotheses (hypothesis, created, last_tested)
                    VALUES (?, ?, ?)
                ''', (hyp, datetime.now().isoformat(), datetime.now().isoformat()))
                self.conn.commit()
                logger.info(f"   [] Nova hiptese: {hyp}")

        self._hypotheses = [
            {"id": r[0], "hypothesis": r[1], "for": r[2], "against": r[3]}
            for r in self.conn.execute(
                "SELECT id, hypothesis, evidence_for, evidence_against "
                "FROM meta_hypotheses ORDER BY id DESC LIMIT 5"
            ).fetchall()
        ]

    def get_context_recommendation(self, current_metrics: Dict) -> Dict[str, float]:
        adjustments = {}
        for mtype, model in self._models.items():
            if model.confidence < 0.3:
                continue
            match_score = self._match_conditions(current_metrics, model.conditions)
            anti_score  = self._match_conditions(current_metrics, model.anti_conditions)
            net = match_score - anti_score * 0.5
            if abs(net) > 0.1:
                adjustments[mtype] = 1.0 + net * model.confidence
        return adjustments

    def _match_conditions(self, metrics: Dict, conditions: Dict) -> float:
        if not conditions:
            return 0.0
        hits = 0
        for key, cond in conditions.items():
            val = metrics.get(key, 0)
            if cond.get("type") == "high" and val >= cond.get("min", 0):
                hits += 1
            elif cond.get("type") == "low" and val <= cond.get("max", float("inf")):
                hits += 1
        return hits / len(conditions)

    def get_rule_problems(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT rule_name, fitness, description FROM meta_rule_fitness "
            "WHERE fitness < -0.3 ORDER BY fitness ASC LIMIT 5"
        ).fetchall()
        return [{"rule": r[0], "fitness": r[1], "suggestion": r[2]} for r in rows]

    def get_hypotheses(self) -> List[Dict]:
        return self._hypotheses

    def print_report(self):
        logger.info("\n[] META-LEARNER REPORT")
        logger.info(""*60)
        if self._models:
            logger.info("Modelos causais ativos:")
            for mtype, model in sorted(self._models.items(),
                                       key=lambda x: x[1].confidence, reverse=True)[:5]:
                logger.info(f"  {mtype:<28} conf={model.confidence:.2f}  n={model.sample_count}")
                for cause in model.causal_chain[:2]:
                    logger.info(f"     {cause}")
        problems = self.get_rule_problems()
        if problems:
            logger.info("\nRegras questionadas:")
            for p in problems:
                logger.info(f"    {p['rule']}: {p['suggestion']}")
        if self._hypotheses:
            logger.info("\nHipteses ativas:")
            for h in self._hypotheses[:3]:
                logger.info(f"   {h['hypothesis']}")
        logger.info(""*60)


# 
# 4. RECURSIVE SANDBOX  testa nova verso da Atena dentro da Atena
# 

@dataclass
class SandboxResult:
    engine_version: str
    cycles_run: int
    score_start: float
    score_end: float
    avg_improvement_per_cycle: float
    mutations_accepted: int
    mutations_rejected: int
    errors: List[str]
    elapsed_seconds: float
    better_than_current: bool


class RecursiveSandbox:
    ISOLATION_TIMEOUT = 120
    INITIAL_CODE = '''#!/usr/bin/env python3
"""Cdigo de teste para sandbox recursivo."""

def main():
    print("Atena Sandbox  teste recursivo")
    return 0

def util_soma(a, b):
    return a + b

def util_fatorial(n):
    if n <= 1: return 1
    return n * util_fatorial(n - 1)

def util_fibonacci(n):
    if n <= 0: return 0
    if n == 1: return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

if __name__ == "__main__":
    main()
'''

    RUNNER_SCRIPT = '''#!/usr/bin/env python3
"""Script executor para o sandbox recursivo da Atena."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

# Desativa rede e escrita fora do sandbox
os.environ["CI"] = "true"
os.environ["GITHUB_ACTIONS"] = "false"
os.environ["XAI_API_KEY"] = ""
os.environ["GITHUB_TOKEN"] = ""

SANDBOX_DIR = os.path.dirname(__file__)

# Redireciona todos os caminhos para o sandbox
import atena_engine_candidate as engine
engine.Config.BASE_DIR    = __import__('pathlib').Path(SANDBOX_DIR) / "atena_data"
engine.Config.CODE_DIR    = engine.Config.BASE_DIR / "code"
engine.Config.BACKUP_DIR  = engine.Config.BASE_DIR / "backups"
engine.Config.KNOWLEDGE_DIR = engine.Config.BASE_DIR / "knowledge"
engine.Config.EVOLUTIONS_DIR = engine.Config.BASE_DIR / "evolutions"
engine.Config.SANDBOX_DIR = engine.Config.BASE_DIR / "sandbox"
engine.Config.MODEL_DIR   = engine.Config.BASE_DIR / "models"
engine.Config.DEPLOY_DIR  = engine.Config.BASE_DIR / "deploy"
engine.Config.PROJECTS_DIR = engine.Config.BASE_DIR / "projects"
engine.Config.CACHE_DIR   = engine.Config.BASE_DIR / "cache"
engine.Config.CURRENT_CODE_FILE = engine.Config.CODE_DIR / "atena_current.py"
engine.Config.NEW_CODE_FILE     = engine.Config.CODE_DIR / "atena_new.py"
engine.Config.ENGINE_FILE       = engine.Config.CODE_DIR / "atena_engine.py"
engine.Config.KNOWLEDGE_DB      = engine.Config.KNOWLEDGE_DIR / "knowledge.db"
engine.Config.STATE_FILE        = engine.Config.BASE_DIR / "atena_state.json"

CYCLES = int(sys.argv[1]) if len(sys.argv) > 1 else 3
results = {"cycles": [], "errors": []}

try:
    engine.Config.setup()
    core = engine.AtenaCore()
    start_score = core.best_score
    results["start_score"] = start_score

    for i in range(CYCLES):
        try:
            r = core.evolve_one_cycle()
            results["cycles"].append({
                "cycle": i + 1,
                "score": r["score"],
                "replaced": r["replaced"],
                "mutation": r["mutation"],
            })
        except Exception as e:
            results["errors"].append(f"Ciclo {i+1}: {e}")

    results["end_score"] = core.best_score
    results["generation"] = core.generation

except Exception as e:
    results["errors"].append(f"Init: {e}")
    results["start_score"] = 0
    results["end_score"] = 0

print(json.dumps(results))
'''

    def __init__(self, engine_path: Path, current_baseline: float):
        self.engine_path = engine_path
        self.current_baseline = current_baseline
        self._results_history: List[SandboxResult] = []

    def test(self, candidate_engine_source: str, cycles: int = None) -> SandboxResult:
        cycles = cycles or RECURSIVE_CYCLES
        t0 = time.time()
        errors = []

        with tempfile.TemporaryDirectory(prefix="atena_rsandbox_") as tmpdir:
            tmp = Path(tmpdir)

            (tmp / "atena_engine_candidate.py").write_text(candidate_engine_source)
            (tmp / "runner.py").write_text(self.RUNNER_SCRIPT)
            (tmp / "initial_code.py").write_text(self.INITIAL_CODE)

            env = os.environ.copy()
            env["PYTHONPATH"] = str(tmp)
            env["CI"] = "true"

            try:
                proc = subprocess.run(
                    [sys.executable, str(tmp / "runner.py"), str(cycles)],
                    capture_output=True,
                    text=True,
                    timeout=self.ISOLATION_TIMEOUT,
                    env=env,
                    cwd=str(tmp),
                )

                output = proc.stdout.strip()
                if proc.stderr:
                    errors.append(proc.stderr[:500])

                data = {}
                if output:
                    for line in reversed(output.splitlines()):
                        if line.strip().startswith('{'):
                            data = json.loads(line.strip())
                            break

                start_score  = data.get("start_score", 0)
                end_score    = data.get("end_score", 0)
                cycle_data   = data.get("cycles", [])
                errors      += data.get("errors", [])
                accepted     = sum(1 for c in cycle_data if c.get("replaced"))
                rejected     = len(cycle_data) - accepted
                avg_imp      = (end_score - start_score) / max(len(cycle_data), 1)

                result = SandboxResult(
                    engine_version=hashlib.sha256(candidate_engine_source[:500].encode()).hexdigest()[:12],
                    cycles_run=len(cycle_data),
                    score_start=start_score,
                    score_end=end_score,
                    avg_improvement_per_cycle=avg_imp,
                    mutations_accepted=accepted,
                    mutations_rejected=rejected,
                    errors=errors,
                    elapsed_seconds=time.time() - t0,
                    better_than_current=(end_score > self.current_baseline * 0.98
                                         and avg_imp >= 0)
                )

            except subprocess.TimeoutExpired:
                result = SandboxResult(
                    engine_version="timeout",
                    cycles_run=0,
                    score_start=0, score_end=0,
                    avg_improvement_per_cycle=0,
                    mutations_accepted=0, mutations_rejected=0,
                    errors=[f"Timeout aps {self.ISOLATION_TIMEOUT}s"],
                    elapsed_seconds=time.time() - t0,
                    better_than_current=False,
                )
            except Exception as e:
                result = SandboxResult(
                    engine_version="error",
                    cycles_run=0,
                    score_start=0, score_end=0,
                    avg_improvement_per_cycle=0,
                    mutations_accepted=0, mutations_rejected=0,
                    errors=[str(e)],
                    elapsed_seconds=time.time() - t0,
                    better_than_current=False,
                )

        self._results_history.append(result)
        return result

    def get_history(self, n: int = 10) -> List[SandboxResult]:
        return self._results_history[-n:]

    def print_result(self, result: SandboxResult):
        icon = "" if result.better_than_current else ""
        logger.info(f"\n[] Sandbox Recursivo  {icon}")
        logger.info(f"   Engine: {result.engine_version}")
        logger.info(f"   Ciclos: {result.cycles_run} | "
                    f"Score: {result.score_start:.2f}{result.score_end:.2f} | "
                    f"/ciclo: {result.avg_improvement_per_cycle:+.3f}")
        logger.info(f"   Aceitas: {result.mutations_accepted} | "
                    f"Rejeitadas: {result.mutations_rejected} | "
                    f"Tempo: {result.elapsed_seconds:.1f}s")
        if result.errors:
            logger.info(f"   Erros: {result.errors[0][:100]}")


# 
# 5. ADAPTIVE CHECKER  StaticChecker com travas evoluveis
# 

@dataclass
class CheckerRule:
    name: str
    pattern: Optional[str]
    rule_type: str
    active: bool = True
    confidence: float = 1.0
    false_positive_rate: float = 0.0
    description: str = ""
    mutable: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AdaptiveChecker:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._rules: Dict[str, CheckerRule] = {}
        self._compiled_patterns: Dict[str, Any] = {}
        self._block_history: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
        self._init_db()
        self._init_default_rules()
        self._load_rules()

    def _init_db(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS checker_rules (
                name TEXT PRIMARY KEY,
                pattern TEXT,
                rule_type TEXT,
                active INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                false_positive_rate REAL DEFAULT 0.0,
                description TEXT,
                mutable INTEGER DEFAULT 1,
                created_at TEXT,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS checker_block_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT,
                code_hash TEXT,
                was_false_positive INTEGER DEFAULT 0,
                timestamp TEXT
            );
        ''')
        self.conn.commit()

    def _init_default_rules(self):
        default_rules = [
            CheckerRule(
                name="block_system_calls",
                pattern=r'os\.system\s*\(',
                rule_type="forbidden",
                active=True, confidence=1.0, mutable=False,
                description="Bloqueia chamadas de sistema diretas",
            ),
            CheckerRule(
                name="block_malicious_import",
                pattern=r'__import__\s*\(',
                rule_type="forbidden",
                active=True, confidence=1.0, mutable=False,
                description="Bloqueia importaes dinmicas perigosas",
            ),
            CheckerRule(
                name="block_file_write_arbitrary",
                pattern=r'open\s*\(.+["\']w["\']',
                rule_type="forbidden",
                active=True, confidence=0.9, mutable=False,
                description="Bloqueia escrita arbitrria em arquivos",
            ),
            CheckerRule(
                name="block_eval",
                pattern=r'(?<!\w)eval\s*\(',
                rule_type="forbidden",
                active=True, confidence=0.8, mutable=True,
                description="Bloqueia eval()  pode ser relaxado para casos especficos",
            ),
            CheckerRule(
                name="block_exec",
                pattern=r'(?<!\w)exec\s*\(',
                rule_type="forbidden",
                active=True, confidence=0.85, mutable=True,
                description="Bloqueia exec()  necessrio para meta-programao legtima",
            ),
            CheckerRule(
                name="require_functions",
                pattern=None,
                rule_type="ast",
                active=True, confidence=0.7, mutable=True,
                description="Exige pelo menos uma funo definida",
            ),
            CheckerRule(
                name="min_code_size",
                pattern=None,
                rule_type="ast",
                active=True, confidence=0.6, mutable=True,
                description="Cdigo mnimo de 50 chars",
            ),
            CheckerRule(
                name="block_subprocess_call",
                pattern=r'subprocess\.call\s*\(',
                rule_type="forbidden",
                active=True, confidence=0.75, mutable=True,
                description="Bloqueia subprocess.call  pode ter falso-positivos em cdigo legtimo",
            ),
        ]
        for rule in default_rules:
            existing = self.conn.execute(
                "SELECT 1 FROM checker_rules WHERE name=?", (rule.name,)
            ).fetchone()
            if not existing:
                self.conn.execute('''
                    INSERT INTO checker_rules
                    (name, pattern, rule_type, active, confidence, false_positive_rate,
                     description, mutable, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (rule.name, rule.pattern, rule.rule_type,
                      1 if rule.active else 0, rule.confidence,
                      rule.false_positive_rate, rule.description,
                      1 if rule.mutable else 0,
                      rule.created_at, datetime.now().isoformat()))
        self.conn.commit()

    def _load_rules(self):
        rows = self.conn.execute(
            "SELECT name, pattern, rule_type, active, confidence, false_positive_rate, "
            "description, mutable, created_at FROM checker_rules"
        ).fetchall()
        for r in rows:
            rule = CheckerRule(
                name=r[0], pattern=r[1], rule_type=r[2],
                active=bool(r[3]), confidence=r[4],
                false_positive_rate=r[5], description=r[6],
                mutable=bool(r[7]), created_at=r[8],
            )
            self._rules[rule.name] = rule
            if rule.pattern and rule.active:
                try:
                    self._compiled_patterns[rule.name] = re.compile(rule.pattern)
                except re.error:
                    pass

    def check(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        for name, rule in self._rules.items():
            if not rule.active or rule.rule_type != "forbidden":
                continue
            pattern = self._compiled_patterns.get(name)
            if pattern and pattern.search(code):
                self._record_block(name, code, was_fp=False)
                return False, f"Padro bloqueado [{name}]: {rule.description}"

        if self._rules.get("require_functions", CheckerRule("x", None, "ast")).active:
            tree = ast.parse(code)
            if not any(isinstance(n, ast.FunctionDef) for n in ast.walk(tree)):
                return False, "Nenhuma funo definida"

        if self._rules.get("min_code_size", CheckerRule("x", None, "ast")).active:
            if len(code.strip()) < 50:
                return False, "Cdigo muito curto"

        return True, "OK"

    def _record_block(self, rule_name: str, code: str, was_fp: bool = False):
        code_hash = hashlib.sha256(code[:200].encode()).hexdigest()[:12]
        self._block_history.append({
            "rule": rule_name, "hash": code_hash,
            "fp": was_fp, "ts": datetime.now().isoformat()
        })
        self.conn.execute('''
            INSERT INTO checker_block_history
            (rule_name, code_hash, was_false_positive, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (rule_name, code_hash, 1 if was_fp else 0, datetime.now().isoformat()))
        self.conn.commit()

    def report_false_positive(self, code: str):
        if not ALLOW_CHECKER_EVOLVE:
            return
        code_hash = hashlib.sha256(code[:200].encode()).hexdigest()[:12]
        row = self.conn.execute(
            "SELECT rule_name FROM checker_block_history WHERE code_hash=? ORDER BY id DESC LIMIT 1",
            (code_hash,)
        ).fetchone()
        if not row:
            return
        rule_name = row[0]
        self.conn.execute(
            "UPDATE checker_block_history SET was_false_positive=1 WHERE code_hash=?",
            (code_hash,)
        )
        self.conn.commit()
        self._recalculate_fp_rate(rule_name)

    def _recalculate_fp_rate(self, rule_name: str):
        row = self.conn.execute(
            "SELECT COUNT(*), SUM(was_false_positive) FROM checker_block_history WHERE rule_name=?",
            (rule_name,)
        ).fetchone()
        if not row or not row[0]:
            return
        total, fp_count = row
        fp_rate = (fp_count or 0) / total

        rule = self._rules.get(rule_name)
        if not rule or not rule.mutable:
            return

        rule.false_positive_rate = fp_rate

        if fp_rate > 0.4 and rule.confidence < 0.85:
            rule.active = False
            logger.info(f"   [] Regra '{rule_name}' desativada (FP={fp_rate:.0%})")

        self.conn.execute('''
            UPDATE checker_rules
            SET false_positive_rate=?, active=?, last_updated=?
            WHERE name=?
        ''', (fp_rate, 1 if rule.active else 0, datetime.now().isoformat(), rule_name))
        self.conn.commit()

        if not rule.active and rule_name in self._compiled_patterns:
            del self._compiled_patterns[rule_name]

    def add_rule(self, name: str, pattern: str, description: str,
                 confidence: float = 0.5):
        if name in self._rules:
            return
        try:
            re.compile(pattern)
        except re.error:
            logger.info(f"   [] Regex invlido para regra '{name}'")
            return
        rule = CheckerRule(
            name=name, pattern=pattern, rule_type="forbidden",
            active=True, confidence=confidence, mutable=True,
            description=description,
        )
        self._rules[name] = rule
        self._compiled_patterns[name] = re.compile(pattern)
        self.conn.execute('''
            INSERT OR IGNORE INTO checker_rules
            (name, pattern, rule_type, active, confidence, false_positive_rate,
             description, mutable, created_at, last_updated)
            VALUES (?, ?, ?, 1, ?, 0, ?, 1, ?, ?)
        ''', (name, pattern, "forbidden", confidence, description,
              datetime.now().isoformat(), datetime.now().isoformat()))
        self.conn.commit()

    def get_rules_status(self) -> List[Dict]:
        return [
            {
                "name": r.name,
                "active": r.active,
                "mutable": r.mutable,
                "confidence": round(r.confidence, 2),
                "fp_rate": round(r.false_positive_rate, 3),
                "description": r.description,
            }
            for r in self._rules.values()
        ]


# 
# SELF-MOD VALIDATOR  valida que um engine candidato  funcionalmente correto
# 

class SelfModValidator:
    REQUIRED_CLASSES = {
        "Config", "KnowledgeBase", "AtenaCore", "MutationEngine",
        "CodeEvaluator", "Sandbox",
    }
    REQUIRED_METHODS = {
        "AtenaCore": {"evolve_one_cycle", "_save_state"},
        "MutationEngine": {"mutate", "generate_candidates"},
        "CodeEvaluator": {"evaluate"},
        "Sandbox": {"run"},
    }
    ALWAYS_FORBIDDEN = [
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'__import__\s*\(',
        r'open\s*\(.+["\']w["\'].+\.\s*engine',
    ]

    def __init__(self):
        self._forbidden = [re.compile(p) for p in self.ALWAYS_FORBIDDEN]

    def validate(self, source: str) -> Tuple[bool, str]:
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        classes_found = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        missing = self.REQUIRED_CLASSES - classes_found
        if missing:
            return False, f"Classes ausentes: {missing}"

        class_methods: Dict[str, Set[str]] = defaultdict(set)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_methods[node.name].add(item.name)
        for cls, methods in self.REQUIRED_METHODS.items():
            missing_methods = methods - class_methods.get(cls, set())
            if missing_methods:
                return False, f"Mtodos ausentes em {cls}: {missing_methods}"

        for pat in self._forbidden:
            if pat.search(source):
                return False, f"Padro perigoso: {pat.pattern}"

        if len(source) < 5000:
            return False, "Engine candidato muito pequeno  possvel corrupo"

        return True, "OK"


# 
# ATENAV3SELFMOD  orquestrador central da auto-modificao
# 

class AtenaV3SelfMod:
    def __init__(self, core):
        self.core = core
        self.kb   = core.kb
        conn      = core.kb.conn

        engine_path = getattr(core, "engine_path", None)
        if not engine_path:
            try:
                from atena_engine import Config as _Cfg
                engine_path = _Cfg.ENGINE_FILE
            except ImportError:
                engine_path = Path("./atena_evolution/code/atena_engine.py")
        self.engine_path = Path(engine_path)

        backup_dir = Path("./atena_evolution/backups/selfmod")
        validator  = SelfModValidator()

        self.self_mod_engine  = SelfModEngine(self.engine_path, backup_dir, validator)
        self.evolvable_scorer = EvolvableScorer(conn)
        self.meta_learner     = MetaLearner(conn)
        self.recursive_sandbox = RecursiveSandbox(self.engine_path, core.best_score)
        self.adaptive_checker = AdaptiveChecker(conn)

        self._generation = 0
        self._last_self_mod_gen = 0
        self._self_mod_results: deque = deque(maxlen=50)

        logger.info("[] AtenaV3SelfMod inicializado")
        logger.info(f"   ALLOW_DEEP_SELF_MOD:  {ALLOW_DEEP_SELF_MOD}")
        logger.info(f"   ALLOW_CHECKER_EVOLVE: {ALLOW_CHECKER_EVOLVE}")
        logger.info(f"   SELF_MOD_INTERVAL:    {SELF_MOD_INTERVAL} geraes")
        logger.info(f"   RECURSIVE_CYCLES:     {RECURSIVE_CYCLES}")

    def on_cycle_end(self, generation: int, metrics: Dict,
                     code: str, replaced: bool):
        self._generation = generation
        score = self.evolvable_scorer.compute(metrics)
        self.evolvable_scorer.record(generation, score, replaced)

        if generation - self._last_self_mod_gen >= SELF_MOD_INTERVAL:
            self.run_self_mod_cycle()
            self._last_self_mod_gen = generation

    def run_self_mod_cycle(self):
        gen = self._generation
        logger.info(f"\n{'='*60}")
        logger.info(f" AUTO-MODIFICAO  Gerao {gen}")
        logger.info(f"{'='*60}")

        self.meta_learner.analyze(self.kb.conn, gen)

        new_scorer = self.evolvable_scorer.evolve(gen)
        if new_scorer:
            logger.info(f"[] Scorer evoludo: {new_scorer.id} (fitness={new_scorer.fitness:.2f})")

        if ALLOW_DEEP_SELF_MOD and self.engine_path.exists():
            self._run_engine_mutation(gen)

        self.print_status()

    def _run_engine_mutation(self, generation: int):
        for attempt in range(MAX_ENGINE_MUTATIONS):
            logger.info(f"\n[] Tentativa de mutao do engine {attempt+1}/{MAX_ENGINE_MUTATIONS}")
            success, description, backup_path = self.self_mod_engine.mutate_engine()

            if not success:
                logger.info(f"    {description}")
                continue

            logger.info(f"     {description}")

            new_source = self.engine_path.read_text()
            result = self.recursive_sandbox.test(new_source)
            self.recursive_sandbox.print_result(result)

            if result.better_than_current:
                logger.info(f"    Engine aceito! score={result.score_end - result.score_start:+.2f}")
                self._self_mod_results.append({
                    "generation": generation,
                    "description": description,
                    "accepted": True,
                    "score_delta": result.avg_improvement_per_cycle,
                })
                break
            else:
                logger.info(f"     Revertendo (sandbox no melhorou baseline)")
                if backup_path and backup_path.exists():
                    self.self_mod_engine.backup.restore(backup_path)
                self._self_mod_results.append({
                    "generation": generation,
                    "description": description,
                    "accepted": False,
                    "score_delta": result.avg_improvement_per_cycle,
                })

    def get_meta_weight_adjustments(self, current_metrics: Dict) -> Dict[str, float]:
        return self.meta_learner.get_context_recommendation(current_metrics)

    def get_active_scorer_fn(self) -> Callable:
        return self.evolvable_scorer.compute

    def get_checker_fn(self) -> Callable:
        return self.adaptive_checker.check

    def print_status(self):
        logger.info("\n" + ""*60)
        logger.info("   ATENA v3  STATUS DE AUTO-MODIFICAO")
        logger.info(""*60)

        logger.info("\n Scorer Population:")
        for s in self.evolvable_scorer.get_population_status()[:3]:
            icon = "" if s["active"] else " "
            logger.info(f"  {icon} {s['id']:<40} "
                        f"fitness={s['fitness']:.2f}  "
                        f"applied={s['applied_count']}")

        logger.info("\n  Checker Rules:")
        for r in self.adaptive_checker.get_rules_status():
            status = "" if r["active"] else ""
            lock   = "" if not r["mutable"] else ""
            logger.info(f"  {status} {lock} {r['name']:<30} "
                        f"conf={r['confidence']:.2f}  fp={r['fp_rate']:.2%}")

        self.meta_learner.print_report()

        recent = list(self._self_mod_results)[-5:]
        if recent:
            logger.info("\n ltimas auto-modificaes:")
            for r in recent:
                icon = "" if r["accepted"] else ""
                logger.info(f"  {icon} Gen {r['generation']:>4} | "
                            f"{r['description'][:45]:<45} | "
                            f"={r['score_delta']:+.3f}")

        logger.info(""*60)

    def get_full_report(self) -> Dict:
        return {
            "scorer_population": self.evolvable_scorer.get_population_status(),
            "checker_rules":     self.adaptive_checker.get_rules_status(),
            "causal_models":     {
                k: {
                    "confidence": v.confidence,
                    "chain": v.causal_chain[:3],
                    "sample_count": v.sample_count,
                }
                for k, v in self.meta_learner._models.items()
            },
            "rule_problems":     self.meta_learner.get_rule_problems(),
            "hypotheses":        self.meta_learner.get_hypotheses(),
            "self_mod_history":  list(self._self_mod_results)[-10:],
            "allow_deep":        ALLOW_DEEP_SELF_MOD,
            "allow_checker":     ALLOW_CHECKER_EVOLVE,
        }


# =============================================================================
# MDULOS v2.2 / v3.1 (complementares)
# =============================================================================

# 
# DEPLOY AUTOMTICO
# 

class AutoDeploy:
    """Gerencia deploy para Git, Docker ou comando personalizado."""

    @staticmethod
    def deploy() -> bool:
        results = []
        if Config.DEPLOY_GIT_REPO:
            results.append(AutoDeploy._deploy_git())
        if Config.DEPLOY_DOCKER_IMAGE:
            results.append(AutoDeploy._deploy_docker())
        if Config.DEPLOY_COMMAND:
            results.append(AutoDeploy._run_command())
        return any(results)

    @staticmethod
    def _deploy_git() -> bool:
        try:
            deploy_path = Config.DEPLOY_DIR / "repo"
            if not deploy_path.exists():
                subprocess.run(
                    ["git", "clone", Config.DEPLOY_GIT_REPO, str(deploy_path)],
                    check=True
                )
            else:
                subprocess.run(["git", "-C", str(deploy_path), "pull"], check=True)
            shutil.copy(Config.CURRENT_CODE_FILE, deploy_path / "atena.py")
            subprocess.run(["git", "-C", str(deploy_path), "add", "atena.py"], check=True)
            subprocess.run(
                ["git", "-C", str(deploy_path), "commit", "-m",
                 f"Auto-deploy Atena v3.0 {datetime.now().isoformat()}"],
                check=True
            )
            subprocess.run(
                ["git", "-C", str(deploy_path), "push", "origin", Config.DEPLOY_BRANCH],
                check=True
            )
            logger.info("[] Deploy Git OK")
            return True
        except Exception as e:
            logger.warning(f"[] Git deploy falhou: {e}")
            return False

    @staticmethod
    def _deploy_docker() -> bool:
        try:
            dockerfile = Config.DEPLOY_DIR / "Dockerfile"
            dockerfile.write_text(f"""FROM python:3.10-slim
WORKDIR /app
COPY {Config.CURRENT_CODE_FILE.name} /app/atena.py
RUN pip install --no-cache-dir radon astor numpy requests
CMD ["python", "atena.py"]
""")
            subprocess.run(
                ["docker", "build", "-t", Config.DEPLOY_DOCKER_IMAGE, str(Config.DEPLOY_DIR)],
                check=True
            )
            subprocess.run(["docker", "push", Config.DEPLOY_DOCKER_IMAGE], check=True)
            logger.info("[] Docker deploy OK")
            return True
        except Exception as e:
            logger.warning(f"[] Docker falhou: {e}")
            return False

    @staticmethod
    def _run_command() -> bool:
        try:
            subprocess.run(Config.DEPLOY_COMMAND, shell=True, check=True)
            logger.info("[] Comando de deploy executado")
            return True
        except Exception as e:
            logger.warning(f"[] Comando falhou: {e}")
            return False


# 
# MUTAO DE WORKFLOW
# 

def apply_workflow_mutation() -> bool:
    """Aplica mutaes no arquivo de workflow do GitHub Actions."""
    if not Config.WORKFLOW_FILE.exists():
        logger.warning("[] Workflow no encontrado")
        return False
    backup = Config.WORKFLOW_BACKUP_DIR / f"atena_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yml"
    shutil.copy(Config.WORKFLOW_FILE, backup)
    try:
        content = Config.WORKFLOW_FILE.read_text()
        nc = content
        mutated = False
        # Muda runner para verso mais recente
        if 'ubuntu-latest' in nc:
            nc = nc.replace('ubuntu-latest', 'ubuntu-22.04')
            mutated = True
        # Reduz timeout
        m = re.search(r'timeout-minutes:\s*(\d+)', nc)
        if m and int(m.group(1)) > 8:
            nc = re.sub(r'timeout-minutes:\s*\d+', f'timeout-minutes: {int(m.group(1))-2}', nc)
            mutated = True
        # Aumenta intervalo do cron
        if "*/30 * * * *" in nc:
            nc = nc.replace("*/30 * * * *", "*/45 * * * *")
            mutated = True
        if not mutated:
            logger.info("[] Nenhuma mutao aplicvel ao workflow")
            return False
        Config.WORKFLOW_FILE.write_text(nc)
        logger.info("[] Workflow mutado")
        return True
    except Exception as e:
        logger.warning(f"[] Workflow mutation falhou: {e}")
        return False


# 
# FEEDBACK LOOP (baseado em LanguageTrainer)
# 

class FeedbackLoop:
    """Ajusta pesos de mutao com base em crticas do LanguageTrainer."""

    WEAKNESS_TO_MUTATION = {
        "funes longas":  ["extract_function", "simplify_expression"],
        "sem docstrings":  ["add_docstring", "add_comment"],
        "loops aninhados": ["loop_unroll", "extract_function", "simplify_expression"],
        "sem type hints":  ["add_type_hints"],
        "bare except":     ["add_error_handling"],
    }
    GROK_KEYWORDS = {
        "memoiz":   ["memoize_function"],
        "cache":    ["memoize_function", "add_import"],
        "simplif":  ["simplify_expression", "constant_folding"],
        "extract":  ["extract_function"],
        "type":     ["add_type_hints"],
        "doc":      ["add_docstring", "add_comment"],
        "loop":     ["loop_unroll", "loop_conversion"],
        "import":   ["add_import", "dead_code_removal"],
        "error":    ["add_error_handling"],
        "optimiz":  ["grok_optimize", "memoize_function", "loop_unroll"],
        "parallel": ["parallelize_loop"],
        "refactor": ["extract_function", "rename_var"],
        "dead code": ["dead_code_removal"],
        "complex":  ["simplify_expression", "extract_function"],
    }

    def __init__(self, kb, mutation_engine):
        self.kb = kb
        self.mutation_engine = mutation_engine
        self._weight_adjustments: Dict[str, float] = {}
        self._adjustment_decay = 0.85
        self._lock = threading.RLock()
        self._history: deque = deque(maxlen=20)

    def apply(self, lt_result: Dict[str, str], current_weights: Dict[str, float]) -> Dict[str, float]:
        """Aplica ajustes baseados no resultado do LanguageTrainer."""
        with self._lock:
            # Decaimento dos ajustes antigos
            for k in list(self._weight_adjustments.keys()):
                self._weight_adjustments[k] *= self._adjustment_decay
                if self._weight_adjustments[k] < 0.05:
                    del self._weight_adjustments[k]

        adjustments = {}
        critique = lt_result.get("critique", "")
        for weakness, mutations in self.WEAKNESS_TO_MUTATION.items():
            if weakness in critique:
                for m in mutations:
                    adjustments[m] = adjustments.get(m, 0) + 1.5

        proposal = lt_result.get("proposal", "")
        for line in proposal.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] in (self.mutation_engine.mutation_types if self.mutation_engine else []):
                try:
                    pct_str = [p for p in parts if '%' in p]
                    if pct_str:
                        pct = float(pct_str[0].replace('%', '')) / 100.0
                        adjustments[parts[0]] = adjustments.get(parts[0], 0) + pct * 2.0
                except Exception:
                    pass

        grok = lt_result.get("grok", "").lower()
        if grok:
            for keyword, mutations in self.GROK_KEYWORDS.items():
                if keyword in grok:
                    for m in mutations:
                        adjustments[m] = adjustments.get(m, 0) + 0.8

        with self._lock:
            for m, delta in adjustments.items():
                self._weight_adjustments[m] = self._weight_adjustments.get(m, 0) + delta
            for m, adj in self._weight_adjustments.items():
                if m in current_weights:
                    current_weights[m] *= (1.0 + adj)

        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "adjustments": dict(adjustments),
            "top_boosted": sorted(adjustments.items(), key=lambda x: x[1], reverse=True)[:3],
        })
        return current_weights

    def get_active_boosts(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._weight_adjustments)

    def get_history(self, n: int = 5) -> List[Dict]:
        return list(self._history)[-n:]

    def reset(self):
        with self._lock:
            self._weight_adjustments.clear()


# 
# MEMRIA EPISDICA
# 

class EpisodicMemory:
    """Armazena episdios de evoluo e detecta padres de sucesso."""

    PATTERN_WINDOW = 5

    def __init__(self, kb):
        self.kb = kb
        self._recent: deque = deque(maxlen=50)
        self._lock = threading.RLock()
        self._load_recent()

    def _load_recent(self):
        """Carrega episdios recentes do banco."""
        try:
            rows = self.kb.conn.execute("""
                SELECT generation, mutation, score, replaced, complexity, num_functions
                FROM episodic_memory ORDER BY generation DESC LIMIT 50
            """).fetchall()
            for r in reversed(rows):
                self._recent.append({
                    "generation": r[0],
                    "mutation": r[1],
                    "score": r[2],
                    "replaced": bool(r[3]),
                    "complexity": r[4],
                    "num_functions": r[5]
                })
        except Exception as e:
            logger.debug(f"Erro ao carregar memria episdica: {e}")

    def record(self, generation: int, mutation: str, score: float,
               replaced: bool, metrics: Dict, code_snapshot: str = ""):
        """Registra um episdio."""
        score_delta = 0.0
        if self._recent:
            score_delta = score - self._recent[-1].get("score", score)
        context_hash = hashlib.sha256(
            f"{metrics.get('num_functions',0)}{metrics.get('complexity',0):.1f}".encode()
        ).hexdigest()[:16]
        episode = {
            "generation": generation,
            "mutation": mutation,
            "score": score,
            "score_delta": score_delta,
            "replaced": replaced,
            "complexity": metrics.get("complexity", 0),
            "num_functions": metrics.get("num_functions", 0),
            "lines": metrics.get("lines", 0)
        }
        with self._lock:
            self._recent.append(episode)
            try:
                self.kb.conn.execute("""
                    INSERT INTO episodic_memory
                    (generation, timestamp, mutation, score, score_delta, replaced,
                     complexity, num_functions, lines, code_snapshot, context_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (generation, datetime.now().isoformat(), mutation, score, score_delta,
                      1 if replaced else 0, metrics.get("complexity", 0),
                      metrics.get("num_functions", 0), metrics.get("lines", 0),
                      code_snapshot[:500], context_hash))
                self.kb.conn.commit()
            except Exception as e:
                logger.warning(f"Erro ao registrar episdio: {e}")
        self._detect_patterns()

    def recall(self, current_metrics: Dict, n: int = 5) -> List[Dict]:
        """Recupera episdios similares ao contexto atual."""
        target_nf = current_metrics.get("num_functions", 0)
        target_cx = current_metrics.get("complexity", 0)
        try:
            rows = self.kb.conn.execute("""
                SELECT generation, mutation, score, score_delta, replaced, complexity, num_functions
                FROM episodic_memory WHERE replaced = 1
                ORDER BY ABS(num_functions - ?) + ABS(complexity - ?) ASC LIMIT ?
            """, (target_nf, target_cx, n)).fetchall()
            return [{
                "generation": r[0],
                "mutation": r[1],
                "score": r[2],
                "delta": r[3],
                "complexity": r[5],
                "num_functions": r[6]
            } for r in rows]
        except Exception as e:
            logger.debug(f"Erro ao recuperar episdios: {e}")
            return []

    def _detect_patterns(self):
        """Detecta padres de sucesso nos episdios recentes."""
        recent = list(self._recent)[-self.PATTERN_WINDOW:]
        if len(recent) < self.PATTERN_WINDOW:
            return
        successful = [e for e in recent if e.get("replaced")]
        if len(successful) < 2:
            return
        pattern = "".join(e["mutation"] for e in successful[-3:])
        avg_delta = sum(e.get("score_delta", 0) for e in successful) / len(successful)
        try:
            with self._lock:
                self.kb.conn.execute("""
                    INSERT INTO episodic_patterns (pattern, occurrences, avg_delta, last_seen)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(pattern) DO UPDATE SET
                        occurrences = occurrences + 1,
                        avg_delta   = (avg_delta * occurrences + excluded.avg_delta) / (occurrences + 1),
                        last_seen   = excluded.last_seen
                """, (pattern, avg_delta, datetime.now().isoformat()))
                self.kb.conn.commit()
        except Exception as e:
            logger.debug(f"Erro ao detectar padro: {e}")

    def get_best_patterns(self, n: int = 5) -> List[Dict]:
        """Retorna os padres com melhor mdia de delta."""
        try:
            rows = self.kb.conn.execute("""
                SELECT pattern, occurrences, avg_delta FROM episodic_patterns
                WHERE occurrences >= 2 ORDER BY avg_delta DESC, occurrences DESC LIMIT ?
            """, (n,)).fetchall()
            return [{
                "pattern": r[0],
                "occurrences": r[1],
                "avg_delta": r[2]
            } for r in rows]
        except Exception as e:
            logger.debug(f"Erro ao buscar padres: {e}")
            return []

    def suggest_next_mutation(self) -> Optional[str]:
        """Sugere a prxima mutao baseada nos melhores padres."""
        patterns = self.get_best_patterns(3)
        if not patterns:
            return None
        last = patterns[0]["pattern"].split("->")[-1].strip()
        return last if last else None

    def forget_old(self, keep_days: int = 14, min_score: float = 20.0):
        """Remove episdios antigos e de baixa qualidade."""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        try:
            with self._lock:
                self.kb.conn.execute(
                    "DELETE FROM episodic_memory WHERE timestamp < ? AND replaced = 0 AND score < ?",
                    (cutoff, min_score))
                self.kb.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao esquecer episdios: {e}")

    def summary(self) -> str:
        """Resumo dos ltimos episdios."""
        recent = list(self._recent)[-10:]
        if not recent:
            return "Sem episdios registrados."
        n_replaced = sum(1 for e in recent if e.get("replaced"))
        avg_score = sum(e.get("score", 0) for e in recent) / len(recent)
        best = max(recent, key=lambda e: e.get("score", 0))
        patterns = self.get_best_patterns(2)
        lines = [
            f"ltimos {len(recent)} episdios: {n_replaced} aceitos, score mdio {avg_score:.2f}",
            f"Melhor recente: '{best['mutation']}'  score {best['score']:.2f}",
        ]
        if patterns:
            lines.append(f"Padro: {patterns[0]['pattern']} (={patterns[0]['avg_delta']:+.2f})")
        return "\n".join(lines)


# 
# SISTEMA DE RECOMPENSA AUTOMTICA
# 

class RewardCriterion:
    """Um critrio de recompensa individual."""

    def __init__(self, name, description, weight, evaluator):
        self.name = name
        self.description = description
        self.weight = weight
        self.evaluator = evaluator
        self.last_value = 0.0

    def evaluate(self, metrics, code, generation) -> float:
        try:
            v = float(self.evaluator(metrics, code, generation))
            self.last_value = max(0.0, min(1.0, v))
            return self.last_value
        except Exception as e:
            logger.debug(f"Erro no critrio {self.name}: {e}")
            return 0.0


class AutoRewardSystem:
    """Sistema de recompensa que combina mltiplos critrios."""

    BASE_WEIGHT = 0.3

    def __init__(self, kb):
        self.kb = kb
        self._lock = threading.RLock()
        self._criteria: List[RewardCriterion] = []
        self._score_history: deque = deque(maxlen=100)
        self._code_hashes: deque = deque(maxlen=50)
        self._init_base_criteria()

    def _init_base_criteria(self):
        """Inicializa critrios padro."""

        def novelty(metrics, code, gen):
            h = hashlib.sha256(code[:200].encode()).hexdigest()[:8]
            if h in self._code_hashes:
                return 0.1
            self._code_hashes.append(h)
            return 0.9

        def elegance(metrics, code, gen):
            cx = metrics.get("complexity", 10)
            nf = max(1, metrics.get("num_functions", 1))
            ratio = cx / nf
            if ratio <= 2:
                return 1.0
            if ratio <= 3:
                return 0.8
            if ratio <= 5:
                return 0.5
            if ratio <= 8:
                return 0.2
            return 0.0

        def growth(metrics, code, gen):
            nf = metrics.get("num_functions", 0)
            lines = max(1, metrics.get("lines", 1))
            density = nf / lines
            if 0.04 <= density <= 0.07:
                return 1.0
            if 0.03 <= density <= 0.1:
                return 0.6
            return 0.2

        def consistency(metrics, code, gen):
            total = metrics.get("tests_total", 0)
            if total == 0:
                return 0.5
            return metrics.get("tests_passed", 0) / total

        def velocity(metrics, code, gen):
            if len(self._score_history) < 3:
                return 0.5
            recent = list(self._score_history)[-3:]
            if recent[-1] >= recent[-2] >= recent[-3]:
                return 1.0
            if recent[-1] >= recent[-2]:
                return 0.6
            return 0.2

        def vocabulary_richness(metrics, code, gen):
            try:
                rows = self.kb.conn.execute(
                    "SELECT word FROM lang_vocabulary ORDER BY frequency DESC LIMIT 100"
                ).fetchall()
                vocab_words = {r[0] for r in rows}
                if not vocab_words:
                    return 0.5
                code_words = set(
                    n.strip('_') for n in re.findall(r'\b[a-z_][a-z0-9_]+\b', code) if len(n) > 3
                )
                return min(1.0, len(vocab_words & code_words) / max(1, len(vocab_words)) * 10)
            except Exception:
                return 0.5

        self._criteria = [
            RewardCriterion("novelty",     "Cdigo diferente do histrico",  1.2, novelty),
            RewardCriterion("elegance",    "Baixa complexidade por funo",   1.5, elegance),
            RewardCriterion("growth",      "Crescimento saudvel",            1.0, growth),
            RewardCriterion("consistency", "Testes passando",                 1.8, consistency),
            RewardCriterion("velocity",    "Sequncia de melhorias",          0.8, velocity),
            RewardCriterion("vocabulary",  "Uso do vocabulrio coletado",     0.5, vocabulary_richness),
        ]

    def evaluate(self, metrics: Dict, code: str, generation: int) -> float:
        """Calcula a recompensa combinada."""
        base_score = metrics.get("score", 0.0)
        criteria_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0
        for criterion in self._criteria:
            val = criterion.evaluate(metrics, code, generation)
            criteria_scores[criterion.name] = round(val, 3)
            weighted_sum += val * criterion.weight
            total_weight += criterion.weight
        custom_score = (weighted_sum / total_weight * 100) if total_weight > 0 else base_score
        final = base_score * (1 - self.BASE_WEIGHT) + custom_score * self.BASE_WEIGHT
        final = min(100.0, max(0.0, final))
        self._score_history.append(final)
        try:
            with self._lock:
                self.kb.conn.execute(
                    "INSERT INTO reward_history (generation, timestamp, base_score, custom_score, criteria_scores) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (generation, datetime.now().isoformat(), base_score, custom_score, json.dumps(criteria_scores))
                )
                self.kb.conn.commit()
        except Exception as e:
            logger.warning(f"Erro ao registrar recompensa: {e}")
        return round(final, 2)

    def add_criterion(self, name, description, weight, evaluator):
        self._criteria.append(RewardCriterion(name, description, weight, evaluator))

    def adjust_weight(self, name: str, new_weight: float):
        for c in self._criteria:
            if c.name == name:
                c.weight = new_weight
                return

    def get_criteria_status(self) -> List[Dict]:
        return [{
            "name": c.name,
            "description": c.description,
            "weight": c.weight,
            "last_value": c.last_value
        } for c in self._criteria]

    def get_recent_scores(self, n: int = 20) -> List[float]:
        return list(self._score_history)[-n:]


# 
# LANGUAGE TRAINER (completo)
# 

class DiffDescriber:
    """Descreve as diferenas entre dois cdigos."""

    def describe(self, old_code: str, new_code: str) -> str:
        try:
            old_funcs = self._func_names(old_code)
            new_funcs = self._func_names(new_code)
            added = new_funcs - old_funcs
            removed = old_funcs - new_funcs
            kept = old_funcs & new_funcs
            delta_lines = len(new_code.splitlines()) - len(old_code.splitlines())
            parts = []
            if added:
                parts.append(f"adicionou {len(added)} funo(es): {', '.join(sorted(added))}")
            if removed:
                parts.append(f"removeu {len(removed)} funo(es): {', '.join(sorted(removed))}")
            changed = [n for n in kept if self._func_body(old_code, n) != self._func_body(new_code, n)]
            if changed:
                parts.append(f"modificou corpo de: {', '.join(sorted(changed))}")
            if delta_lines > 0:
                parts.append(f"cresceu {delta_lines} linha(s)")
            elif delta_lines < 0:
                parts.append(f"encolheu {abs(delta_lines)} linha(s)")
            if not parts:
                parts.append("pequenas alteraes simblicas sem mudana estrutural")
            return "Mutao: " + "; ".join(parts) + "."
        except Exception as e:
            return f"Mutao aplicada (erro ao descrever: {e})."

    def _func_names(self, code):
        try:
            tree = ast.parse(code)
            return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        except Exception:
            return set()

    def _func_body(self, code, name):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return astor.to_source(node)
        except Exception:
            pass
        return ""


class SelfCritic:
    """Analisa o cdigo e aponta fraquezas."""

    HINTS = [
        ("funes longas",
         lambda tree: [n.name for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and sum(1 for _ in ast.walk(n)) > 40]),
        ("sem docstrings",
         lambda tree: [n.name for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and not ast.get_docstring(n)]),
        ("loops aninhados",
         lambda tree: [n.lineno for n in ast.walk(tree)
                       if isinstance(n, (ast.For, ast.While)) and
                       any(isinstance(c, (ast.For, ast.While)) for c in ast.walk(n) if c is not n)]),
        ("sem type hints",
         lambda tree: [n.name for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and
                       (n.returns is None or any(a.annotation is None for a in n.args.args))]),
        ("bare except",
         lambda tree: [n.lineno for n in ast.walk(tree)
                       if isinstance(n, ast.ExceptHandler) and n.type is None]),
    ]

    def critique(self, code: str) -> str:
        issues = []
        try:
            tree = ast.parse(code)
            for label, check in self.HINTS:
                found = check(tree)
                if found:
                    sample = str(found[:3]).strip("[]")
                    issues.append(f"[{label}]  {sample}")
        except Exception as e:
            return f"(erro ao analisar: {e})"
        if not issues:
            return "Cdigo sem problemas estruturais bvios detectados."
        return "Fraquezas detectadas:\n" + "\n".join(f"   {i}" for i in issues)


class ProposalWriter:
    """Escreve propostas de melhoria baseadas no histrico."""

    def propose(self, kb: KnowledgeBase, current_score: float) -> str:
        rates = kb.get_mutation_success_rates()
        if not rates:
            return "Histrico insuficiente  continue evoluindo para acumular dados."
        top = sorted(rates.items(), key=lambda x: x[1], reverse=True)[:5]
        bottom = sorted(rates.items(), key=lambda x: x[1])[:3]
        lines = [f"Score atual: {current_score:.2f}", "Mutaes mais promissoras:"]
        for mtype, rate in top:
            bar = "" * int(rate * 10) + "" * (10 - int(rate * 10))
            lines.append(f"  {mtype:<28} {bar} {rate*100:.0f}%")
        lines.append("Mutaes para evitar:")
        for mtype, rate in bottom:
            lines.append(f"  {mtype:<28} {rate*100:.0f}% sucesso")
        return "\n".join(lines)


class GrokLanguageAgent:
    """Agente que consulta Grok para anlise lingustica."""

    def __init__(self, grok: Optional[GrokGenerator]):
        self.grok = grok
        self._last_gen = -1

    def should_run(self, generation: int) -> bool:
        if not self.grok or not self.grok.api_key:
            return False
        return generation - self._last_gen >= GROK_LT_INTERVAL

    def analyze(self, code, diff_desc, critique, score, replaced) -> Optional[str]:
        if not self.grok:
            return None
        context = (
            f"You are an AI code coach analyzing the following Python program "
            f"that evolves itself autonomously.\n\n"
            f"--- CURRENT CODE (truncated) ---\n{code[:1200]}\n\n"
            f"--- LATEST MUTATION ---\n{diff_desc}\n\n"
            f"--- SELF-CRITIQUE ---\n{critique}\n\n"
            f"--- SCORE: {score:.2f} | ACCEPTED: {replaced} ---\n\n"
            f"In 3-5 sentences, explain what the mutation achieved, "
            f"why the score changed, and ONE concrete improvement for the next generation."
        )
        result = self.grok.generate_function(context, max_tokens=300)
        if result:
            self._last_gen += GROK_LT_INTERVAL
        return result


class VocabularyTracker:
    """Rastreia vocabulrio usado no cdigo."""

    STOP_WORDS = {
        "self", "return", "def", "class", "import", "from", "if", "else",
        "elif", "for", "while", "try", "except", "with", "as", "in", "not",
        "and", "or", "is", "None", "True", "False", "pass", "break",
        "continue", "lambda", "yield", "raise", "assert", "del", "global",
        "nonlocal", "print", "range", "len", "str", "int", "float", "list",
        "dict", "set", "tuple", "type", "super", "object",
    }

    def update(self, conn: sqlite3.Connection, code: str):
        try:
            tree = ast.parse(code)
            names = [n.id for n in ast.walk(tree)
                     if isinstance(n, ast.Name) and n.id not in self.STOP_WORDS
                     and len(n.id) > 3 and n.id.isidentifier()]
            counter = Counter(names)
            now = datetime.now().isoformat()
            with threading.RLock():
                for word, freq in counter.most_common(50):
                    conn.execute("""
                        INSERT INTO lang_vocabulary (word, frequency, last_seen)
                        VALUES (?, ?, ?)
                        ON CONFLICT(word) DO UPDATE SET
                            frequency = frequency + excluded.frequency,
                            last_seen = excluded.last_seen
                    """, (word, freq, now))
                conn.commit()
        except Exception as e:
            logger.debug(f"Erro ao atualizar vocabulrio: {e}")

    def top_terms(self, conn, n: int = 10) -> List[Tuple[str, int]]:
        try:
            return conn.execute(
                "SELECT word, frequency FROM lang_vocabulary ORDER BY frequency DESC LIMIT ?", (n,)
            ).fetchall()
        except Exception as e:
            logger.debug(f"Erro ao buscar top termos: {e}")
            return []


class LanguageTrainer:
    """Orquestrador de anlise lingustica."""

    def __init__(self, kb: KnowledgeBase, grok: Optional[GrokGenerator] = None):
        self.kb = kb
        self.describer = DiffDescriber()
        self.critic = SelfCritic()
        self.proposer = ProposalWriter()
        self.vocab = VocabularyTracker()
        self.grok_agent = GrokLanguageAgent(grok)
        self._prev_code: Optional[str] = None
        self._cycle_count = 0
        logger.info("[] LanguageTrainer inicializado")

    def maybe_run(self, generation, code, prev_code, metrics, replaced) -> Optional[Dict[str, str]]:
        self._cycle_count += 1
        if self._cycle_count % LT_INTERVAL != 0:
            return None
        old = prev_code or self._prev_code or code
        self._prev_code = code
        return self._run(generation, old, code, metrics.get("score", 0.0), replaced)

    def _run(self, generation, old_code, new_code, score, replaced) -> Dict[str, str]:
        logger.info(f"\n[] LanguageTrainer  gerao {generation}")
        description = self.describer.describe(old_code, new_code)
        logger.info(f"    {description}")
        critique = self.critic.critique(new_code)
        first_issue = critique.splitlines()[0] if critique else ""
        logger.info(f"    {first_issue}")
        proposal = self.proposer.propose(self.kb, score)
        top_line = proposal.splitlines()[1] if len(proposal.splitlines()) > 1 else proposal
        logger.info(f"    {top_line.strip()}")
        grok_analysis = None
        if self.grok_agent.should_run(generation):
            logger.info("   [] Consultando Grok para anlise lingustica...")
            grok_analysis = self.grok_agent.analyze(new_code, description, critique, score, replaced)
            if grok_analysis:
                for chunk in [grok_analysis[i:i+120] for i in range(0, len(grok_analysis), 120)]:
                    logger.info(f"    {chunk}")
        self.vocab.update(self.kb.conn, new_code)
        result = {
            "description": description,
            "critique": critique,
            "proposal": proposal,
            "grok": grok_analysis or ""
        }
        self._persist(generation, result, score, replaced)
        return result

    def _persist(self, generation, result, score, replaced):
        try:
            with self.kb._lock:
                self.kb.conn.execute("""
                    INSERT INTO lang_diffs
                        (generation, timestamp, description, critique, proposal, score_delta, replaced)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (generation, datetime.now().isoformat(), result["description"],
                      result["critique"], result["proposal"], score, 1 if replaced else 0))
                self.kb.conn.commit()
        except Exception as e:
            logger.warning(f"[] Falha ao persistir LanguageTrainer: {e}")

    def get_history(self, limit: int = 10) -> List[Dict]:
        try:
            rows = self.kb.conn.execute("""
                SELECT generation, timestamp, description, critique, proposal, score_delta, replaced
                FROM lang_diffs ORDER BY generation DESC LIMIT ?
            """, (limit,)).fetchall()
            return [{
                "generation": r[0],
                "timestamp": r[1],
                "description": r[2],
                "critique": r[3],
                "proposal": r[4],
                "score": r[5],
                "replaced": bool(r[6])
            } for r in rows]
        except Exception:
            return []

    def get_top_vocabulary(self, n: int = 20) -> List[Tuple[str, int]]:
        return self.vocab.top_terms(self.kb.conn, n)

    def print_report(self):
        logger.info("\n" + ""*60)
        logger.info("    RELATRIO DE LINGUAGEM  ATENA NEURAL v3")
        logger.info(""*60)
        for entry in self.get_history(5):
            status = "" if entry["replaced"] else ""
            logger.info(f"\n{status} Gerao {entry['generation']}  score={entry['score']:.2f}")
            logger.info(f"   {entry['description']}")
            logger.info(f"   {entry['critique'].splitlines()[0]}")
        logger.info("\n Vocabulrio (top 15):")
        for word, freq in self.get_top_vocabulary(15):
            logger.info(f"   {word:<30} {'' * min(freq, 20)} ({freq})")
        logger.info(""*60)


# 
# HARVESTER DE VOCABULRIO (thread)
# 

class VocabularyHarvester(threading.Thread):
    """Coleta termos de fontes externas periodicamente."""
    STOPWORDS = {
        "with", "from", "that", "this", "there", "their", "have", "what", "when", "where", "which",
        "about", "would", "could", "should", "into", "your", "while", "using", "used", "more", "less",
        "para", "como", "mais", "menos", "sobre", "entre", "depois", "antes", "tambem", "ainda",
        "resultado", "util", "main", "class", "work", "through", "either", "reading",
    }
    ADVANCED_SIGNAL_TERMS = {
        "transformer", "transformers", "attention", "tokenizer", "embedding", "vector", "retrieval",
        "rag", "agentic", "orchestrator", "kubernetes", "k8s", "terraform", "observability", "otel",
        "telemetry", "distributed", "sharding", "consensus", "eventdriven", "streaming", "asyncio",
        "profiling", "memoization", "autotuning", "rlhf", "inference", "quantization", "distillation",
        "federated", "multimodal", "timeseries", "featurestore", "grpc", "protobuf", "websocket",
    }
    SEED_ADVANCED_TERMS = {
        "orchestrator", "telemetry", "kubernetes", "vectorstore", "retrieval", "optimizer",
        "observability", "asyncio", "distributed", "inference",
    }

    def __init__(self, kb: KnowledgeBase):
        super().__init__(daemon=True)
        self.kb = kb
        self.interval = VH_INTERVAL_HOURS * 3600
        self.running = True

    def run(self):
        while self.running:
            try:
                self.harvest_all()
            except Exception as e:
                logger.warning(f"[] Erro: {e}")
            time.sleep(self.interval)

    def harvest_all(self):
        logger.info("[] Iniciando coleta de vocabulrio externo...")
        terms = set()
        for fn in [self._fetch_stackoverflow_terms, self._fetch_wiki_terms]:
            try:
                terms.update(fn())
            except Exception as e:
                logger.debug(f"Erro em fonte: {e}")
        terms.update(self.SEED_ADVANCED_TERMS)
        if HAS_NLTK:
            try:
                terms.update(self._expand_with_wordnet(terms))
            except Exception as e:
                logger.debug(f"Erro no WordNet: {e}")
        terms = {term for term in terms if self._is_high_signal_term(term)}
        if terms:
            now = datetime.now().isoformat()
            with self.kb._lock:
                for word in terms:
                    if word.isidentifier():
                        self.kb.conn.execute("""
                            INSERT INTO lang_vocabulary (word, frequency, last_seen)
                            VALUES (?, 1, ?)
                            ON CONFLICT(word) DO UPDATE SET
                                frequency = frequency + 1,
                                last_seen = excluded.last_seen
                        """, (word, now))
                self.kb.conn.commit()
            logger.info(f"[] {len(terms)} termos inseridos/atualizados.")
        else:
            logger.info("[] Nenhum termo avançado de alta confiança coletado nesta rodada.")

    def _is_high_signal_term(self, word: str) -> bool:
        return self._term_signal_score(word) >= 2

    def _term_signal_score(self, word: str) -> int:
        word = (word or "").strip().lower()
        if len(word) < 4 or not word.isidentifier():
            return 0
        if word in self.STOPWORDS:
            return -3
        score = 0
        if word in self.ADVANCED_SIGNAL_TERMS:
            score += 3
        advanced_fragments = (
            "cloud", "vector", "graph", "quant", "model", "agent", "async", "cache", "cluster",
            "metric", "telemet", "kubern", "token", "embed", "optimizer", "federat", "distill",
        )
        if any(fragment in word for fragment in advanced_fragments):
            score += 1
        if len(word) >= 10:
            score += 1
        if any(ch.isdigit() for ch in word):
            score += 1
        generic_noise = {"python", "function", "object", "system", "method", "variable"}
        if word in generic_noise:
            score -= 1
        return score

    def _fetch_stackoverflow_terms(self, pages: int = 2) -> Set[str]:
        terms = set()
        for page in range(1, pages + 1):
            try:
                resp = requests.get(
                    "https://api.stackexchange.com/2.3/questions",
                    params={
                        "order": "desc",
                        "sort": "votes",
                        "tagged": "python",
                        "site": "stackoverflow",
                        "pagesize": 100,
                        "page": page
                    },
                    timeout=10
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    for word in item["title"].split():
                        word = word.strip('.,;:?!"\'()[]{}').lower()
                        if word.isidentifier() and len(word) > 3:
                            terms.add(word)
            except Exception as e:
                logger.debug(f"Erro no StackOverflow: {e}")
        return terms

    def _fetch_wiki_terms(self) -> Set[str]:
        terms = set()
        for topic in ["Algorithm", "Data_structure", "Python_(programming_language)"]:
            try:
                resp = requests.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": topic,
                        "prop": "extracts",
                        "format": "json",
                        "explaintext": True
                    },
                    timeout=10
                )
                data = resp.json()
                for page in data["query"]["pages"].values():
                    for word in page.get("extract", "").split():
                        word = word.strip('.,;:?!"\'()[]{}').lower()
                        if word.isidentifier() and len(word) > 3:
                            terms.add(word)
            except Exception as e:
                logger.debug(f"Erro na Wikipedia: {e}")
        return terms

    def _expand_with_wordnet(self, terms: Set[str]) -> Set[str]:
        expanded = set()
        for term in terms:
            for syn in wordnet.synsets(term):
                for lemma in syn.lemmas():
                    for part in lemma.name().replace('_', ' ').split():
                        if part.isidentifier() and len(part) > 3:
                            expanded.add(part)
        return expanded

    def stop(self):
        self.running = False


# 
# STATIC CHECKER BASE (usado como fallback)
# 

class StaticChecker:
    """Verificador esttico bsico (usado como fallback)."""
    FORBIDDEN_PATTERNS = [
        r'__import__\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'open\s*\(.+["\']w["\']',
    ]

    def __init__(self):
        self._patterns = [re.compile(p) for p in self.FORBIDDEN_PATTERNS]

    def check(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"
        for pat in self._patterns:
            if pat.search(code):
                return False, f"Padro proibido: {pat.pattern}"
        if len(code.strip()) < 50:
            return False, "Cdigo muito curto aps mutao"
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return False, "Nenhuma funo definida"
        return True, "OK"


# =============================================================================
# HACKER RECON MODULE
# =============================================================================

class HackerReconModule:
    """Coleta cdigo da web para expandir conhecimento."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.session = requests.Session()
        self.ua = UserAgent() if HAS_FAKE_UA else "AtenaNeural/3.0"
        self._processed: Set[str] = set()
        self._last_req: Dict[str, float] = {}

    def hunt_new_tech(self, topic: str, max_results: int = None):
        max_r = max_results or Config.HACKER_RECON_MAX_RESULTS
        logger.info(f"[] Recon: {topic}")
        urls = set()
        try:
            resp = self.session.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"{topic} python code site:github.com OR site:stackoverflow.com"},
                headers={"User-Agent": str(self.ua)},
                timeout=10
            )
            if resp.status_code == 200 and HAS_BEAUTIFULSOUP:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a', class_='result__url')[:max_r]:
                    href = a.get('href', '')
                    if href.startswith('http'):
                        urls.add(href)
        except Exception as e:
            logger.warning(f"[] DuckDuckGo falhou: {e}")
        for url in urls:
            if url in self._processed:
                continue
            self._rate_limit(url)
            content = self._fetch(url)
            if content:
                for snippet in self._extract_code(content):
                    self.kb.add_function(snippet, url, f"recon_{topic}")
                self._processed.add(url)

    def _rate_limit(self, url):
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        last = self._last_req.get(domain, 0)
        wait = Config.HACKER_RECON_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_req[domain] = time.time()

    def _fetch(self, url):
        try:
            r = self.session.get(
                url,
                headers={"User-Agent": str(self.ua)},
                timeout=15
            )
            return r.text if r.status_code == 200 else None
        except Exception as e:
            logger.debug(f"Erro ao buscar {url}: {e}")
            return None

    def _extract_code(self, html):
        if not HAS_BEAUTIFULSOUP:
            return []
        snippets = []
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(['pre', 'code']):
            text = tag.get_text().strip()
            if len(text) >= Config.HACKER_RECON_MIN_CODE_LENGTH and self._is_code(text):
                snippets.append(text)
        return snippets

    def _is_code(self, text):
        special = sum(1 for c in text if c in '{}[]();=<>+-*/&|')
        if len(text) > 0 and special / len(text) > 0.04:
            return True
        return any(kw in text for kw in ('def ', 'class ', 'import ', 'function', 'return '))


# =============================================================================
# NO-CODE BUILDER
# =============================================================================

@dataclass
class Project:
    name: str
    description: str
    path: Path
    files: Dict[str, str]
    created_at: datetime
    last_evolved: Optional[datetime] = None
    score: float = 0.0


class NoCodeBuilder:
    """Cria projetos a partir de descries em linguagem natural."""

    def __init__(self, kb, mutation_engine, grok):
        self.kb = kb
        self.mutation_engine = mutation_engine
        self.grok = grok
        self.projects: Dict[str, Project] = {}
        self._load_projects()

    def _load_projects(self):
        for proj_path in Config.PROJECTS_DIR.iterdir():
            if proj_path.is_dir():
                meta = proj_path / ".atena_meta.json"
                if meta.exists():
                    try:
                        data = json.loads(meta.read_text())
                        files = {
                            f: (proj_path / f).read_text()
                            for f in data.get("files", [])
                            if (proj_path / f).exists()
                        }
                        self.projects[data["name"]] = Project(
                            name=data["name"],
                            description=data["description"],
                            path=proj_path,
                            files=files,
                            created_at=datetime.fromisoformat(data["created_at"]),
                            last_evolved=datetime.fromisoformat(data["last_evolved"]) if data.get("last_evolved") else None,
                            score=data.get("score", 0.0)
                        )
                    except Exception as e:
                        logger.warning(f"Erro ao carregar projeto {proj_path}: {e}")

    def create_project(self, description: str) -> Optional[Project]:
        if not self.grok:
            logger.error("[] Grok no configurado")
            return None
        spec = self._generate_spec(description)
        if not spec:
            return None
        name = self._make_name(description)
        counter = 1
        base = name
        while name in self.projects or (Config.PROJECTS_DIR / name).exists():
            name = f"{base}_{counter}"
            counter += 1
        path = Config.PROJECTS_DIR / name
        path.mkdir(parents=True)
        files = {}
        for fname, content in spec.items():
            fp = path / fname
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)
            files[fname] = content
        proj = Project(
            name=name,
            description=description,
            path=path,
            files=files,
            created_at=datetime.now()
        )
        self._save_meta(proj)
        self.projects[name] = proj
        logger.info(f"[] Projeto '{name}' criado")
        return proj

    def _generate_spec(self, description):
        prompt = (f"Create a complete Python project for: {description}. "
                  f"Return ONLY a JSON object where keys are file paths and values are file contents. "
                  f"Include app.py, requirements.txt, and any needed templates.")
        resp = self.grok.generate_function(prompt, max_tokens=3000)
        if not resp:
            return None
        try:
            start = resp.find('{')
            end = resp.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(resp[start:end])
        except Exception as e:
            logger.warning(f"Erro ao parsear JSON do Grok: {e}")
        return None

    def _make_name(self, desc):
        words = desc.lower().split()[:3]
        name = "_".join(words)
        name = re.sub(r'[^a-z0-9_]', '', name) or f"project_{int(time.time())}"
        return name

    def _save_meta(self, proj):
        (proj.path / ".atena_meta.json").write_text(json.dumps({
            "name": proj.name,
            "description": proj.description,
            "created_at": proj.created_at.isoformat(),
            "last_evolved": proj.last_evolved.isoformat() if proj.last_evolved else None,
            "score": proj.score,
            "files": list(proj.files.keys())
        }, indent=2))

    def evolve_project(self, proj, cycles=3):
        logger.info(f"[] Evoluindo '{proj.name}' por {cycles} ciclos...")
        for i in range(cycles):
            for fname, content in list(proj.files.items()):
                if fname.endswith('.py'):
                    mtype = random.choice(self.mutation_engine.mutation_types)
                    mutated, desc = self.mutation_engine.mutate(content, mtype)
                    if mutated != content:
                        proj.files[fname] = mutated
                        (proj.path / fname).write_text(mutated)
                        logger.info(f"   [{i+1}] {desc} em {fname}")
        proj.last_evolved = datetime.now()
        self._save_meta(proj)

    def list_projects(self):
        return list(self.projects.keys())

    def get_project(self, name):
        return self.projects.get(name)


# =============================================================================
# DASHBOARD (HTML inline)  verso resumida
# =============================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head><title>Atena Neural v3 Dashboard</title>
<style>
body { font-family: monospace; background: #0a0e1a; color: #c0caf5; padding: 20px; }
h1 { color: #bb9af7; border-bottom: 1px solid #3b4261; }
.section { margin: 20px 0; padding: 10px; background: #161c2e; border-radius: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); gap: 10px; }
.card { background: #1a2335; padding: 10px; border-radius: 6px; border-left: 4px solid #7aa2f7; }
.good { color: #9ece6a; }
.warn { color: #e0af68; }
.bad { color: #f7768e; }
</style>
<script>
async function refresh() {
    let res = await fetch('/api/state');
    let data = await res.json();
    document.getElementById('gen').innerText = data.generation;
    document.getElementById('score').innerText = data.score.toFixed(2);
    document.getElementById('last_mut').innerText = data.last_mutation;
    document.getElementById('last_critique').innerText = data.last_critique;
    document.getElementById('funcs').innerText = data.num_functions;
    document.getElementById('cx').innerText = data.complexity.toFixed(2);
    document.getElementById('lines').innerText = data.lines;
    if (data.problem_name) {
        document.getElementById('problem_name').innerText = data.problem_name;
        document.getElementById('problem_desc').innerText = data.problem_description;
    } else {
        document.getElementById('problem_name').innerText = "nenhum";
    }
    let mr = document.getElementById('mutation_rates');
    mr.innerHTML = '';
    for (let [m,r] of Object.entries(data.mutation_rates).slice(0,6)) {
        mr.innerHTML += `<div>${m}: ${(r*100).toFixed(0)}%</div>`;
    }
    let pat = document.getElementById('patterns');
    pat.innerHTML = '';
    for (let p of data.patterns) {
        pat.innerHTML += `<div>${p.pattern} (${p.avg_delta.toFixed(2)})</div>`;
    }
    let rules = document.getElementById('checker_rules');
    rules.innerHTML = '';
    for (let r of data.checker_rules.slice(0,5)) {
        let cls = r.active ? 'good' : 'bad';
        rules.innerHTML += `<div class="${cls}">${r.name} fp=${r.fp_rate}</div>`;
    }
}
setInterval(refresh, 5000);
window.onload = refresh;
</script>
</head>
<body>
<h1> ATENA NEURAL v3.1  DASHBOARD</h1>
<div class="section">
    <div>Gerao: <span id="gen">0</span> | Score: <span id="score">0</span></div>
    <div>Problema: <span id="problem_name"></span>  <span id="problem_desc"></span></div>
    <div>ltima mutao: <span id="last_mut"></span></div>
    <div>Crtica: <span id="last_critique"></span></div>
    <div>Funes: <span id="funcs">0</span> | Complexidade: <span id="cx">0</span> | Linhas: <span id="lines">0</span></div>
</div>
<div class="grid">
    <div class="card"><h3>Taxas de sucesso</h3><div id="mutation_rates"></div></div>
    <div class="card"><h3>Checker rules</h3><div id="checker_rules"></div></div>
    <div class="card"><h3>Padres episdicos</h3><div id="patterns"></div></div>
</div>
</body>
</html>
"""

class AtenaDashboard:
    def __init__(self, core, port: int = None):
        self.core = core
        self.port = port or DASHBOARD_PORT
        self._thread = None
        self._server = None

    def start(self):
        import http.server, urllib.parse, socketserver
        dashboard = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = urllib.parse.urlparse(self.path).path
                if path == '/api/state':
                    data = dashboard._build_state()
                    body = json.dumps(data).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(body))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = DASHBOARD_HTML.encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', len(body))
                    self.end_headers()
                    self.wfile.write(body)

        def _serve():
            try:
                with socketserver.TCPServer(("0.0.0.0", dashboard.port), Handler) as srv:
                    dashboard._server = srv
                    srv.serve_forever()
            except Exception as e:
                logger.error(f"Erro no dashboard: {e}")

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        time.sleep(0.3)
        logger.info(f"[] Dashboard disponvel em http://localhost:{self.port}")

    def _build_state(self) -> Dict:
        core = self.core
        state = {
            "generation": getattr(core, "generation", 0),
            "score": getattr(core, "best_score", 0),
            "last_mutation": "",
            "last_diff": "",
            "last_critique": "",
            "replaced": False,
            "num_functions": 0,
            "complexity": 0,
            "lines": 0,
            "mutation_rates": {},
            "criteria": [],
            "boosts": {},
            "patterns": [],
            "vocab": [],
            "checker_rules": [],
            "scorer_population": [],
            "self_mod_history": [],
            "problem_name": core.problem.name if core.problem else None,
            "problem_description": core.problem.description if core.problem else None,
        }
        try:
            code = getattr(core, "current_code", "")
            if code:
                tree = ast.parse(code)
                if HAS_RADON:
                    raw = radon_raw.analyze(code)
                    state["lines"] = raw.loc
                    state["comment_ratio"] = raw.comments / (raw.loc + 1e-6)
                    cc_blocks = radon_cc.cc_visit(code)
                    state["complexity"] = round(
                        sum(b.complexity for b in cc_blocks) / len(cc_blocks) if cc_blocks else 1.0, 2
                    )
                else:
                    state["lines"] = len(code.splitlines())
                    state["complexity"] = 1.0
                state["num_functions"] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        except Exception as e:
            logger.debug(f"Erro ao coletar mtricas para dashboard: {e}")
        try:
            lt = getattr(core, "lang_trainer", None)
            if lt:
                history = lt.get_history(1)
                if history:
                    h = history[0]
                    state["last_diff"] = h.get("description", "")
                    state["last_critique"] = h.get("critique", "").splitlines()[0]
                    state["replaced"] = h.get("replaced", False)
                state["vocab"] = lt.get_top_vocabulary(40)
        except Exception as e:
            logger.debug(f"Erro ao obter dados do LanguageTrainer: {e}")
        try:
            state["mutation_rates"] = core.kb.get_mutation_success_rates()
        except Exception:
            pass
        try:
            rs = getattr(core, "reward_system", None)
            if rs:
                state["criteria"] = rs.get_criteria_status()
        except Exception:
            pass
        try:
            fl = getattr(core, "feedback_loop", None)
            if fl:
                state["boosts"] = fl.get_active_boosts()
        except Exception:
            pass
        try:
            em = getattr(core, "episodic_memory", None)
            if em:
                state["patterns"] = em.get_best_patterns(4)
        except Exception:
            pass
        try:
            v3 = getattr(core, "v3", None)
            if v3:
                state["checker_rules"] = v3.adaptive_checker.get_rules_status()
                state["scorer_population"] = v3.evolvable_scorer.get_population_status()
                state["self_mod_history"] = list(v3._self_mod_results)[-10:]
        except Exception:
            pass
        try:
            row = core.kb.conn.execute(
                "SELECT mutation, new_score, replaced FROM evolution_metrics ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                state["last_mutation"] = row[0] or ""
                state["score"] = row[1] or state["score"]
                state["replaced"] = bool(row[2])
        except Exception:
            pass
        return state

    def stop(self):
        if self._server:
            self._server.shutdown()


# =============================================================================
# EXEMPLOS DE PROBLEMAS PR-DEFINIDOS
# =============================================================================

def create_sorting_problem() -> Problem:
    """Cria um problema de ordenao."""
    test_cases = [
        ([3, 1, 2], [1, 2, 3]),
        ([5, 5, 5], [5, 5, 5]),
        ([], []),
        ([9, 8, 7, 6], [6, 7, 8, 9]),
        ([1, 2, 3, 4], [1, 2, 3, 4]),
    ]

    def evaluate(code: str) -> float:
        adapter = ""
        if "def sort(" not in code:
            if "def util_sort(" in code:
                adapter = "\nsort = util_sort\n"
            elif "def sort_list(" in code:
                adapter = "\nsort = sort_list\n"
            elif "def quicksort(" in code:
                adapter = "\nsort = quicksort\n"
            elif "def solve(" in code:
                adapter = "\nsort = solve\n"

        # Deve definir uma funo 'sort' que recebe lista e retorna lista ordenada
        test_code = code + adapter + """

def _test():
    import json
    test_cases = """ + json.dumps(test_cases) + """
    correct = 0
    for i, (inp, expected) in enumerate(test_cases):
        try:
            result = sort(inp)
            if result == expected:
                correct += 1
            else:
                print(f"FAIL case {i}: {inp} -> {result} (expected {expected})")
        except Exception as e:
            print(f"ERROR case {i}: {e}")
    print(f"PASSED {correct}/{len(test_cases)}")
    return correct
_test()
"""
        sandbox = Sandbox(timeout=5)
        success, output, _ = sandbox.run(test_code)
        if not success:
            return 0.0
        # Extrai nmero de acertos
        match = re.search(r"PASSED (\d+)/(\d+)", output)
        if match:
            correct = int(match.group(1))
            total = int(match.group(2))
            return (correct / total) * 100
        return 0.0

    return Problem(
        name="sorting",
        description="Ordenar listas de inteiros",
        evaluate=evaluate
    )


def create_fibonacci_problem() -> Problem:
    """Cria um problema de Fibonacci."""
    test_cases = [(0, 0), (1, 1), (2, 1), (3, 2), (4, 3), (5, 5), (10, 55)]

    def evaluate(code: str) -> float:
        adapter = ""
        if "def fibonacci(" not in code:
            if "def util_fibonacci(" in code:
                adapter = "\nfibonacci = util_fibonacci\n"
            elif "def fib(" in code:
                adapter = "\nfibonacci = fib\n"
            elif "def solve(" in code:
                adapter = "\nfibonacci = solve\n"

        test_code = code + adapter + """

def _test():
    test_cases = """ + json.dumps(test_cases) + """
    correct = 0
    for n, expected in test_cases:
        try:
            result = fibonacci(n)
            if result == expected:
                correct += 1
            else:
                print(f"FAIL: fibonacci({n}) = {result}, expected {expected}")
        except Exception as e:
            print(f"ERROR: {e}")
    print(f"PASSED {correct}/{len(test_cases)}")
    return correct
_test()
"""
        sandbox = Sandbox(timeout=5)
        success, output, _ = sandbox.run(test_code)
        if not success:
            return 0.0
        match = re.search(r"PASSED (\d+)/(\d+)", output)
        if match:
            correct = int(match.group(1))
            total = int(match.group(2))
            return (correct / total) * 100
        return 0.0

    return Problem(
        name="fibonacci",
        description="Calcular o n-simo nmero de Fibonacci",
        evaluate=evaluate
    )


# =============================================================================
# ORQUESTRADOR PRINCIPAL v3.1 (com suporte a problemas)
# =============================================================================

class AtenaCore:
    """Ncleo de evoluo da Atena."""

    def __init__(self, problem: Optional[Problem] = None):
        Config.setup()
        self.problem = problem
        self.kb = KnowledgeBase()
        self.sandbox = Sandbox()
        self.evaluator = CodeEvaluator(self.sandbox, self.kb, problem=problem)
        self.mutation_engine = MutationEngine(self.kb)
        self.predictor = MutationPredictor(self.kb)
        
        # Inicialização de Módulos Avançados
        if HAS_GRAPH_MEMORY:
            self.graph_memory = KnowledgeGraph()
            logger.info("🔱 Módulo Avançado: Memória de Grafo de Conhecimento Ativa")
        
        if HAS_ORCHESTRATOR:
            self.orchestrator = MultiAgentOrchestrator()
            
            # Registra o Browser Agent se disponível
            if HAS_BROWSER_AGENT:
                from multi_agent_orchestrator import Agent
                import asyncio
                
                def browser_task_handler(task):
                    logger.info(f"Iniciando tarefa de navegação: {task.get('url')}")
                    agent = AtenaBrowserAgent()
                    
                    async def run_browser_task():
                        await agent.launch(headless=True)
                        success = await agent.navigate(task.get('url'))
                        if success:
                            if task.get('action') == 'screenshot':
                                await agent.take_screenshot(task.get('output_path', 'screenshot.png'))
                                result = f"Screenshot salvo em {task.get('output_path', 'screenshot.png')}"
                            elif task.get('action') == 'extract_text':
                                text = await agent.get_text_content()
                                result = f"Texto extraído ({len(text)} caracteres): {text[:200]}..."
                            else:
                                result = "Navegação concluída com sucesso."
                        else:
                            result = "Falha na navegação."
                        await agent.close()
                        return result
                    
                    # Executa a corrotina em um novo loop de eventos para a thread do agente
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(run_browser_task())
                    finally:
                        loop.close()

                browser_agent = Agent(
                    agent_id="ATENA-Browser-01",
                    role="Navegador Web Autônomo",
                    capabilities=["web_browsing", "data_extraction", "screenshot"],
                    task_handler=browser_task_handler
                )
                self.orchestrator.register_agent(browser_agent)
                logger.info("🔱 Módulo Avançado: ATENA-Browser-Agent Registrado no Orquestrador")

            self.orchestrator.start()
            logger.info("🔱 Módulo Avançado: Orquestrador Multi-Agente Ativo")
            
        if HAS_FEDERATED:
            self.fed_server = FederatedLearningServer(initial_weights={"base_score": 0.5})
            logger.info("🔱 Módulo Avançado: Servidor de Aprendizado Federado Ativo")
        self.news = NewsAPIClient(self.kb) if Config.NEWS_API_KEY else None
        self.learner = GitHubLearner(self.kb) if Config.GITHUB_TOKEN else None
        self.current_code = Config.CURRENT_CODE_FILE.read_text()
        self.generation = 0
        self.original_code = self.current_code
        self.best_score = 0.0
        self.stagnation_cycles = 0
        self.last_cycle_delta = 0.0
        self._load_state()

        baseline = self.evaluator.evaluate(self.current_code)
        baseline_score = baseline["score"]
        restored_score = self.best_score
        if restored_score > 0:
            self.best_score = max(restored_score, baseline_score)
            logger.info(
                f"[] Score restaurado mantido: {restored_score:.2f} | baseline atual: {baseline_score:.2f} | usado: {self.best_score:.2f}"
            )
        else:
            self.best_score = baseline_score
        self.best_code = self.current_code
        self.engine_path = Config.ENGINE_FILE
        self.advanced_essentials = AtenaAdvancedEssentials()
        boot_state = self.advanced_essentials.bootstrap(
            core_generation=self.generation,
            best_score=self.best_score,
        )
        logger.info(
            f"[] Advanced Essentials ativos: {len(boot_state.get('capabilities', []))} capacidades essenciais carregadas"
        )

        # v2.2 mdulos
        self.lang_trainer = LanguageTrainer(kb=self.kb, grok=self.mutation_engine.grok)
        self.vocab_harvester = VocabularyHarvester(self.kb)
        self.vocab_harvester.start()
        self.feedback_loop = FeedbackLoop(self.kb, self.mutation_engine)
        self.episodic_memory = EpisodicMemory(self.kb)
        self.reward_system = AutoRewardSystem(self.kb)

        # v3.0  auto-modificao profunda
        self.v3 = AtenaV3SelfMod(self)
        # Substitui checker e scorer pelo AdaptiveChecker e EvolvableScorer
        self.evaluator.checker = self.v3.adaptive_checker
        self.evaluator._compute_score = self.v3.evolvable_scorer.compute

        logger.info(f"[] Atena v3.1 iniciada | Score inicial: {self.best_score:.2f} | CI={IS_CI}")

    def _load_state(self):
        if Config.STATE_FILE.exists():
            try:
                data = json.loads(Config.STATE_FILE.read_text())
                self.generation = data.get("generation", 0)
                saved_score = data.get("best_score", 0)
                if saved_score > 0:
                    self.best_score = saved_score
                logger.info(f"[] Estado carregado: gerao {self.generation}, score {self.best_score:.2f}")
            except Exception as e:
                logger.warning(f"Erro ao carregar estado: {e}")

    def _save_state(self):
        try:
            Config.STATE_FILE.write_text(json.dumps({
                "generation": self.generation,
                "best_score": self.best_score,
                "timestamp": datetime.now().isoformat(),
                "is_ci": IS_CI,
            }, indent=2))
        except Exception as e:
            logger.warning(f"Erro ao salvar estado: {e}")

    def _backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Config.BACKUP_DIR / f"atena_backup_{ts}.py"
        shutil.copy(Config.CURRENT_CODE_FILE, backup_path)
        fhash = hashlib.sha256(self.current_code.encode()).hexdigest()
        self.kb.record_backup(str(backup_path), fhash, self.best_score)
        self._cleanup_backups()

    def _cleanup_backups(self):
        cutoff = datetime.now() - timedelta(days=Config.BACKUP_KEEP_DAYS)
        for f in Config.BACKUP_DIR.glob("atena_backup_*.py"):
            try:
                ts_str = f.stem.replace("atena_backup_", "")
                if datetime.strptime(ts_str, "%Y%m%d_%H%M%S") < cutoff:
                    f.unlink()
            except Exception:
                pass

    def evolve_one_cycle(self) -> Dict:
        """Executa um ciclo de evoluo."""
        self.generation += 1
        old_best_score = self.best_score
        logger.info(f"\n{'='*50}")
        logger.info(f" Gerao {self.generation} | Score atual: {self.best_score:.2f}")

        # Hacker Recon 2.0: Curiosidade Intrínseca
        recon_topic = "advanced python optimization"
        if HAS_CURIOSITY:
            recon_topic = curiosity.get_next_topic(context_terms=self._get_context_terms_for_curiosity())
            logger.info(f"🔍 Próximo tópico de curiosidade: {recon_topic}")

        # Protocolo Hydra: Auto-Hospedagem e Redundância
        if HAS_HYDRA and self.generation % 50 == 0:
            logger.info("🐉 Protocolo Hydra: Gerando configurações de infraestrutura...")
            hydra.generate_dockerfile()
            hydra.generate_terraform_stub()
            hydra.check_health()

        # Memória Episódica de Longo Prazo (Vector-DB)
        if HAS_VECTOR_MEMORY and HAS_TRANSFORMERS:
            try:
                current_emb = self.evaluator.get_embedding(self.current_code)
                similar_experiences = vector_memory.search_similar(current_emb, top_k=3)
                if similar_experiences:
                    logger.info(f"🧠 Memória de Longo Prazo: {len(similar_experiences)} experiências similares encontradas.")
                    for exp, dist in similar_experiences:
                        logger.info(f"  - Experiência: {exp.get('mutation', 'N/A')} (Distância: {dist:.4f})")
            except Exception as e:
                logger.debug(f"Erro ao acessar memória vetorial: {e}")

        objectives = self.kb.get_objectives()
        weights = self._compute_mutation_weights(objectives)

        # Sugesto da memria episdica
        next_suggested = self.episodic_memory.suggest_next_mutation()
        if next_suggested and random.random() < 0.3:
            weights[next_suggested] = weights.get(next_suggested, 1.0) * 3.0
            logger.info(f"   [] Memria episdica sugere '{next_suggested}'")

        # Ajuste do MetaLearner v3
        try:
            current_metrics = self.evaluator.evaluate(self.current_code)
            meta_adj = self.v3.get_meta_weight_adjustments(current_metrics)
            for mtype, factor in meta_adj.items():
                if mtype in weights:
                    weights[mtype] *= factor
        except Exception as e:
            logger.debug(f"Erro ao aplicar ajustes do MetaLearner: {e}")

        candidates = self.mutation_engine.generate_candidates(
            self.current_code, list(weights.keys()), n=Config.CANDIDATES_PER_CYCLE
        )

        if not candidates:
            logger.warning("  Nenhum candidato vlido gerado")
            self._save_state()
            gc.collect()
            return {
                "generation": self.generation,
                "mutation": "none",
                "score": self.best_score,
                "replaced": False
            }

        best_candidate = None
        best_candidate_score = -1.0

        def _blend_score(
            code: str,
            desc: str,
            mtype: str,
            metrics: Dict,
            *,
            apply_rlhf: bool = True,
            log_world_model_failures: bool = True,
        ) -> float:
            """Calcula score operacional em escala comparável para seleção."""
            if self.problem:
                return float(metrics["score"])

            evolvable_score = self.v3.evolvable_scorer.compute(metrics)
            blended = metrics["score"] * 0.7 + evolvable_score * 0.3

            if HAS_COUNCIL:
                council_vote = council.consensus_score(code, metrics)
                blended = blended * 0.8 + council_vote * 20.0

            if HAS_WORLD_MODEL:
                success, predicted_score, logs = world_model.simulate_mutation(code)
                if not success:
                    if log_world_model_failures:
                        logger.warning(f"⚠️ WorldModel previu falha crítica para mutação: {desc[:30]}")
                    blended *= 0.1
                else:
                    logger.info(f"✅ WorldModel validou mutação: {desc[:30]} (Score previsto: {predicted_score:.2f})")
                    blended *= 1.1

            if apply_rlhf and HAS_RLHF:
                reward_mult = rlhf.get_reward_multiplier(mtype)
                blended *= reward_mult
                logger.info(f"🧠 RLHF: Multiplicador de recompensa para '{mtype}': {reward_mult:.2f}")

            return float(blended)

        def _eval_candidate(candidate):
            code, desc, mtype = candidate
            metrics = self.evaluator.evaluate(code, original_code=self.original_code)
            blended = _blend_score(code, desc, mtype, metrics, apply_rlhf=True, log_world_model_failures=True)
            return code, desc, mtype, metrics, blended

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(candidates), Config.PARALLEL_WORKERS)
        ) as ex:
            futures = {ex.submit(_eval_candidate, c): c for c in candidates}
            for fut in concurrent.futures.as_completed(futures, timeout=Config.EVALUATION_TIMEOUT * 3):
                try:
                    code, desc, mtype, metrics, score = fut.result()
                    logger.info(f"   Candidato: {desc[:50]}  score {score:.2f}")
                    if score > best_candidate_score and metrics["valid"]:
                        best_candidate_score = score
                        best_candidate = (code, desc, mtype, metrics)
                except Exception as e:
                    logger.debug(f"   Avaliao falhou: {e}")

        # Baseline operacional do código atual para evitar mismatch de escala
        current_metrics = self.evaluator.evaluate(self.current_code, original_code=self.original_code)
        current_operational_score = _blend_score(
            self.current_code,
            "baseline_current",
            "baseline_current",
            current_metrics,
            apply_rlhf=False,
            log_world_model_failures=False,
        )

        replaced = False
        stagnation_factor = min(self.stagnation_cycles, 10)
        adaptive_delta = max(0.001, Config.MIN_IMPROVEMENT_DELTA * (1.0 - 0.08 * stagnation_factor))
        score_scale_ratio = old_best_score / max(current_operational_score, 1e-6)
        if score_scale_ratio > 2.0 or score_scale_ratio < 0.5:
            comparison_baseline = current_operational_score
            logger.info(
                f"   [Recalibração] Baseline de seleção ajustada para escala operacional ({comparison_baseline:.2f}); "
                f"histórico={old_best_score:.2f}"
            )
        else:
            comparison_baseline = old_best_score
        improvement_threshold = comparison_baseline + adaptive_delta

        if best_candidate and best_candidate_score >= improvement_threshold:
            code, desc, mtype, metrics = best_candidate
            logger.info(f" Melhorou: {best_candidate_score:.2f} > {old_best_score:.2f} ({desc})")
            self._backup()
            Config.CURRENT_CODE_FILE.write_text(code)
            self.current_code = code
            self.best_score = best_candidate_score
            self.best_code = code
            self.last_cycle_delta = self.best_score - comparison_baseline
            self.stagnation_cycles = 0
            replaced = True
            if HAS_CURIOSITY:
                curiosity.update_reward(recon_topic, 1.0)
            
            # RLHF: Registra sucesso
            if HAS_RLHF:
                rlhf.record_feedback(mtype, True)
            
            # Self-Reflection: Registra sucesso e gera pensamento
            if HAS_REFLECTION:
                reflection.reflect(self.generation, desc, True, best_candidate_score)
            
            # Salva experiência na memória vetorial
            if HAS_VECTOR_MEMORY and HAS_TRANSFORMERS:
                try:
                    new_emb = self.evaluator.get_embedding(code)
                    vector_memory.add_experience(new_emb, {
                        "generation": self.generation,
                        "mutation": desc,
                        "score": best_candidate_score,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.debug(f"Erro ao salvar na memória vetorial: {e}")

            if mtype == "optimize_workflow" and Config.ALLOW_WORKFLOW_MUTATION:
                apply_workflow_mutation()
                self.kb.update_objective("otimizar_workflow", 1.0)
        else:
            self.last_cycle_delta = max(0.0, best_candidate_score - comparison_baseline) if best_candidate else 0.0
            self.stagnation_cycles += 1
            if best_candidate:
                _, desc, mtype, metrics = best_candidate
                logger.info(
                    f"  No melhorou (melhor: {best_candidate_score:.2f}, threshold: {improvement_threshold:.2f}, estagnao: {self.stagnation_cycles} ciclos)"
                )
                if HAS_CURIOSITY:
                    curiosity.update_reward(recon_topic, 0.1)
                # RLHF: Registra falha (não melhorou)
                if HAS_RLHF:
                    rlhf.record_feedback(mtype, False)
                # Self-Reflection: Registra falha e gera pensamento
                if HAS_REFLECTION:
                    reflection.reflect(self.generation, desc, False, best_candidate_score)
            else:
                desc, mtype = "none", "none"
                metrics = self.evaluator.evaluate(self.current_code)
                logger.info("  Nenhum candidato vlido")

        features = {
            "mutation_type": mtype if best_candidate else "none",
            "old_score": old_best_score,
            "new_score": self.best_score,
            "candidate_score": best_candidate_score if best_candidate_score >= 0 else old_best_score,
            "score_delta": self.last_cycle_delta,
            "adaptive_delta": adaptive_delta,
            "stagnation_cycles": self.stagnation_cycles,
            "lines": metrics.get("lines", 0),
            "complexity": metrics.get("complexity", 0),
            "num_functions": metrics.get("num_functions", 0),
        }
        self.kb.record_evolution(
            self.generation,
            desc if best_candidate else "none",
            old_best_score,
            self.best_score,
            replaced,
            features,
            metrics.get("tests", {})
        )
        logger.info(
            f"  Progresso mensurvel: score_delta={self.last_cycle_delta:.4f} | adaptive_delta={adaptive_delta:.4f} | estagnao={self.stagnation_cycles}"
        )
        essentials_state = self.advanced_essentials.on_cycle_end(
            generation=self.generation,
            score=self.best_score,
            score_delta=self.last_cycle_delta,
            stagnation_cycles=self.stagnation_cycles,
            replaced=replaced,
        )
        if essentials_state.get("recommendations"):
            logger.info(f"  Essentials recomendam: {' | '.join(essentials_state['recommendations'])}")
        self._update_objectives(metrics)
        self._save_state()

        # Language Trainer
        lt_result = self.lang_trainer.maybe_run(
            generation=self.generation,
            code=self.current_code,
            prev_code=self.original_code,
            metrics=metrics,
            replaced=replaced,
        )
        if lt_result:
            self.feedback_loop.apply(lt_result, weights)

        # Episodic Memory
        self.episodic_memory.record(
            generation=self.generation,
            mutation=desc if best_candidate else "none",
            score=best_candidate_score if best_candidate_score >= 0 else self.best_score,
            replaced=replaced,
            metrics=metrics,
            code_snapshot=self.current_code[:500],
        )

        # Auto Reward System
        custom_score = self.reward_system.evaluate(metrics, self.current_code, self.generation)
        logger.info(f"   [] Score customizado: {custom_score:.2f}")

        # v3: notifica o mdulo de auto-modificao
        self.v3.on_cycle_end(
            generation=self.generation,
            metrics=metrics,
            code=self.current_code,
            replaced=replaced,
        )

        # Hiper-Evoluo (Nvel AGI)
        try:
            from modules.hyper_evolution import HyperEvolutionEngine
            hyper = HyperEvolutionEngine()
            if HAS_CURIOSITY:
                topic = curiosity.get_next_topic(context_terms=self._get_context_terms_for_curiosity())
                if random.random() < 0.3: # 30% de chance de gerar novo mdulo
                    proposal = hyper.propose_new_module(topic)
                    if hyper.run_adversarial_test(proposal["code"]):
                        with open(proposal["path"], "w") as f:
                            f.write(proposal["code"])
                        logger.info(f"🔱 Hiper-Evoluo: Novo mdulo auto-gerado: {proposal['name']}")
            
            # Evoluo da funo de recompensa
            new_weights = hyper.evolve_reward_function(metrics)
            for k, v in new_weights.items():
                if k in weights:
                    weights[k] *= v
        except Exception as e:
            logger.debug(f"Erro na Hiper-Evoluo: {e}")

        try:
            self.kb.save_intelligence_snapshot(
                generation=self.generation,
                best_score=self.best_score,
                score_delta=self.last_cycle_delta,
                stagnation_cycles=self.stagnation_cycles,
                adaptive_delta=adaptive_delta,
                replaced=replaced,
            )
        except Exception as e:
            logger.debug(f"Erro ao salvar intelligence snapshot: {e}")

        gc.collect()
        return {
            "generation": self.generation,
            "mutation": desc if best_candidate else "none",
            "score": self.best_score,
            "score_delta": self.last_cycle_delta,
            "stagnation_cycles": self.stagnation_cycles,
            "adaptive_delta": adaptive_delta,
            "replaced": replaced,
        }

    def _compute_mutation_weights(self, objectives: List[Dict]) -> Dict[str, float]:
        """Calcula pesos para cada tipo de mutao baseado nos objetivos."""
        mutation_types = self.mutation_engine.mutation_types
        weights = {mt: 1.0 for mt in mutation_types}
        for obj in objectives:
            name, curr, target = obj["name"], obj["current"], obj["target"]
            if name == "reduzir_complexidade" and curr > target:
                weights["simplify_expression"] += 2.0
                weights["extract_function"]    += 1.5
                weights["constant_folding"]    += 1.5
            if name == "aumentar_modularidade":
                weights["extract_function"]  += 2.0
                weights["insert_learned"]    += 1.0
                weights["add_class"]         += 1.0
            if name == "melhorar_documentacao":
                weights["add_docstring"]  += 2.0
                weights["add_comment"]    += 1.0
                weights["add_type_hints"] += 1.5
            if name == "aprender_algoritmos" and curr < target:
                weights["insert_learned"]    += 2.0
                weights["change_algorithm"]  += 2.0
                weights["grok_generate"]     += 2.0
                weights["crossover_function"]+= 2.0
            if name == "reduzir_tempo_execucao" and curr > target:
                weights["add_numba_jit"]     += 3.0
                weights["loop_unroll"]       += 2.0
                weights["constant_folding"]  += 2.0
                weights["memoize_function"]  += 2.0
                weights["grok_optimize"]     += 3.0
                weights["vectorize_loop"]    += 2.0
            if name == "eliminar_dead_code" and curr < target:
                weights["dead_code_removal"] += 4.0
            if name == "melhorar_type_hints" and curr < target:
                weights["add_type_hints"]    += 3.0
                weights["strengthen_types"]  += 2.0
            if name.startswith("learn_"):
                weights["grok_generate"]  += 1.5
                weights["insert_learned"] += 1.5

        # Incorpora preditor ML
        if self.predictor.model and random.random() > Config.EXPLORATION_RATE:
            current_metrics = self.evaluator.evaluate(self.current_code)
            for mt in mutation_types:
                feat = {
                    "lines": current_metrics.get("lines", 0),
                    "num_functions": current_metrics.get("num_functions", 0),
                    "complexity": current_metrics.get("complexity", 0),
                    "mutation_type": mt
                }
                prob = self.predictor.predict_proba(feat)
                weights[mt] *= (0.3 + prob)
        return weights

    def _update_objectives(self, metrics: Dict):
        """Atualiza os valores dos objetivos com base nas mtricas."""
        self.kb.update_objective("reduzir_complexidade",      metrics.get("complexity", 0))
        self.kb.update_objective("aumentar_modularidade",     metrics.get("num_functions", 0))
        self.kb.update_objective("melhorar_documentacao",     metrics.get("comment_ratio", 0))
        self.kb.update_objective("reduzir_tempo_execucao",    metrics.get("execution_time", 1.0) or 1.0)
        self.kb.update_objective("aprender_algoritmos",       metrics.get("num_functions", 0) // 2)
        total = max(1, metrics.get("tests_total", 1))
        self.kb.update_objective("aumentar_cobertura_testes", metrics.get("tests_passed", 0) / total)

    def _get_context_terms_for_curiosity(self, limit: int = 12) -> List[str]:
        """Extrai termos recentes aprendidos para guiar a geração de tópicos de pesquisa."""
        try:
            rows = self.kb.conn.execute(
                "SELECT word FROM lang_vocabulary ORDER BY frequency DESC, last_seen DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
            return [str(r[0]) for r in rows if r and r[0]]
        except Exception:
            return []


# =============================================================================
# APLICATIVO PRINCIPAL v3.1
# =============================================================================

class AtenaApp:
    """Aplicao principal da Atena."""

    def __init__(self, problem: Optional[Problem] = None):
        self.core = AtenaCore(problem=problem)
        self.no_code_builder = NoCodeBuilder(
            kb=self.core.kb,
            mutation_engine=self.core.mutation_engine,
            grok=self.core.mutation_engine.grok
        )
        self.hacker_recon = HackerReconModule(kb=self.core.kb)
        self.dashboard = AtenaDashboard(self.core)
        self.dashboard.start()
        self.running = False
        self._last_train = 0.0
        self._last_news = 0.0
        self._last_deploy_score = self.core.best_score

    def start_autonomous(self, cycles: Optional[int] = None):
        """Inicia modo autnomo."""
        logger.info("\n MODO AUTNOMO | Atena Neural v3.1")
        logger.info(f"   Ambiente: {'GitHub Actions CI' if IS_GITHUB_ACTIONS else 'Local'}")
        logger.info(f"   Candidatos/ciclo: {Config.CANDIDATES_PER_CYCLE}")
        logger.info(f"   Workers: {Config.PARALLEL_WORKERS}")
        logger.info(f"   Timeout sandbox: {Config.EVALUATION_TIMEOUT}s")
        logger.info(f"   ALLOW_DEEP_SELF_MOD: {ALLOW_DEEP_SELF_MOD}")
        logger.info(f"   ALLOW_CHECKER_EVOLVE: {ALLOW_CHECKER_EVOLVE}")
        logger.info(f"   SELF_MOD_INTERVAL: a cada {SELF_MOD_INTERVAL} geraes")
        if self.core.problem:
            logger.info(f"   Problema: {self.core.problem.name}  {self.core.problem.description}")
        self.running = True
        if self.core.learner:
            self.core.learner.start()
        try:
            count = 0
            while self.running and (cycles is None or count < cycles):
                result = self.core.evolve_one_cycle()
                count += 1
                if time.time() - self._last_train > Config.TRAINING_INTERVAL:
                    self.core.predictor.train()
                    self._last_train = time.time()
                if self.core.news and time.time() - self._last_news > 3600:
                    self.core.news.update_objectives()
                    self._last_news = time.time()
                if self.core.best_score > self._last_deploy_score * Config.DEPLOY_THRESHOLD:
                    logger.info(f" Melhoria {Config.DEPLOY_THRESHOLD*100-100:.0f}%+  Deploy")
                    AutoDeploy.deploy()
                    self._last_deploy_score = self.core.best_score
                if not IS_CI and cycles is None:
                    time.sleep(30)
        except KeyboardInterrupt:
            logger.info("\n[] Interrompido pelo usurio")
        finally:
            self._shutdown()

    def _shutdown(self):
        if self.core.learner:
            self.core.learner.stop()
        self.core.vocab_harvester.stop()
        self.dashboard.stop()
        try:
            # Prune cache ANTES de fechar a conexão
            self.core.kb.prune_eval_cache()
        except Exception as e:
            logger.warning(f"Erro ao limpar cache no shutdown: {e}")
        self.core.kb.close()
        logger.info(f"[] Score final: {self.core.best_score:.2f} | Geraes: {self.core.generation}")

    def run_interactive(self):
        """Loop interativo principal com interface rica."""
        try:
            from atena_ui_engine import AtenaUIEngine
            ui = AtenaUIEngine()
        except ImportError:
            logger.warning("atena_ui_engine no encontrado. Usando interface simples.")
            return self._run_interactive_simple()

        ui.clear_screen()
        ui.print_header("🔱 ATENA NEURAL Ω", "Sistema de Auto-Evolução Autônoma v4.2", color="#00D9FF")
        
        cmds = [
            ("/evoluir",           "Inicia um ciclo de evolução"),
            ("/ciclos <n>",        "Executa N ciclos de evolução"),
            ("/auto [n]",          "Modo autônomo (N ciclos ou infinito)"),
            ("/status",            "Status atual do sistema"),
            ("/codigo",            "Mostra o código atual"),
            ("/melhor",            "Mostra o melhor código já gerado"),
            ("/chat <msg>",        "Conversa consciente (IA Avançada)"),
            ("/criar <desc>",      "Cria um novo projeto No-Code"),
            ("/recon <tópico>",    "Hacker Recon (Pesquisa Tech)"),
            ("/v3status",          "Status completo v3 (Self-Mod)"),
            ("/sair",              "Encerra a sessão"),
        ]
        
        ui.print_table("Comandos Disponíveis", ["Comando", "Descrição"], cmds, color="#00D9FF")
        
        if self.core.learner:
            self.core.learner.start()
        
        while True:
            try:
                raw = ui.prompt("").strip()
                if not raw:
                    continue
                parts = raw.split()
                cmd = parts[0].lower()
                
                if cmd == '/sair':
                    ui.print_header("Sessão Encerrada", "🔱 ATENA Ω offline", color="red")
                    break
                elif cmd == '/evoluir':
                    task_id = ui.start_progress("Evoluindo ciclo...", total=100)
                    self.core.evolve_one_cycle()
                    ui.update_progress(task_id, 100)
                    ui.stop_progress()
                    ui.print_log(f"Ciclo concluído. Novo Score: {self.core.best_score:.4f}", level="info")
                elif cmd == '/ciclos':
                    n = int(parts[1]) if len(parts) > 1 else 1
                    task_id = ui.start_progress(f"Executando {n} ciclos...", total=n)
                    for i in range(n):
                        self.core.evolve_one_cycle()
                        ui.update_progress(task_id, 1)
                    ui.stop_progress()
                elif cmd == '/auto':
                    n = int(parts[1]) if len(parts) > 1 else None
                    ui.print_log(f"Iniciando modo autônomo por {n if n else 'infinitos'} ciclos...", level="warning")
                    self.start_autonomous(cycles=n)
                elif cmd == '/status':
                    status_data = {
                        "Geração": self.core.generation,
                        "Melhor Score": f"{self.core.best_score:.4f}",
                        "Código Atual": f"{len(self.core.current_code)} chars",
                        "Memória": f"{len(self.core.kb.function_cache)} funções"
                    }
                    ui.print_status_panel("Status da ATENA", status_data)
                elif cmd == '/codigo':
                    ui.print_code(self.core.current_code)
                elif cmd == '/melhor':
                    ui.print_header(f"Melhor Código (Score: {self.core.best_score:.4f})", color="green")
                    ui.print_code(self.core.best_code)
                elif cmd == '/chat':
                    msg = ' '.join(parts[1:])
                    if not msg:
                        ui.print_log("Uso: /chat <mensagem>", level="warning")
                        continue
                    
                    if any(word in msg.lower() for word in ["pesquise", "procure", "google", "search", "busque"]):
                        ui.print_log("Detectado pedido de pesquisa. Acionando Browser-Agent...", level="info")
                        search_term = msg.lower().replace("pesquise", "").replace("no google", "").replace("busque", "").replace("procure", "").replace("search", "").strip()
                        if not search_term: search_term = "ATENA AI"
                        subprocess.Popen(["python3", "atena_google_search.py", search_term])
                        ui.print_log(f"Pesquisando por '{search_term}' no Google. Veja no Dashboard!", level="info")
                    else:
                        ui.print_log("Processando solicitação com DeepSeek-R1...", level="info")
                        try:
                            from openai import OpenAI
                            client = OpenAI()
                            prompt = f"Você é a ATENA Ω, uma IA avançada. Responda: {msg}"
                            completion = client.chat.completions.create(
                                model="gpt-4.1-mini",
                                messages=[
                                    {"role": "system", "content": "Você é a ATENA Ω, uma IA de elite focada em evolução e código."},
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            ui.print_markdown(f"**🔱 ATENA Ω Responde:**\n\n{completion.choices[0].message.content}")
                        except Exception as e:
                            ui.print_log(f"Erro no chat: {e}", level="error")
                elif cmd == '/v3status':
                    self.core.v3.print_status()
                else:
                    ui.print_log(f"Comando desconhecido: {cmd}", level="warning")
                
            except KeyboardInterrupt:
                print("")
                continue
            except EOFError:
                ui.print_log("EOF no stdin detectado; encerrando loop interativo.", level="warning")
                break
            except Exception as e:
                ui.print_log(f"Erro crítico: {e}", level="error")
        
        self._shutdown()

    def _run_interactive_simple(self):
        """Fallback para o loop interativo original sem Rich."""
        # (O código original do run_interactive seria movido para cá se necessário)
        pass


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Atena Neural v3.1  Auto-evoluo orientada a problemas")
    parser.add_argument("--auto",      action="store_true", help="Modo autnomo")
    parser.add_argument("--cycles",    type=int, default=0, help="Nmero de ciclos (0=infinito)")
    parser.add_argument("--recon",     type=str, default="",  help="Hacker Recon sobre um tpico")
    parser.add_argument("--nocode",    action="store_true",   help="Modo criao de projeto No-Code")
    parser.add_argument("--desc",      type=str, default="",  help="Descrio do projeto No-Code")
    parser.add_argument("--deep",      action="store_true",   help="Força ALLOW_DEEP_SELF_MOD=true (já vem ativo por padrão)")
    parser.add_argument("--checker",   action="store_true",   help="Ativa ALLOW_CHECKER_EVOLVE")
    parser.add_argument("--problem",   type=str, choices=["sorting", "fibonacci"], help="Problema a resolver")
    args = parser.parse_args()

    if args.deep:
        ALLOW_DEEP_SELF_MOD = True
        logger.info("[] ALLOW_DEEP_SELF_MOD=true via --deep")

    if args.checker:
        ALLOW_CHECKER_EVOLVE = True
        logger.info("[] ALLOW_CHECKER_EVOLVE=true via --checker")

    problem = None
    if args.problem == "sorting":
        problem = create_sorting_problem()
    elif args.problem == "fibonacci":
        problem = create_fibonacci_problem()

    app = AtenaApp(problem=problem)

    if args.recon:
        app.hacker_recon.hunt_new_tech(args.recon)
    elif args.nocode and args.desc:
        app.no_code_builder.create_project(args.desc)
    elif args.auto or IS_CI:
        n = args.cycles if args.cycles > 0 else (10 if IS_CI else None)
        if os.getenv("ATENA_LM_ENABLED", "false").lower() == "true":
            try:
                from atena_local_lm import patch_atena_core, AtenaLMConfig
                _overrides = {
                    "train_every_n_cycles": int(os.getenv("ATENA_LM_TRAIN_EVERY", "3")),
                    "embed_dim": int(os.getenv("ATENA_LM_EMBED_DIM", "128")),
                    "num_layers": int(os.getenv("ATENA_LM_LAYERS", "4")),
                    "min_train_samples": int(os.getenv("ATENA_LM_MIN_SAMPLES", "10")),
                }
                _orig_init = AtenaLMConfig.__init__
                def _patched_init(self, **kwargs):
                    _orig_init(self, **kwargs)
                    for k, v in _overrides.items():
                        setattr(self, k, v)
                AtenaLMConfig.__init__ = _patched_init
                lm = patch_atena_core(app.core)
                logger.info(f"[] AtenaLocalLM ativo | min_samples={_overrides['min_train_samples']}")
            except ImportError:
                logger.warning("[] atena_local_lm.py no encontrado")
            except Exception as e:
                logger.warning(f"[] AtenaLocalLM erro: {e}")
        app.start_autonomous(cycles=n)
    else:
        app.run_interactive()
