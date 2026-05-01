#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Real Meta-Learner v3.0
Sistema de aprendizado contínuo que analisa DADOS REAIS de logs, evolução e histórico
para otimizar parâmetros dinamicamente, sem valores hardcoded.

Recursos:
- 📊 Análise multidimensional de padrões de evolução
- 🧠 Otimização adaptativa de hiperparâmetros
- 📈 Previsão de tendências com regressão
- 🔄 Feedback loop contínuo com reinforcement learning
- 📝 Geração de relatórios de autorreflexão
- 🎯 Recomendações acionáveis baseadas em dados reais
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import sys
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Union
import threading

# Tentativa de importar numpy para análise avançada
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger("atena.meta_learner")

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_DIR = ROOT / "evolution"
LOGS_DIR = EVOLUTION_DIR / "logs"
EVO_DIR = ROOT / "atena_evolution"
REPORTS_DIR = ROOT / "analysis_reports"
META_DB = EVOLUTION_DIR / "meta_learner.db"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class EvolutionPattern:
    """Padrão extraído de ciclos reais de evolução."""
    syntax_errors: int = 0
    logic_errors: int = 0
    security_violations: int = 0
    timeout_errors: int = 0
    total_mutations: int = 0
    successful_mutations: int = 0
    best_mutation_type: str = ""
    worst_mutation_type: str = ""
    avg_fitness: float = 0.0
    fitness_trend: str = "sem_dados"
    most_successful_api: str = ""
    api_success_rate: float = 0.0
    project_type_bias: Dict[str, float] = field(default_factory=dict)
    sampled_cycles: int = 0
    fitness_history: List[float] = field(default_factory=list)
    mutation_success_rates: Dict[str, float] = field(default_factory=dict)
    time_series: Dict[str, List[float]] = field(default_factory=dict)
    anomaly_detected: bool = False
    anomaly_description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "syntax_errors": self.syntax_errors,
            "logic_errors": self.logic_errors,
            "security_violations": self.security_violations,
            "timeout_errors": self.timeout_errors,
            "total_mutations": self.total_mutations,
            "successful_mutations": self.successful_mutations,
            "success_rate": round(self.successful_mutations / max(1, self.total_mutations), 4),
            "best_mutation_type": self.best_mutation_type,
            "worst_mutation_type": self.worst_mutation_type,
            "avg_fitness": self.avg_fitness,
            "fitness_trend": self.fitness_trend,
            "most_successful_api": self.most_successful_api,
            "api_success_rate": self.api_success_rate,
            "project_type_bias": self.project_type_bias,
            "sampled_cycles": self.sampled_cycles,
            "mutation_success_rates": self.mutation_success_rates,
            "anomaly_detected": self.anomaly_detected,
            "anomaly_description": self.anomaly_description
        }


@dataclass
class OptimizedParams:
    """Parâmetros otimizados pelo meta-learner."""
    temperature: float = 0.7
    security_rigor: str = "NORMAL"
    mutation_strength: float = 0.3
    population_size: int = 5
    preferred_strategy: str = ""
    risk_threshold: float = 0.75
    exploration_rate: float = 0.2
    learning_rate: float = 0.1
    batch_size: int = 32
    reasoning: List[str] = field(default_factory=list)
    confidence: float = 0.5
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "security_rigor": self.security_rigor,
            "mutation_strength": self.mutation_strength,
            "population_size": self.population_size,
            "preferred_strategy": self.preferred_strategy,
            "risk_threshold": self.risk_threshold,
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "version": self.version
        }


# =============================================================================
# Time Series Analyzer
# =============================================================================

