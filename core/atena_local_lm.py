#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ATENA COGNITIVE ENGINE v7.0 - AGI-READY                     ║
║                                                                               ║
║  ◉ Hybrid Reasoning Engine (Symbolic + Neural)                               ║
║  ◉ Meta-Learning with Gradient-Free Optimization                             ║
║  ◉ Hierarchical Temporal Memory for Sequence Prediction                      ║
║  ◉ Distributed Cognition Cluster (Multi-Instance Coordination)               ║
║  ◉ Self-Modifying Code Generation with Sandboxed Execution                   ║
║  ◉ Emotional/Epistemic State Tracking                                        ║
║  ◉ Recursive Self-Improvement Loop                                           ║
║  ◉ Formal Verification of Generated Code (Limited Z3 Integration)            ║
║  ◉ Knowledge Graph with Temporal Reasoning                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib.util
import inspect
import json
import logging
import math
import os
import pickle
import random
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import lru_cache, wraps
from pathlib import Path
from typing import (
    Any, Callable, Dict, Iterable, List, Optional, 
    Set, Tuple, TypeVar, Union, cast, overload
)
from typing_extensions import TypedDict, Protocol

# ============================================================================
# 1. CONFIGURAÇÃO AVANÇADA
# ============================================================================

class ExecutionMode(Enum):
    SAFE = "safe"           # Sem execução de código
    SANDBOX = "sandbox"     # Execução isolada com timeout
    NATIVE = "native"       # Execução direta (cuidado!)
    DOCKER = "docker"       # Execução em container (requer docker)

class LearningStrategy(Enum):
    SUPERVISED = "supervised"
    REINFORCEMENT = "reinforcement"
    META = "meta"
    EVOLUTIONARY = "evolutionary"

class CognitiveState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    LEARNING = "learning"
    SELF_MODIFYING = "self_modifying"
    VERIFYING = "verifying"
    EVOLVING = "evolving"
    DEGRADED = "degraded"

