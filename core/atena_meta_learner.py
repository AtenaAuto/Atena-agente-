#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Meta-Learner Real
Analisa DADOS REAIS de logs, evolução e histórico para otimizar parâmetros.
Substitui a versão fake que retornava valores hardcodados.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("atena.meta_learner")

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_DIR  = ROOT / "evolution"
LOGS_DIR       = EVOLUTION_DIR / "logs"
EVO_DIR        = ROOT / "atena_evolution"
REPORTS_DIR    = ROOT / "analysis_reports"
META_DB        = EVOLUTION_DIR / "meta_learner.db"


@dataclass
class EvolutionPattern:
    """Padrão extraído de ciclos reais de evolução."""
    syntax_errors:       int   = 0
    logic_errors:        int   = 0
    security_violations: int   = 0
    timeout_errors:      int   = 0
    total_mutations:     int   = 0
    successful_mutations:int   = 0
    best_mutation_type:  str   = ""
    worst_mutation_type: str   = ""
    avg_fitness:         float = 0.0
    fitness_trend:       str   = "sem_dados"
    most_successful_api: str   = ""
    api_success_rate:    float = 0.0
    project_type_bias:   dict  = field(default_factory=dict)
    sampled_cycles:      int   = 0


@dataclass
class OptimizedParams:
    temperature:       float = 0.7
    security_rigor:    str   = "NORMAL"
    mutation_strength: float = 0.3
    population_size:   int   = 5
    preferred_strategy:str   = ""
    risk_threshold:    float = 0.75
    reasoning:         list  = field(default_factory=list)