class TimeSeriesAnalyzer:
    """Analisa séries temporais de fitness e métricas."""
    
    @staticmethod
    def calculate_trend(values: List[float]) -> Tuple[str, float]:
        """
        Calcula tendência usando regressão linear.
        
        Returns:
            Tuple[tipo_tendencia, inclinacao]
        """
        if len(values) < 3:
            return "insuficiente", 0.0
        
        if HAS_NUMPY:
            x = np.arange(len(values))
            slope = np.polyfit(x, values, 1)[0]
        else:
            # Regressão manual
            n = len(values)
            x = list(range(n))
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_x2 = sum(xi * xi for xi in x)
            
            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                slope = 0.0
            else:
                slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        if slope > 0.02:
            return "melhora", slope
        elif slope < -0.02:
            return "piora", slope
        else:
            return "estavel", slope
    
    @staticmethod
    def detect_anomalies(values: List[float], threshold: float = 2.0) -> List[int]:
        """Detecta anomalias usando desvio padrão."""
        if len(values) < 5:
            return []
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        
        anomalies = []
        for i, v in enumerate(values):
            if abs(v - mean) > threshold * std_dev:
                anomalies.append(i)
        
        return anomalies
    
    @staticmethod
    def moving_average(values: List[float], window: int = 5) -> List[float]:
        """Calcula média móvel."""
        if len(values) < window:
            return values
        
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            avg = sum(values[start:i+1]) / (i - start + 1)
            result.append(avg)
        
        return result


# =============================================================================
# Self-Reflective Meta-Learner
# =============================================================================