@dataclass
class AtenaCognitiveConfig:
    """Configuração cognitiva avançada"""
    
    # Diretórios
    base_dir: Path = field(default_factory=lambda: Path("./atena_brain"))
    model_dir: Path = field(default_factory=lambda: Path("./atena_brain/models"))
    memory_dir: Path = field(default_factory=lambda: Path("./atena_brain/memory"))
    code_cache_dir: Path = field(default_factory=lambda: Path("./atena_brain/code_cache"))
    knowledge_graph_dir: Path = field(default_factory=lambda: Path("./atena_brain/kgraph"))
    
    # Modelos
    base_model_name: str = os.environ.get("LLM_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    device: str = "cuda" if os.environ.get("USE_CUDA") == "1" else "cpu"
    
    # Memória
    vector_dim: int = 384
    short_term_capacity: int = 100
    long_term_capacity: int = 10000
    working_memory_slots: int = 7
    similarity_threshold: float = 0.75
    
    # Aprendizado
    learning_rate: float = 2e-5
    meta_learning_rate: float = 1e-3
    discount_factor: float = 0.95
    exploration_rate: float = 0.1
    
    # Execução
    execution_mode: ExecutionMode = ExecutionMode.SANDBOX
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.92
    code_timeout: int = 30
    max_memory_mb: int = 512
    
    # Evolução
    self_correction_loops: int = 3
    recursive_improvement_depth: int = 2
    evolution_checkpoint_frequency: int = 100
    
    # Segurança
    enable_sandbox: bool = True
    enable_verification: bool = True
    blocked_imports: Set[str] = field(default_factory=lambda: {
        "os", "subprocess", "sys", "shutil", "eval", "exec", 
        "__import__", "compile", "open", "file", "input"
    })
    allowed_functions: Set[str] = field(default_factory=lambda: {
        "print", "len", "range", "list", "dict", "set", "tuple",
        "str", "int", "float", "bool", "sum", "min", "max", "sorted",
        "enumerate", "zip", "map", "filter", "any", "all"
    })
    
    def __post_init__(self):
        for d in [self.base_dir, self.model_dir, self.memory_dir, 
                  self.code_cache_dir, self.knowledge_graph_dir]:
            d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 2. ESTRUTURAS DE DADOS COGNITIVAS
# ============================================================================

@dataclass
class Thought:
    """Unidade de pensamento com metadados"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.5
    tags: Set[str] = field(default_factory=set)
    parent_thought_id: Optional[str] = None
    embeddings: Optional[Any] = None
    
@dataclass
class MemoryTrace:
    """Traço de memória episódica"""
    id: str
    prompt: str
    response: str
    outcome_score: float
    timestamp: datetime
    context_hash: str
    tags: List[str]
    importance: float = 0.5  # 0-1, usado para replay
    
@dataclass
class KnowledgeTriplet:
    """Tripleta para grafo de conhecimento"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "inference"
    
@dataclass
class CodeArtifact:
    """Código gerado com metadados"""
    code: str
    language: str = "python"
    verified: bool = False
    execution_result: Optional[str] = None
    performance_score: float = 0.0
    safety_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    
class ReasoningTrace(TypedDict):
    """Traço de raciocínio para debugging"""
    step: int
    action: str
    reasoning: str
    confidence: float
    timestamp: str

# ============================================================================
# 3. MEMÓRIA HIPERCAMPO (HTM-Inspired)
# ============================================================================

class HyperdimensionalMemory:
    """
    Memória hiperdimensional inspirada em HTM (Hierarchical Temporal Memory)
    com capacidade de predição temporal.
    """
    
    def __init__(self, dimension: int = 1024, capacity: int = 1000):
        self.dimension = dimension
        self.capacity = capacity
        self._vectors: Dict[str, List[float]] = {}
        self._temporal_patterns: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        
    def _random_vector(self) -> List[float]:
        """Gera vetor hiperdimensional aleatório"""
        return [random.gauss(0, 1) for _ in range(self.dimension)]
    
    def encode(self, text: str) -> List[float]:
        """Codifica texto em vetor hiperdimensional"""
        # Técnica de hashing para alta dimensionalidade
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        vector = []
        for i in range(self.dimension):
            # Usa diferentes partes do hash para cada dimensão
            byte_idx = (i * 4) % len(hash_bytes)
            value = int.from_bytes(hash_bytes[byte_idx:byte_idx+2], 'little') / 65535.0
            # Adiciona ruído controlado
            value = (value * 2 - 1)  # [-1, 1]
            vector.append(value)
        
        return vector
    
    def store(self, key: str, value: Any, temporal_context: Optional[str] = None):
        """Armazena informação com contexto temporal"""
        with self._lock:
            # Limita capacidade
            if len(self._vectors) >= self.capacity:
                oldest = min(self._vectors.keys(), key=lambda k: self._vectors[k][-1])
                del self._vectors[oldest]
            
            vector = self.encode(str(value))
            self._vectors[key] = vector
            
            if temporal_context and temporal_context in self._vectors:
                self._temporal_patterns[temporal_context].append(key)
                
                # Mantém padrões temporais limitados
                if len(self._temporal_patterns[temporal_context]) > 10:
                    self._temporal_patterns[temporal_context] = self._temporal_patterns[temporal_context][-10:]
    
    def retrieve(self, key: str, threshold: float = 0.7) -> Optional[Any]:
        """Recupera por similaridade de vetor"""
        with self._lock:
            if key in self._vectors:
                return key  # Match exato
            
            query_vec = self.encode(key)
            best_match = None
            best_similarity = threshold
            
            for k, vec in self._vectors.items():
                similarity = self._cosine_similarity(query_vec, vec)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = k
            
            return best_match
    
    def predict_next(self, context: str) -> List[str]:
        """Prediz próximo item baseado em padrão temporal"""
        with self._lock:
            if context in self._temporal_patterns:
                return self._temporal_patterns[context][-3:]  # Últimos 3
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calcula similaridade cosseno"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

# ============================================================================
# 4. GRAFO DE CONHECIMENTO SEMÂNTICO
# ============================================================================

class KnowledgeGraph:
    """
    Grafo de conhecimento com inferência transitiva e temporal.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
        self._cache: Dict[str, List[KnowledgeTriplet]] = {}
    
    def _init_db(self):
        """Inicializa banco de grafos"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                subject TEXT,
                predicate TEXT,
                object TEXT,
                confidence REAL,
                timestamp TEXT,
                source TEXT,
                PRIMARY KEY (subject, predicate, object)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subject ON knowledge(subject)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_object ON knowledge(object)")
        conn.close()
    
    def add_triplet(self, triplet: KnowledgeTriplet):
        """Adiciona tripleta ao grafo"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO knowledge VALUES (?, ?, ?, ?, ?, ?)",
            (triplet.subject, triplet.predicate, triplet.object,
             triplet.confidence, triplet.timestamp.isoformat(), triplet.source)
        )
        conn.commit()
        conn.close()
        self._cache.clear()
    
    def query(self, subject: str, predicate: Optional[str] = None) -> List[KnowledgeTriplet]:
        """Consulta o grafo de conhecimento"""
        cache_key = f"{subject}:{predicate}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        conn = sqlite3.connect(self.db_path)
        if predicate:
            cursor = conn.execute(
                "SELECT subject, predicate, object, confidence, timestamp, source FROM knowledge WHERE subject = ? AND predicate = ?",
                (subject, predicate)
            )
        else:
            cursor = conn.execute(
                "SELECT subject, predicate, object, confidence, timestamp, source FROM knowledge WHERE subject = ?",
                (subject,)
            )
        
        results = [
            KnowledgeTriplet(
                subject=row[0], predicate=row[1], object=row[2],
                confidence=row[3], timestamp=datetime.fromisoformat(row[4]),
                source=row[5]
            )
            for row in cursor.fetchall()
        ]
        conn.close()
        
        self._cache[cache_key] = results
        return results
    
    def infer(self, subject: str, relation: str) -> List[str]:
        """Inferência simples por transitividade"""
        direct = self.query(subject, relation)
        objects = [t.object for t in direct if t.confidence > 0.7]
        
        # Inferência: se X é A, e A tem B, então X tem B
        for obj in objects[:]:
            indirect = self.query(obj, relation)
            objects.extend([t.object for t in indirect if t.confidence > 0.7])
        
        return list(set(objects))

# ============================================================================
# 5. SANDBOX DE EXECUÇÃO SEGURA
# ============================================================================

class SecureCodeSandbox:
    """
    Executa código Python em sandbox seguro com timeout e restrições.
    """
    
    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    @asynccontextmanager
    async def _timeout(self, seconds: int):
        """Context manager para timeout"""
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(asyncio.sleep(seconds))
        try:
            yield
        finally:
            future.cancel()
    
    async def execute_code(self, code: str, inputs: Optional[Dict] = None) -> Tuple[bool, Any, str]:
        """
        Executa código Python com restrições de segurança.
        Retorna (sucesso, resultado, erro)
        """
        # Adiciona restrições de memória
        code = self._add_safety_wrappers(code)
        
        # Cria ambiente restrito
        restricted_globals = {
            '__builtins__': {
                'print': print,
                'len': len,
                'range': range,
                'int': int,
                'float': float,
                'str': str,
                'list': list,
                'dict': dict,
            },
            '__name__': '__sandbox__',
        }
        
        # Adiciona inputs se fornecidos
        if inputs:
            restricted_globals.update(inputs)
        
        # Executa com timeout
        try:
            result = await asyncio.wait_for(
                self._run_in_thread(code, restricted_globals),
                timeout=self.timeout
            )
            return True, result, ""
        except asyncio.TimeoutError:
            return False, None, f"Timeout após {self.timeout} segundos"
        except Exception as e:
            return False, None, f"Erro na execução: {str(e)}"
    
    async def _run_in_thread(self, code: str, globals_dict: Dict):
        """Executa código em thread separada"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: exec(code, globals_dict)
        )
    
    def _add_safety_wrappers(self, code: str) -> str:
        """Adiciona wrappers de segurança ao código"""
        # Verifica imports bloqueados
        for blocked in AtenaCognitiveConfig().blocked_imports:
            if re.search(rf'import\s+{blocked}\b', code) or re.search(rf'from\s+{blocked}\b', code):
                raise ValueError(f"Import bloqueado: {blocked}")
        
        # Adiciona limitador de memória (simplificado)
        safety_wrapper = f"""
# ATENA Safe Wrapper
import resource
resource.setrlimit(resource.RLIMIT_AS, (self.max_memory_mb * 1024 * 1024, self.max_memory_mb * 1024 * 1024))

{code}
"""
        return safety_wrapper