class SelfReflectiveMetaLearner:
    """
    Meta-learner que lê dados reais de:
    - digital_organism_memory.jsonl  (ciclos de vida)
    - evolution/logs/*.log           (logs de texto)
    - analysis_reports/*.json        (relatórios JSON)
    - meta_learner.db                (histórico próprio)
    """

    def __init__(self, history_path: str | None = None):
        self.history_path = Path(history_path) if history_path else LOGS_DIR
        META_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── DB ───────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(META_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta_cycles (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         REAL    NOT NULL,
                    patterns   TEXT    NOT NULL,
                    params     TEXT    NOT NULL,
                    sampled    INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mutation_stats (
                    mutation_type  TEXT PRIMARY KEY,
                    success_count  INTEGER DEFAULT 0,
                    fail_count     INTEGER DEFAULT 0,
                    avg_fitness    REAL    DEFAULT 0.0,
                    last_updated   REAL    DEFAULT 0.0
                )
            """)
            conn.commit()

    def _upsert_mutation_stat(self, mut_type: str, success: bool, fitness: float) -> None:
        with sqlite3.connect(META_DB) as conn:
            conn.execute("""
                INSERT INTO mutation_stats (mutation_type, success_count, fail_count, avg_fitness, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mutation_type) DO UPDATE SET
                    success_count = success_count + excluded.success_count,
                    fail_count    = fail_count    + excluded.fail_count,
                    avg_fitness   = (avg_fitness * (success_count + fail_count) + excluded.avg_fitness)
                                    / (success_count + fail_count + 1),
                    last_updated  = excluded.last_updated
            """, (mut_type, 1 if success else 0, 0 if success else 1, fitness, time.time()))
            conn.commit()

    def _best_mutation_type_from_db(self) -> str:
        with sqlite3.connect(META_DB) as conn:
            cur = conn.execute("""
                SELECT mutation_type
                FROM mutation_stats
                WHERE (success_count + fail_count) > 0
                ORDER BY (CAST(success_count AS REAL) / (success_count + fail_count)) DESC
                LIMIT 1
            """)
            row = cur.fetchone()
        return row[0] if row else ""

    # ── Análise de dados reais ───────────────────────────────────────────────

    def analyze_logs(self) -> EvolutionPattern:
        """Analisa DADOS REAIS — nunca retorna valores fictícios."""
        pattern = EvolutionPattern()

        # 1. digital_organism_memory.jsonl
        memory_file = EVO_DIR / "digital_organism_memory.jsonl"
        if memory_file.exists():
            self._parse_organism_memory(memory_file, pattern)

        # 2. Logs de texto em evolution/logs/
        if self.history_path.exists():
            self._parse_text_logs(self.history_path, pattern)

        # 3. JSONs de relatório em analysis_reports/
        if REPORTS_DIR.exists():
            self._parse_json_reports(REPORTS_DIR, pattern)

        # 4. Histórico do próprio meta-learner
        pattern.best_mutation_type = self._best_mutation_type_from_db() or pattern.best_mutation_type

        if pattern.total_mutations > 0:
            rate = pattern.successful_mutations / pattern.total_mutations
            pattern.fitness_trend = (
                "melhora" if rate > 0.6 else
                "piora"   if rate < 0.3 else
                "estavel"
            )

        logger.info(
            "[MetaLearner] %d ciclos analisados | sintaxe=%d | sucesso=%.0f%% | trend=%s",
            pattern.sampled_cycles,
            pattern.syntax_errors,
            (pattern.successful_mutations / max(1, pattern.total_mutations)) * 100,
            pattern.fitness_trend,
        )
        return pattern

    def _parse_organism_memory(self, path: Path, p: EvolutionPattern) -> None:
        type_ok:  Counter = Counter()
        type_all: Counter = Counter()
        fitnesses: list[float] = []
        api_hits:  Counter = Counter()

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
            ok    = bool(entry.get("execution", {}).get("ok", False))
            fitness = float(entry.get("fitness", 0.0))

            type_all[ptype] += 1
            if ok:
                type_ok[ptype] += 1
                p.successful_mutations += 1
            p.total_mutations += 1

            if fitness > 0:
                fitnesses.append(fitness)

            # API mais usada
            for src in entry.get("learning", {}).get("sources", []):
                if src.get("ok"):
                    api_hits[src.get("source", "")] += 1

            # Rastrear tipos de erro
            reason = str(entry.get("execution", {}).get("reason", "")).lower()
            if "syntax" in reason or "syntax_error" in reason:
                p.syntax_errors += 1
            if "logic" in reason or "assertion" in reason:
                p.logic_errors += 1
            if "timeout" in reason:
                p.timeout_errors += 1

        if fitnesses:
            p.avg_fitness = round(sum(fitnesses) / len(fitnesses), 2)

        if type_all:
            p.project_type_bias = {t: round(type_ok.get(t, 0) / type_all[t], 3) for t in type_all}
            best_type = max(type_all, key=lambda t: type_ok.get(t, 0) / type_all[t])
            p.best_mutation_type = best_type
            worst_type = min(type_all, key=lambda t: type_ok.get(t, 0) / type_all[t])
            p.worst_mutation_type = worst_type

        if api_hits:
            p.most_successful_api = api_hits.most_common(1)[0][0]
            total_api = sum(api_hits.values())
            p.api_success_rate = round(api_hits.most_common(1)[0][1] / max(1, total_api), 3)

    def _parse_text_logs(self, log_dir: Path, p: EvolutionPattern) -> None:
        patterns = {
            "syntax_errors":       re.compile(r"SyntaxError|syntax error|py_compile falhou", re.I),
            "logic_errors":        re.compile(r"AssertionError|logic error|falha lógica|LogicError", re.I),
            "security_violations": re.compile(r"security|SecurityViolation|violação.*segurança", re.I),
            "timeout_errors":      re.compile(r"TimeoutError|timeout|timed out", re.I),
        }
        for log_file in list(log_dir.glob("*.log"))[:30]:
            try:
                text = log_file.read_text(encoding="utf-8", errors="replace")
                for field_name, rx in patterns.items():
                    count = len(rx.findall(text))
                    setattr(p, field_name, getattr(p, field_name) + count)
            except OSError:
                pass

    def _parse_json_reports(self, reports_dir: Path, p: EvolutionPattern) -> None:
        for jf in list(reports_dir.glob("**/*.json"))[:20]:
            try:
                data = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
                fitness = float(data.get("best_fitness") or data.get("fitness") or 0.0)
                if fitness > 0:
                    p.total_mutations += 1
                    if fitness > 50:
                        p.successful_mutations += 1
            except (json.JSONDecodeError, OSError):
                pass

    # ── Otimização ────────────────────────────────────────────────────────────

    def optimize_parameters(self, current_params: dict) -> dict:
        pattern = self.analyze_logs()
        params  = OptimizedParams(
            temperature       = float(current_params.get("temperature",       0.7)),
            security_rigor    = str(current_params.get("security_rigor",    "NORMAL")),
            mutation_strength = float(current_params.get("mutation_strength", 0.3)),
            population_size   = int(current_params.get("population_size",    5)),
            preferred_strategy= str(current_params.get("preferred_strategy", "")),
            risk_threshold    = float(current_params.get("risk_threshold",   0.75)),
        )

        total = max(1, pattern.total_mutations)
        syntax_rate   = pattern.syntax_errors       / total
        security_rate = pattern.security_violations / total
        timeout_rate  = pattern.timeout_errors      / total

        if syntax_rate > 0.15:
            params.temperature = round(max(0.1, params.temperature - 0.15), 2)
            params.reasoning.append(f"↓ temperature {params.temperature} (syntax_rate={syntax_rate:.2f})")

        if security_rate > 0.05:
            params.security_rigor = "MAXIMUM"
            params.risk_threshold = round(min(0.95, params.risk_threshold + 0.1), 2)
            params.reasoning.append(f"🔒 security_rigor=MAXIMUM (violations={pattern.security_violations})")

        if timeout_rate > 0.10:
            params.mutation_strength = round(max(0.1, params.mutation_strength - 0.1), 2)
            params.reasoning.append(f"↓ mutation_strength (timeouts={pattern.timeout_errors})")

        if pattern.fitness_trend == "melhora" and pattern.avg_fitness > 60:
            params.population_size = min(10, params.population_size + 1)
            params.temperature     = round(min(0.9, params.temperature + 0.05), 2)
            params.reasoning.append(f"↑ population_size={params.population_size} (trend=melhora, avg_fitness={pattern.avg_fitness})")

        if pattern.fitness_trend == "piora":
            params.population_size = max(3, params.population_size - 1)
            params.mutation_strength = round(min(0.5, params.mutation_strength + 0.05), 2)
            params.reasoning.append(f"↑ mutation_strength (trend=piora)")

        if pattern.best_mutation_type:
            params.preferred_strategy = pattern.best_mutation_type
            params.reasoning.append(f"→ preferred_strategy={pattern.best_mutation_type}")

        result = asdict(params)
        result["_pattern_summary"] = {
            "sampled_cycles":      pattern.sampled_cycles,
            "syntax_error_rate":   round(syntax_rate,   4),
            "security_rate":       round(security_rate, 4),
            "avg_fitness":         pattern.avg_fitness,
            "fitness_trend":       pattern.fitness_trend,
            "most_successful_api": pattern.most_successful_api,
        }
        return result

    def record_mutation_result(self, mutation_type: str, success: bool, fitness: float = 0.0) -> None:
        """Registra resultado real de uma mutação para aprendizado futuro."""
        self._upsert_mutation_stat(mutation_type, success, fitness)

    def generate_reflection_report(self) -> str:
        pattern = self.analyze_logs()
        total   = max(1, pattern.total_mutations)
        success_pct = round(pattern.successful_mutations / total * 100, 1)

        return f"""# Relatório de Autorreflexão — ATENA Ω
## Dados Analisados
- Ciclos amostrados : {pattern.sampled_cycles}
- Total mutações   : {pattern.total_mutations}
- Taxa de sucesso  : {success_pct}%
- Fitness médio    : {pattern.avg_fitness}
- Tendência        : {pattern.fitness_trend}

## Padrões de Erro (reais)
- Erros de sintaxe       : {pattern.syntax_errors}
- Erros de lógica        : {pattern.logic_errors}
- Violações de segurança : {pattern.security_violations}
- Timeouts               : {pattern.timeout_errors}

## Descobertas
- Melhor tipo de projeto : {pattern.best_mutation_type or 'N/A'}
- Pior tipo de projeto   : {pattern.worst_mutation_type or 'N/A'}
- API mais eficaz        : {pattern.most_successful_api or 'N/A'} ({pattern.api_success_rate:.0%})
- Viés por tipo          : {pattern.project_type_bias}
"""