class SelfReflectiveMetaLearner:
    """
    Meta-learner avançado que lê dados reais de:
    - digital_organism_memory.jsonl (ciclos de vida)
    - evolution/logs/*.log (logs de texto)
    - analysis_reports/*.json (relatórios JSON)
    - meta_learner.db (histórico próprio)
    - mutation_stats (estatísticas de mutações)
    """
    
    def __init__(self, history_path: str | None = None):
        self.history_path = Path(history_path) if history_path else LOGS_DIR
        self.evo_dir = EVO_DIR
        self.reports_dir = REPORTS_DIR
        self._lock = threading.RLock()
        self._pattern_cache: Optional[EvolutionPattern] = None
        self._last_analysis: float = 0
        self._cache_ttl: int = 60  # segundos
        
        META_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        logger.info("🔬 SelfReflectiveMetaLearner v3.0 inicializado")
    
    # ── Database Initialization ───────────────────────────────────────────────
    
    def _init_db(self) -> None:
        """Inicializa banco de dados com schema otimizado."""
        with sqlite3.connect(META_DB) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS meta_cycles (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         REAL    NOT NULL,
                    patterns   TEXT    NOT NULL,
                    params     TEXT    NOT NULL,
                    sampled    INTEGER NOT NULL DEFAULT 0,
                    version    INTEGER DEFAULT 1
                );
                
                CREATE TABLE IF NOT EXISTS mutation_stats (
                    mutation_type  TEXT PRIMARY KEY,
                    success_count  INTEGER DEFAULT 0,
                    fail_count     INTEGER DEFAULT 0,
                    avg_fitness    REAL    DEFAULT 0.0,
                    last_updated   REAL    DEFAULT 0.0,
                    total_attempts INTEGER DEFAULT 0
                );
                
                CREATE TABLE IF NOT EXISTS parameter_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  REAL    NOT NULL,
                    params     TEXT    NOT NULL,
                    reasoning  TEXT    NOT NULL,
                    version    INTEGER NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS anomaly_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  REAL    NOT NULL,
                    anomaly_type TEXT  NOT NULL,
                    description TEXT   NOT NULL,
                    severity   TEXT   NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_meta_cycles_ts ON meta_cycles(ts);
                CREATE INDEX IF NOT EXISTS idx_mutation_stats_rate ON mutation_stats(
                    CAST(success_count AS REAL) / (success_count + fail_count)
                );
            """)
            conn.commit()
    
    def _upsert_mutation_stat(self, mut_type: str, success: bool, fitness: float = 0.0) -> None:
        """Atualiza estatísticas de mutação."""
        with sqlite3.connect(META_DB) as conn:
            conn.execute("""
                INSERT INTO mutation_stats (mutation_type, success_count, fail_count, avg_fitness, last_updated, total_attempts)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(mutation_type) DO UPDATE SET
                    success_count = success_count + excluded.success_count,
                    fail_count = fail_count + excluded.fail_count,
                    avg_fitness = (avg_fitness * (success_count + fail_count) + excluded.avg_fitness * excluded.total_attempts)
                                  / (success_count + fail_count + excluded.total_attempts),
                    last_updated = excluded.last_updated,
                    total_attempts = total_attempts + excluded.total_attempts
            """, (mut_type, 1 if success else 0, 0 if success else 1, fitness, time.time(), 1))
            conn.commit()
    
    def _get_mutation_stats(self) -> Dict[str, Dict[str, Any]]:
        """Recupera estatísticas de todas as mutações."""
        with sqlite3.connect(META_DB) as conn:
            rows = conn.execute("""
                SELECT mutation_type, success_count, fail_count, avg_fitness, total_attempts, last_updated
                FROM mutation_stats
                WHERE (success_count + fail_count) > 0
            """).fetchall()
            
            return {
                row[0]: {
                    "success": row[1],
                    "fail": row[2],
                    "success_rate": row[1] / (row[1] + row[2]) if (row[1] + row[2]) > 0 else 0,
                    "avg_fitness": row[3],
                    "total_attempts": row[4],
                    "last_updated": row[5]
                }
                for row in rows
            }
    
    def _get_best_mutation_type(self) -> Tuple[str, float]:
        """Retorna o melhor tipo de mutação baseado em taxa de sucesso."""
        stats = self._get_mutation_stats()
        if not stats:
            return "", 0.0
        
        best = max(stats.items(), key=lambda x: x[1]["success_rate"])
        return best[0], best[1]["success_rate"]
    
    # ── Data Parsing ──────────────────────────────────────────────────────────
    
    def _parse_organism_memory(self, path: Path, p: EvolutionPattern) -> None:
        """Analisa arquivo digital_organism_memory.jsonl."""
        if not path.exists():
            return
        
        type_ok: Counter = Counter()
        type_all: Counter = Counter()
        fitnesses: List[float] = []
        api_hits: Counter = Counter()
        mutation_outcomes: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
        
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            p.sampled_cycles += 1
            ptype = str(entry.get("build", {}).get("project_type", "unknown"))
            ok = bool(entry.get("execution", {}).get("ok", False))
            fitness = float(entry.get("fitness", entry.get("score", 0.0)))
            mutation_type = str(entry.get("mutation", entry.get("mutation_type", "unknown")))
            
            # Registra fitness para série temporal
            if fitness > 0:
                fitnesses.append(fitness)
                p.fitness_history.append(fitness)
            
            # Contagem por tipo de projeto
            type_all[ptype] += 1
            if ok:
                type_ok[ptype] += 1
                p.successful_mutations += 1
                
                # Registra resultado de mutação
                s, f = mutation_outcomes[mutation_type]
                mutation_outcomes[mutation_type] = (s + 1, f)
            else:
                s, f = mutation_outcomes[mutation_type]
                mutation_outcomes[mutation_type] = (s, f + 1)
            
            p.total_mutations += 1
            
            # Rastreia APIs bem-sucedidas
            for src in entry.get("learning", {}).get("sources", []):
                if src.get("ok"):
                    api_hits[src.get("source", "")] += 1
            
            # Rastreia tipos de erro
            reason = str(entry.get("execution", {}).get("reason", "")).lower()
            if "syntax" in reason or "syntax_error" in reason:
                p.syntax_errors += 1
            if "logic" in reason or "assertion" in reason:
                p.logic_errors += 1
            if "security" in reason or "violation" in reason:
                p.security_violations += 1
            if "timeout" in reason:
                p.timeout_errors += 1
        
        # Calcula taxas de sucesso por mutação
        for mut_type, (s, f) in mutation_outcomes.items():
            total = s + f
            if total >= 3:  # mínimo de amostras para considerar
                p.mutation_success_rates[mut_type] = s / total
        
        # Calcula fitness médio
        if fitnesses:
            p.avg_fitness = round(sum(fitnesses) / len(fitnesses), 2)
        
        # Calcula viés por tipo de projeto
        if type_all:
            p.project_type_bias = {
                t: round(type_ok.get(t, 0) / type_all[t], 3)
                for t in type_all
            }
            best_type = max(type_all, key=lambda t: type_ok.get(t, 0) / type_all[t])
            p.best_mutation_type = best_type
            worst_type = min(type_all, key=lambda t: type_ok.get(t, 0) / type_all[t])
            p.worst_mutation_type = worst_type
        
        # API mais bem-sucedida
        if api_hits:
            most_common = api_hits.most_common(1)[0]
            p.most_successful_api = most_common[0]
            total_api = sum(api_hits.values())
            p.api_success_rate = round(most_common[1] / max(1, total_api), 3)
    
    def _parse_text_logs(self, log_dir: Path, p: EvolutionPattern) -> None:
        """Analisa logs de texto brutos."""
        if not log_dir.exists():
            return
        
        patterns = {
            "syntax_errors": re.compile(r"SyntaxError|syntax error|py_compile falhou|compilation failed", re.I),
            "logic_errors": re.compile(r"AssertionError|logic error|falha lógica|LogicError|ValueError", re.I),
            "security_violations": re.compile(r"security|SecurityViolation|violação.*segurança|forbidden|blocked", re.I),
            "timeout_errors": re.compile(r"TimeoutError|timeout|timed out|Tempo limite", re.I),
        }
        
        for log_file in list(log_dir.glob("*.log"))[:50]:
            try:
                text = log_file.read_text(encoding="utf-8", errors="replace")
                for field_name, rx in patterns.items():
                    count = len(rx.findall(text))
                    setattr(p, field_name, getattr(p, field_name) + count)
            except OSError:
                pass
    
    def _parse_json_reports(self, reports_dir: Path, p: EvolutionPattern) -> None:
        """Analisa relatórios JSON."""
        if not reports_dir.exists():
            return
        
        json_files = list(reports_dir.glob("**/*.json"))[:30]
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
                fitness = float(data.get("best_fitness") or data.get("fitness") or data.get("score", 0.0))
                if fitness > 0:
                    p.total_mutations += 1
                    if fitness > 50:
                        p.successful_mutations += 1
                        p.fitness_history.append(fitness)
            except (json.JSONDecodeError, OSError, ValueError):
                pass
    
    # ── Trend and Anomaly Detection ──────────────────────────────────────────
    
    def _detect_trends(self, p: EvolutionPattern) -> None:
        """Detecta tendências e anomalias nos dados."""
        if len(p.fitness_history) >= 3:
            trend, slope = TimeSeriesAnalyzer.calculate_trend(p.fitness_history)
            p.fitness_trend = trend
            
            # Detecta anomalias
            anomalies = TimeSeriesAnalyzer.detect_anomalies(p.fitness_history)
            if anomalies:
                p.anomaly_detected = True
                p.anomaly_description = f"{len(anomalies)} anomalias detectadas nas últimas {len(p.fitness_history)} medições"
                
                # Log de anomalia
                with sqlite3.connect(META_DB) as conn:
                    conn.execute("""
                        INSERT INTO anomaly_log (timestamp, anomaly_type, description, severity)
                        VALUES (?, ?, ?, ?)
                    """, (time.time(), "fitness_anomaly", p.anomaly_description, "warning"))
                    conn.commit()
    
    def analyze_logs(self, force_refresh: bool = False) -> EvolutionPattern:
        """
        Analisa DADOS REAIS — nunca retorna valores fictícios.
        
        Args:
            force_refresh: Força reanálise mesmo em cache
        """
        # Cache de 60 segundos
        if not force_refresh and self._pattern_cache and (time.time() - self._last_analysis) < self._cache_ttl:
            return self._pattern_cache
        
        pattern = EvolutionPattern()
        
        # 1. digital_organism_memory.jsonl
        memory_file = self.evo_dir / "digital_organism_memory.jsonl"
        if memory_file.exists():
            self._parse_organism_memory(memory_file, pattern)
        
        # 2. Logs de texto
        if self.history_path.exists():
            self._parse_text_logs(self.history_path, pattern)
        
        # 3. JSONs de relatório
        if self.reports_dir.exists():
            self._parse_json_reports(self.reports_dir, pattern)
        
        # 4. Detecção de tendências
        self._detect_trends(pattern)
        
        # 5. Melhor mutação do DB
        best_mut, best_rate = self._get_best_mutation_type()
        if best_mut and (not pattern.best_mutation_type or best_rate > pattern.mutation_success_rates.get(pattern.best_mutation_type, 0)):
            pattern.best_mutation_type = best_mut
        
        # 6. Limpeza de ruído
        if pattern.total_mutations > 0:
            # Remove mutações com poucas amostras
            pattern.mutation_success_rates = {
                k: v for k, v in pattern.mutation_success_rates.items()
                if (pattern.mutation_success_rates.get(k, 0) > 0.1)
            }
        
        logger.info(
            "[MetaLearner] %d ciclos analisados | sintaxe=%d | sucesso=%.0f%% | trend=%s | anomalias=%s",
            pattern.sampled_cycles,
            pattern.syntax_errors,
            (pattern.successful_mutations / max(1, pattern.total_mutations)) * 100,
            pattern.fitness_trend,
            "✅" if not pattern.anomaly_detected else "⚠️"
        )
        
        # Atualiza cache
        self._pattern_cache = pattern
        self._last_analysis = time.time()
        
        return pattern
    
    # ── Parameter Optimization ────────────────────────────────────────────────
    
    def optimize_parameters(self, current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Otimiza parâmetros baseado em análise de dados reais.
        
        Args:
            current_params: Parâmetros atuais do sistema
        
        Returns:
            Parâmetros otimizados com reasoning
        """
        pattern = self.analyze_logs()
        
        params = OptimizedParams(
            temperature=float(current_params.get("temperature", 0.7)),
            security_rigor=str(current_params.get("security_rigor", "NORMAL")).upper(),
            mutation_strength=float(current_params.get("mutation_strength", 0.3)),
            population_size=int(current_params.get("population_size", 5)),
            preferred_strategy=str(current_params.get("preferred_strategy", "")),
            risk_threshold=float(current_params.get("risk_threshold", 0.75)),
            exploration_rate=float(current_params.get("exploration_rate", 0.2)),
            learning_rate=float(current_params.get("learning_rate", 0.1)),
            batch_size=int(current_params.get("batch_size", 32)),
            version=int(current_params.get("version", 1)) + 1
        )
        
        total = max(1, pattern.total_mutations)
        syntax_rate = pattern.syntax_errors / total
        security_rate = pattern.security_violations / total
        timeout_rate = pattern.timeout_errors / total
        success_rate = pattern.successful_mutations / total
        
        # ── Ajustes baseados em erros de sintaxe ──────────────────────────
        if syntax_rate > 0.15:
            params.temperature = round(max(0.1, params.temperature - 0.15), 2)
            params.reasoning.append(f"📉 ↓ temperature para {params.temperature} (syntax_rate={syntax_rate:.2f} > 0.15)")
        elif syntax_rate < 0.03 and pattern.sampled_cycles > 10:
            params.temperature = round(min(0.9, params.temperature + 0.05), 2)
            params.reasoning.append(f"📈 ↑ temperature para {params.temperature} (syntax_rate={syntax_rate:.2f} baixo)")
        
        # ── Ajustes de segurança ──────────────────────────────────────────
        if security_rate > 0.05:
            params.security_rigor = "MAXIMUM"
            params.risk_threshold = round(min(0.95, params.risk_threshold + 0.1), 2)
            params.reasoning.append(f"🔒 security_rigor=MAXIMUM (violações={pattern.security_violations})")
        elif security_rate < 0.01 and pattern.security_violations == 0:
            params.security_rigor = "NORMAL"
            params.reasoning.append(f"🔓 security_rigor=NORMAL (sem violações recentes)")
        
        # ── Ajustes de timeout ────────────────────────────────────────────
        if timeout_rate > 0.10:
            old_strength = params.mutation_strength
            params.mutation_strength = round(max(0.1, params.mutation_strength - 0.1), 2)
            params.reasoning.append(f"⏱️ ↓ mutation_strength de {old_strength} para {params.mutation_strength} (timeouts={pattern.timeout_errors})")
        
        # ── Ajustes baseados em tendência de fitness ──────────────────────
        if pattern.fitness_trend == "melhora":
            if pattern.avg_fitness > 60:
                params.population_size = min(10, params.population_size + 1)
                params.temperature = round(min(0.9, params.temperature + 0.05), 2)
                params.confidence = min(0.95, params.confidence + 0.05)
                params.reasoning.append(f"📈 ↑ population_size={params.population_size} (trend=melhora, fitness={pattern.avg_fitness})")
        elif pattern.fitness_trend == "piora":
            params.population_size = max(3, params.population_size - 1)
            params.exploration_rate = min(0.5, params.exploration_rate + 0.1)
            params.mutation_strength = round(min(0.5, params.mutation_strength + 0.05), 2)
            params.reasoning.append(f"🔄 ↑ exploration_rate={params.exploration_rate} (trend=piora)")
            params.confidence = max(0.3, params.confidence - 0.05)
        
        # ── Ajustes baseados em taxa de sucesso ───────────────────────────
        if success_rate > 0.6:
            params.learning_rate = min(0.3, params.learning_rate + 0.02)
            params.reasoning.append(f"🧠 ↑ learning_rate={params.learning_rate} (success_rate={success_rate:.1%})")
        elif success_rate < 0.3 and pattern.sampled_cycles > 20:
            params.learning_rate = max(0.05, params.learning_rate - 0.02)
            params.exploration_rate = min(0.5, params.exploration_rate + 0.05)
            params.reasoning.append(f"🔍 ↑ exploration_rate={params.exploration_rate} (success_rate={success_rate:.1%})")
        
        # ── Estratégia preferida ──────────────────────────────────────────
        if pattern.best_mutation_type:
            params.preferred_strategy = pattern.best_mutation_type
            params.reasoning.append(f"🎯 preferred_strategy={pattern.best_mutation_type} (success_rate={pattern.mutation_success_rates.get(pattern.best_mutation_type, 0):.1%})")
        
        # ── Detecção de anomalias ─────────────────────────────────────────
        if pattern.anomaly_detected:
            params.exploration_rate = min(0.6, params.exploration_rate + 0.1)
            params.reasoning.append(f"⚠️ Anomalia detectada: {pattern.anomaly_description[:50]}... aumentando exploração")
        
        # Salva histórico de parâmetros
        with sqlite3.connect(META_DB) as conn:
            conn.execute("""
                INSERT INTO parameter_history (timestamp, params, reasoning, version)
                VALUES (?, ?, ?, ?)
            """, (time.time(), json.dumps(params.to_dict()), json.dumps(params.reasoning), params.version))
            conn.commit()
        
        # Salva ciclo de meta-aprendizado
        with sqlite3.connect(META_DB) as conn:
            conn.execute("""
                INSERT INTO meta_cycles (ts, patterns, params, sampled, version)
                VALUES (?, ?, ?, ?, ?)
            """, (time.time(), json.dumps(pattern.to_dict()), json.dumps(params.to_dict()), pattern.sampled_cycles, params.version))
            conn.commit()
        
        result = params.to_dict()
        result["_pattern_summary"] = {
            "sampled_cycles": pattern.sampled_cycles,
            "syntax_error_rate": round(syntax_rate, 4),
            "security_rate": round(security_rate, 4),
            "timeout_rate": round(timeout_rate, 4),
            "success_rate": round(success_rate, 4),
            "avg_fitness": pattern.avg_fitness,
            "fitness_trend": pattern.fitness_trend,
            "most_successful_api": pattern.most_successful_api,
            "api_success_rate": pattern.api_success_rate,
            "anomaly_detected": pattern.anomaly_detected
        }
        
        return result
    
    def record_mutation_result(self, mutation_type: str, success: bool, fitness: float = 0.0) -> None:
        """
        Registra resultado real de uma mutação para aprendizado futuro.
        
        Args:
            mutation_type: Tipo de mutação executada
            success: Se foi bem-sucedida
            fitness: Valor de fitness resultante
        """
        self._upsert_mutation_stat(mutation_type, success, fitness)
        # Invalida cache para próxima análise
        self._pattern_cache = None
        logger.debug(f"[MetaLearner] Registrado: {mutation_type} -> {'✅' if success else '❌'} (fitness={fitness:.2f})")
    
    def get_parameter_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna histórico de parâmetros otimizados."""
        with sqlite3.connect(META_DB) as conn:
            rows = conn.execute("""
                SELECT timestamp, params, reasoning, version
                FROM parameter_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                {
                    "timestamp": row[0],
                    "params": json.loads(row[1]),
                    "reasoning": json.loads(row[2]),
                    "version": row[3]
                }
                for row in rows
            ]
    
    def get_anomaly_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna log de anomalias detectadas."""
        with sqlite3.connect(META_DB) as conn:
            rows = conn.execute("""
                SELECT timestamp, anomaly_type, description, severity
                FROM anomaly_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                {
                    "timestamp": row[0],
                    "type": row[1],
                    "description": row[2],
                    "severity": row[3]
                }
                for row in rows
            ]
    
    def generate_reflection_report(self) -> str:
        """Gera relatório detalhado de autorreflexão."""
        pattern = self.analyze_logs()
        total = max(1, pattern.total_mutations)
        success_pct = round(pattern.successful_mutations / total * 100, 1)
        syntax_rate = round(pattern.syntax_errors / total * 100, 1)
        security_rate = round(pattern.security_violations / total * 100, 1)
        timeout_rate = round(pattern.timeout_errors / total * 100, 1)
        
        # Histórico de parâmetros
        param_history = self.get_parameter_history(5)
        
        report_lines = [
            "# 🔬 Relatório de Autorreflexão — ATENA Ω",
            "",
            f"**Gerado em:** {datetime.now().isoformat()}",
            "",
            "## 📊 Dados Analisados",
            f"- Ciclos amostrados: **{pattern.sampled_cycles}**",
            f"- Total de mutações: **{pattern.total_mutations}**",
            f"- Taxa de sucesso: **{success_pct}%**",
            f"- Fitness médio: **{pattern.avg_fitness:.2f}**",
            f"- Tendência de fitness: **{pattern.fitness_trend.upper()}**",
            "",
            "## 🐛 Padrões de Erro (reais)",
            f"- Erros de sintaxe: **{pattern.syntax_errors}** ({syntax_rate}% das mutações)",
            f"- Erros de lógica: **{pattern.logic_errors}**",
            f"- Violações de segurança: **{pattern.security_violations}** ({security_rate}%)",
            f"- Timeouts: **{pattern.timeout_errors}** ({timeout_rate}%)",
            "",
            "## 💡 Descobertas",
            f"- Melhor tipo de mutação: **{pattern.best_mutation_type or 'N/A'}**",
            f"- Pior tipo de mutação: **{pattern.worst_mutation_type or 'N/A'}**",
            f"- API mais eficaz: **{pattern.most_successful_api or 'N/A'}** (taxa: {pattern.api_success_rate:.1%})",
            "",
            "## 📈 Viés por Tipo de Projeto",
        ]
        
        for proj_type, rate in pattern.project_type_bias.items():
            report_lines.append(f"- `{proj_type}`: {rate:.1%} sucesso")
        
        report_lines.extend([
            "",
            "## 🎯 Top Mutações por Taxa de Sucesso",
        ])
        
        for mut_type, rate in sorted(pattern.mutation_success_rates.items(), key=lambda x: x[1], reverse=True)[:5]:
            report_lines.append(f"- `{mut_type}`: {rate:.1%}")
        
        if pattern.anomaly_detected:
            report_lines.extend([
                "",
                "## ⚠️ Anomalias Detectadas",
                f"- {pattern.anomaly_description}",
            ])
        
        if param_history:
            report_lines.extend([
                "",
                "## 🔄 Evolução de Parâmetros (últimos ajustes)",
            ])
            for ph in param_history[:3]:
                report_lines.append(f"- Versão {ph['version']}: {', '.join(ph['reasoning'][:2])}")
        
        report_lines.extend([
            "",
            "## 🚀 Recomendações",
        ])
        
        # Recomendações baseadas na análise
        if pattern.fitness_trend == "melhora":
            report_lines.append("- ✅ Manter inércia positiva. Continue aplicando mutações de alto desempenho.")
        elif pattern.fitness_trend == "piora":
            report_lines.append("- ⚠️ Tendência de degradação detectada. Considere reverter para versões anteriores ou aumentar exploração.")
        else:
            report_lines.append("- ➡️ Plateau detectado. Explore mutações mais ousadas ou busque conhecimento externo.")
        
        if security_rate > 5:
            report_lines.append("- 🔒 Alertas de segurança elevados. Ative modo MAXIMUM e revise permissões.")
        
        if pattern.most_successful_api:
            report_lines.append(f"- 🌐 Priorize buscas que utilizem {pattern.most_successful_api} para maior taxa de sucesso.")
        
        return "\n".join(report_lines)
    
    def get_metrics_dashboard(self) -> Dict[str, Any]:
        """Retorna métricas agregadas para dashboard."""
        pattern = self.analyze_logs()
        stats = self._get_mutation_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overview": {
                "total_mutations": pattern.total_mutations,
                "success_rate": round(pattern.successful_mutations / max(1, pattern.total_mutations), 4),
                "avg_fitness": pattern.avg_fitness,
                "fitness_trend": pattern.fitness_trend,
                "sampled_cycles": pattern.sampled_cycles,
                "anomaly_detected": pattern.anomaly_detected
            },
            "errors": {
                "syntax": pattern.syntax_errors,
                "logic": pattern.logic_errors,
                "security": pattern.security_violations,
                "timeout": pattern.timeout_errors
            },
            "mutation_stats": stats,
            "best_mutation": pattern.best_mutation_type,
            "best_api": {
                "name": pattern.most_successful_api,
                "success_rate": pattern.api_success_rate
            }
        }