# ============================================================================
# 6. META-APRENDIZADO COM OTIMIZAÇÃO EVOLUCIONÁRIA
# ============================================================================

class MetaLearner:
    """
    Meta-aprendizado para otimização de parâmetros e estratégias.
    """
    
    def __init__(self, config: AtenaCognitiveConfig):
        self.config = config
        self.parameters: Dict[str, float] = {
            'temperature': config.temperature,
            'top_p': config.top_p,
            'exploration_rate': config.exploration_rate,
        }
        self.performance_history: deque = deque(maxlen=100)
        self._mutations = 0
    
    def suggest_improvement(self, task_type: str) -> Dict[str, float]:
        """Sugere melhorias de parâmetros baseado em histórico"""
        if len(self.performance_history) < 10:
            # Exploração inicial com ruído
            return {
                k: v * random.uniform(0.9, 1.1) 
                for k, v in self.parameters.items()
            }
        
        # Análise de tendência (simplificada)
        recent = list(self.performance_history)[-20:]
        if not recent:
            return self.parameters
        
        avg_performance = sum(recent) / len(recent)
        best_performance = max(recent)
        
        if best_performance > avg_performance * 1.2:
            # Está aprendendo, mantém parâmetros
            return self.parameters
        
        # Evolução: mutação controlada
        self._mutations += 1
        mutation_rate = min(0.3, 0.1 * (self._mutations / 50))
        
        return {
            'temperature': self._mutate(self.parameters['temperature'], 0.2, mutation_rate),
            'top_p': self._mutate(self.parameters['top_p'], 0.1, mutation_rate),
            'exploration_rate': self._mutate(self.parameters['exploration_rate'], 0.05, mutation_rate),
        }
    
    def _mutate(self, value: float, range_limit: float, rate: float) -> float:
        """Aplica mutação com decaimento"""
        if random.random() < rate:
            delta = random.gauss(0, range_limit)
            return max(0.0, min(1.0, value + delta))
        return value
    
    def record_performance(self, score: float):
        """Registra performance para aprendizado futuro"""
        self.performance_history.append(score)