# =============================================================================
# Instância Global e Funções de Conveniência
# =============================================================================

_default_meta_learner: Optional[SelfReflectiveMetaLearner] = None


def get_meta_learner() -> SelfReflectiveMetaLearner:
    """Retorna instância global do meta-learner."""
    global _default_meta_learner
    if _default_meta_learner is None:
        _default_meta_learner = SelfReflectiveMetaLearner()
    return _default_meta_learner


# =============================================================================
# CLI e Demonstração
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Real Meta-Learner v3.0")
    parser.add_argument("--analyze", action="store_true", help="Executa análise completa")
    parser.add_argument("--optimize", action="store_true", help="Otimiza parâmetros")
    parser.add_argument("--report", action="store_true", help="Gera relatório de reflexão")
    parser.add_argument("--dashboard", action="store_true", help="Mostra dashboard de métricas")
    parser.add_argument("--params", type=str, default="{}", help="Parâmetros atuais (JSON)")
    parser.add_argument("--record", type=str, help="Registra resultado de mutação (formato: tipo,sucesso,fitness)")
    
    args = parser.parse_args()
    
    ml = get_meta_learner()
    
    if args.record:
        parts = args.record.split(",")
        if len(parts) >= 2:
            mut_type = parts[0]
            success = parts[1].lower() in ("true", "1", "yes", "success")
            fitness = float(parts[2]) if len(parts) > 2 else 0.0
            ml.record_mutation_result(mut_type, success, fitness)
            print(f"✅ Registrado: {mut_type} -> {'success' if success else 'failure'}")
        return 0
    
    if args.analyze:
        pattern = ml.analyze_logs(force_refresh=True)
        print(json.dumps(pattern.to_dict(), indent=2, default=str))
        return 0
    
    if args.optimize:
        current = json.loads(args.params) if args.params != "{}" else {}
        result = ml.optimize_parameters(current)
        print(json.dumps(result, indent=2, default=str))
        return 0
    
    if args.report:
        print(ml.generate_reflection_report())
        return 0
    
    if args.dashboard:
        print(json.dumps(ml.get_metrics_dashboard(), indent=2, default=str))
        return 0
    
    # Modo interativo
    print("🔬 ATENA Real Meta-Learner v3.0")
    print("=" * 50)
    print(ml.generate_reflection_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