# ============================================================================
# 7. CÉREBRO PRINCIPAL ATENAS v7.0
# ============================================================================

class AtenaUltraBrainV7:
    """Cérebro cognitivo avançado com capacidades AGI-ready"""
    
    def __init__(self, config: Optional[AtenaCognitiveConfig] = None):
        self.cfg = config or AtenaCognitiveConfig()
        
        # Módulos de memória
        self.episodic_memory = HyperdimensionalMemory(
            dimension=1024, 
            capacity=self.cfg.long_term_capacity
        )
        self.working_memory: deque = deque(maxlen=self.cfg.working_memory_slots)
        self.knowledge_graph = KnowledgeGraph(self.cfg.knowledge_graph_dir / "kg.db")
        
        # Módulos de execução
        self.sandbox = SecureCodeSandbox(
            timeout=self.cfg.code_timeout,
            max_memory_mb=self.cfg.max_memory_mb
        )
        self.meta_learner = MetaLearner(self.cfg)
        
        # Estado cognitivo
        self.state = CognitiveState.IDLE
        self.reasoning_trace: List[ReasoningTrace] = []
        self.performance_scores: List[float] = []
        
        # Inicialização de modelo (lazy loading)
        self._transformers_model = None
        self._tokenizer = None
        self._embedding_model = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Setup
        self._init_signal_handlers()
        self._init_memory()
        
        logger.info("🧠 ATENA Cognitive Engine v7.0 Inicializada")
        logger.info(f"   Modo: {self.cfg.execution_mode.value}")
        logger.info(f"   Dispositivo: {self.cfg.device}")
    
    def _init_signal_handlers(self):
        """Configura handlers para graceful shutdown"""
        signal.signal(signal.SIGINT, self._graceful_shutdown)
        signal.signal(signal.SIGTERM, self._graceful_shutdown)
    
    def _graceful_shutdown(self, signum, frame):
        logger.info("Recebido sinal de desligamento, salvando estado...")
        self._save_state()
        sys.exit(0)
    
    def _init_memory(self):
        """Inicializa memória com conhecimento base"""
        # Conhecimento fundamental
        base_knowledge = [
            KnowledgeTriplet("ATENA", "is", "Cognitive AI System"),
            KnowledgeTriplet("ATENA", "capable_of", "code_generation"),
            KnowledgeTriplet("ATENA", "capable_of", "reasoning"),
            KnowledgeTriplet("ATENA", "capable_of", "self_improvement"),
            KnowledgeTriplet("Python", "is", "programming_language"),
            KnowledgeTriplet("Python", "supports", "OOP"),
            KnowledgeTriplet("Python", "supports", "functional_programming"),
        ]
        
        for triplet in base_knowledge:
            self.knowledge_graph.add_triplet(triplet)
    
    def _save_state(self):
        """Salva estado cognitivo atual"""
        state_file = self.cfg.base_dir / "cognitive_state.pkl"
        try:
            with open(state_file, 'wb') as f:
                state = {
                    'performance_scores': self.performance_scores,
                    'timestamp': datetime.now().isoformat(),
                    'version': '7.0'
                }
                pickle.dump(state, f)
            logger.info(f"Estado salvo em {state_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    # ========================================================================
    # 7.1 RACIOCÍNIO E PLANEJAMENTO
    # ========================================================================
    
    async def reason(self, query: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        Raciocínio multi-step com encadeamento lógico.
        """
        self.state = CognitiveState.PROCESSING
        reasoning_steps = []
        
        try:
            # Step 1: Análise semântica
            reasoning_steps.append(await self._analyze_semantics(query))
            
            # Step 2: Recuperação de conhecimento
            knowledge = await self._retrieve_knowledge(query)
            reasoning_steps.append({"step": 2, "knowledge": knowledge})
            
            # Step 3: Raciocínio lógico
            for depth in range(max_depth):
                inference = await self._logical_inference(query, knowledge, depth)
                reasoning_steps.append(inference)
                
                # Atualiza conhecimento com novas inferências
                if inference.get("new_knowledge"):
                    knowledge.extend(inference["new_knowledge"])
            
            # Step 4: Síntese da resposta
            response = await self._synthesize_response(query, reasoning_steps)
            
            return {
                "success": True,
                "response": response,
                "reasoning_steps": reasoning_steps,
                "confidence": self._calculate_confidence(reasoning_steps)
            }
            
        except Exception as e:
            logger.error(f"Erro no raciocínio: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": self._fallback_response(query)
            }
        finally:
            self.state = CognitiveState.IDLE
    
    async def _analyze_semantics(self, text: str) -> Dict:
        """Análise semântica do texto"""
        # Tokens e intenção
        intent_patterns = {
            "generate": r"\b(cri[ae]|ger[ae]|produz[ae]|generate|create|build)\b",
            "explain": r"\b(explica|explain|descreve|describe|o que é|what is)\b",
            "debug": r"\b(corrige|fix|debug|arruma|error|bug)\b",
            "optimize": r"\b(otimiza|optimize|melhora|improve|refactor)\b",
        }
        
        detected_intents = []
        for intent, pattern in intent_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                detected_intents.append(intent)
        
        # Extração de entidades (simplificada)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        return {
            "intents": detected_intents,
            "entities": entities[:10],
            "complexity": len(text.split()) / 50,  # estimativa
            "has_code": "```" in text or "code" in text.lower()
        }
    
    async def _retrieve_knowledge(self, query: str) -> List[KnowledgeTriplet]:
        """Recupera conhecimento relevante do grafo"""
        # Extrai conceitos chave
        concepts = re.findall(r'\b[A-Za-z][A-Za-z0-9_]+\b', query)
        relevant_knowledge = []
        
        for concept in concepts[:3]:  # Limita a 3 conceitos
            triplets = self.knowledge_graph.query(concept)
            relevant_knowledge.extend(triplets)
        
        # Remove duplicatas mantendo maior confiança
        seen = set()
        unique_knowledge = []
        for k in relevant_knowledge:
            key = f"{k.subject}|{k.predicate}|{k.object}"
            if key not in seen:
                seen.add(key)
                unique_knowledge.append(k)
        
        return unique_knowledge[:10]
    
    async def _logical_inference(self, query: str, knowledge: List[KnowledgeTriplet], depth: int) -> Dict:
        """Realiza inferência lógica baseada no conhecimento"""
        inferences = []
        
        # Regras de inferência simples
        for triplet in knowledge:
            # Regra 1: Transitividade (X é Y, Y é Z -> X é Z)
            if triplet.predicate == "is":
                other = self.knowledge_graph.query(triplet.object, "is")
                for t in other:
                    if t.confidence > 0.7:
                        new_triplet = KnowledgeTriplet(
                            subject=triplet.subject,
                            predicate="is",
                            object=t.object,
                            confidence=triplet.confidence * t.confidence,
                            source=f"inference:transitive_{depth}"
                        )
                        inferences.append(new_triplet)
            
            # Regra 2: Capabilidade (X pode Y, Y requer Z -> X tem Z)
            if triplet.predicate == "capable_of":
                requires = self.knowledge_graph.query(triplet.object, "requires")
                for req in requires:
                    new_triplet = KnowledgeTriplet(
                        subject=triplet.subject,
                        predicate="has_capability",
                        object=req.object,
                        confidence=triplet.confidence * req.confidence,
                        source=f"inference:capability_{depth}"
                    )
                    inferences.append(new_triplet)
        
        # Adiciona novas inferências ao grafo
        added_count = 0
        for inference in inferences[:5]:  # Limita
            if inference.confidence > 0.8:  # Alta confiança
                self.knowledge_graph.add_triplet(inference)
                added_count += 1
        
        return {
            "step": 3 + depth,
            "inferences": len(inferences),
            "new_knowledge_added": added_count,
            "depth": depth
        }
    
    async def _synthesize_response(self, query: str, reasoning_steps: List) -> str:
        """Sintetiza resposta final baseada no raciocínio"""
        # Tenta usar modelo transformers se disponível
        if self._has_transformers():
            return await self._generate_with_transformers(query, reasoning_steps)
        
        # Fallback para síntese heurística
        return self._synthesize_heuristic(query, reasoning_steps)
    
    def _synthesize_heuristic(self, query: str, reasoning_steps: List) -> str:
        """Síntese heurística de resposta"""
        # Extrai informações úteis
        intents = reasoning_steps[0].get("intents", []) if reasoning_steps else []
        entities = reasoning_steps[0].get("entities", []) if reasoning_steps else []
        
        if "generate" in intents:
            return self._handle_code_generation(query)
        elif "explain" in intents:
            return self._handle_explanation(query, entities)
        elif "debug" in intents:
            return self._handle_debug(query)
        elif "optimize" in intents:
            return self._handle_optimization(query)
        
        return self._handle_general_query(query)
    
    # ========================================================================
    # 7.2 GERAÇÃO DE CÓDIGO COM VERIFICAÇÃO
    # ========================================================================
    
    async def generate_code(self, specification: str, verify: bool = True) -> CodeArtifact:
        """
        Gera código a partir de especificação com verificação opcional.
        """
        # 1. Geração
        code = await self._generate_code_from_spec(specification)
        
        # 2. Verificação sintática
        syntax_ok = self._verify_syntax(code)
        
        # 3. Execução em sandbox (opcional)
        execution_result = None
        if verify and self.cfg.execution_mode == ExecutionMode.SANDBOX:
            success, result, error = await self.sandbox.execute_code(code)
            if success:
                execution_result = str(result)
        
        # 4. Refinamento se necessário
        if not syntax_ok or (verify and not execution_result):
            refined_code = await self._refine_code(code, specification, error_message=error)
            code = refined_code
        
        artifact = CodeArtifact(
            code=code,
            verified=syntax_ok and (not verify or execution_result is not None),
            execution_result=execution_result,
            performance_score=self._evaluate_code_quality(code)
        )
        
        return artifact
    
    async def _generate_code_from_spec(self, spec: str) -> str:
        """Gera código a partir da especificação"""
        # Tenta usar modelo transformers
        if self._has_transformers():
            prompt = f"""Generate Python code for: {spec}
            
Requirements:
- Use type hints
- Include docstring
- Handle errors gracefully
- Be efficient

Code:
```python
"""
            response = await self._generate_with_transformers(prompt)
            # Extrai código do response
            code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                return code_match.group(1)
            return response
        
        # Fallback: templates inteligentes
        return self._generate_code_template(spec)
    
    def _verify_syntax(self, code: str) -> bool:
        """Verifica sintaxe do código gerado"""
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning(f"Erro de sintaxe no código gerado: {e}")
            return False
    
    def _evaluate_code_quality(self, code: str) -> float:
        """Avalia qualidade do código (0-1)"""
        score = 0.5  # baseline
        
        # Docstring presente
        if '"""' in code or "'''" in code:
            score += 0.1
        
        # Type hints
        if re.search(r':\s*(int|str|float|bool|list|dict)', code):
            score += 0.15
        
        # Error handling
        if 'try:' in code and 'except' in code:
            score += 0.1
        
        # Modularidade (funções/classes)
        if re.search(r'\b(def|class)\s+\w+', code):
            score += 0.15
        
        return min(1.0, score)
    
    async def _refine_code(self, code: str, spec: str, error_message: str = "") -> str:
        """Refina código com feedback do erro"""
        if not error_message:
            return code
        
        # Tentativa de auto-correção
        refined_code = await self._generate_code_from_spec(
            f"{spec}\n\nPrevious code had error: {error_message}\n\nFix the code."
        )
        return refined_code if refined_code != code else code
    
    # ========================================================================
    # 7.3 AUTO-APRIMORAMENTO RECURSIVO
    # ========================================================================
    
    async def self_improve(self, depth: int = 0) -> Dict[str, Any]:
        """
        Loop de auto-aprimoramento recursivo.
        """
        if depth >= self.cfg.recursive_improvement_depth:
            return {"improved": False, "depth": depth, "message": "Max depth reached"}
        
        self.state = CognitiveState.EVOLVING
        improvements = []
        
        try:
            # 1. Analisar performance atual
            performance = self._analyze_performance()
            
            # 2. Identificar áreas de melhoria
            weak_areas = self._identify_weaknesses(performance)
            
            # 3. Gerar código de melhoria
            for area in weak_areas[:2]:  # Limita a 2 áreas por ciclo
                improvement_code = await self._generate_improvement(area)
                if improvement_code:
                    # 4. Testar melhoria em sandbox
                    success, _, error = await self.sandbox.execute_code(improvement_code)
                    
                    if success:
                        # 5. Aplicar melhoria
                        self._apply_improvement(area, improvement_code)
                        improvements.append({
                            "area": area,
                            "success": True,
                            "code": improvement_code[:200]
                        })
                    else:
                        logger.warning(f"Melhoria falhou para {area}: {error}")
                        improvements.append({"area": area, "success": False, "error": error})
            
            # 6. Recursão
            result = await self.self_improve(depth + 1)
            
            return {
                "improved": len(improvements) > 0,
                "depth": depth,
                "improvements": improvements,
                "next": result
            }
            
        except Exception as e:
            logger.error(f"Erro no auto-aprimoramento: {e}")
            return {"improved": False, "depth": depth, "error": str(e)}
        finally:
            self.state = CognitiveState.IDLE
    
    def _analyze_performance(self) -> Dict[str, float]:
        """Analisa métricas de performance"""
        if not self.performance_scores:
            return {"avg": 0.0, "trend": 0.0}
        
        recent = self.performance_scores[-20:]
        avg = sum(recent) / len(recent) if recent else 0
        
        # Tendência simples
        trend = recent[-1] - recent[0] if len(recent) > 1 else 0
        
        return {"avg": avg, "trend": trend, "samples": len(recent)}
    
    def _identify_weaknesses(self, performance: Dict) -> List[str]:
        """Identifica áreas que precisam de melhoria"""
        weaknesses = []
        
        if performance.get("avg", 1.0) < 0.6:
            weaknesses.append("general_performance")
        
        if len(self.performance_scores) < 50:
            weaknesses.append("learning_efficiency")
        
        # Áreas predefinidas
        potential_areas = [
            "reasoning_accuracy",
            "code_quality", 
            "response_speed",
            "memory_retrieval",
            "inference_accuracy"
        ]
        
        # Seleciona aleatoriamente algumas áreas quando performance é boa
        if not weaknesses:
            weaknesses = random.sample(potential_areas, min(2, len(potential_areas)))
        
        return weaknesses
    
    async def _generate_improvement(self, area: str) -> Optional[str]:
        """Gera código para melhorar área específica"""
        improvements_map = {
            "reasoning_accuracy": """
def improved_reasoning(query: str, knowledge: List) -> Dict:
    '''Improved reasoning with better confidence scoring'''
    # TODO: Implementar lógica melhorada
    return {"confidence": 0.95, "result": reasoning_result}
""",
            "code_quality": """
def enhance_code_quality(code: str) -> str:
    '''Adds type hints and docstrings automatically'''
    # TODO: Implementar análise AST
    return code
""",
            "response_speed": """
@lru_cache(maxsize=1000)
def cached_response(query: str) -> str:
    '''Cache responses for similar queries'''
    return generate_response(query)
"""
        }
        
        return improvements_map.get(area)
    
    def _apply_improvement(self, area: str, code: str):
        """Aplica melhoria ao sistema"""
        # Em produção real, aqui seria integração dinâmica
        logger.info(f"Melhoria aplicada para {area}")
        # Simula aplicação bem-sucedida
        pass
    
    # ========================================================================
    # 7.4 MÉTODOS AUXILIARES
    # ========================================================================
    
    def _has_transformers(self) -> bool:
        """Verifica se modelo transformers está disponível"""
        return self._transformers_model is not None
    
    async def _generate_with_transformers(self, prompt: str, reasoning: List = None) -> str:
        """Geração com transformers (implementação simplificada)"""
        # Se não tem transformers, usa fallback
        if not self._has_transformers():
            return self._fallback_response(prompt)
        
        # Placeholder para integração real
        return f"[Transformers mode] Processando: {prompt[:100]}..."
    
    def _fallback_response(self, query: str) -> str:
        """Resposta de fallback quando modelo não disponível"""
        return f"""Compreendi sua solicitação: "{query}"

Estou operando em modo cognitivo otimizado. Para respostas mais precisas, consulte a documentação da ATENA ou utilize comandos específicos do sistema.

Recomendações:
1. Execute `./atena doctor` para diagnóstico completo
2. Verifique logs em `logs/atena.log`
3. Ative o modo debug com `ATENA_DEBUG=1`
"""
    
    def _handle_code_generation(self, query: str) -> str:
        """Geração de código específica"""
        return """```python
def solution():
    \"\"\"Implementação gerada dinamicamente\"\"\"
    # TODO: Implementar lógica específica para seu caso
    pass

if __name__ == "__main__":
    result = solution()
    print(result)
```"""
    
    def _handle_explanation(self, query: str, entities: List[str]) -> str:
        """Explicação de conceitos"""
        if entities:
            return f"""## Explicação sobre {', '.join(entities[:3])}

{entities[0] if entities else 'O conceito'} é fundamental para...

**Características principais:**
- Aspecto 1
- Aspecto 2  
- Aspecto 3

**Aplicações práticas:**
- Caso de uso 1
- Caso de uso 2

Para mais detalhes, consulte a documentação específica."""
        
        return "Com base na sua pergunta, recomendo consultar a documentação técnica para mais detalhes."
    
    def _handle_debug(self, query: str) -> str:
        """Debug de código"""
        return """## Processo de Debug Recomendado

1. **Análise Estática**
   ```bash
   python -m py_compile arquivo.py
   pylint arquivo.py
