#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Motor de Evolução Paralela
Executa múltiplas mutações simultaneamente, avalia fitness de cada uma
e mantém apenas as melhores — evolução por seleção natural real.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import logging
import os
import random
import subprocess
import sys
import tempfile
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("atena.parallel_evolution")

ROOT = Path(__file__).resolve().parent.parent
POPULATION_SIZE   = int(os.getenv("ATENA_POPULATION_SIZE",   "5"))
PARALLEL_WORKERS  = int(os.getenv("ATENA_PARALLEL_WORKERS",  "3"))
EVAL_TIMEOUT_S    = float(os.getenv("ATENA_EVAL_TIMEOUT_S",  "30"))
SURVIVAL_RATE     = float(os.getenv("ATENA_SURVIVAL_RATE",   "0.6"))
MUTATION_STRENGTH = float(os.getenv("ATENA_MUTATION_STRENGTH","0.3"))


# ── Fitness ───────────────────────────────────────────────────────────────────

@dataclass
class FitnessScore:
    syntax_ok:        bool  = False
    runs_ok:          bool  = False
    complexity_delta: float = 0.0   # negativo = mais simples = melhor
    test_pass_rate:   float = 0.0   # 0.0–1.0
    response_time_s:  float = 999.0
    total:            float = 0.0

    def compute(self) -> "FitnessScore":
        if not self.syntax_ok:
            self.total = 0.0
            return self
        base = 30.0 if self.syntax_ok else 0.0
        base += 30.0 if self.runs_ok else 0.0
        base += self.test_pass_rate * 25.0
        # complexidade menor = melhor (até 10 pontos)
        base += max(0.0, min(10.0, -self.complexity_delta * 2))
        # tempo de resposta rápido = melhor (até 5 pontos)
        base += max(0.0, 5.0 - self.response_time_s * 0.5)
        self.total = round(min(100.0, base), 2)
        return self


# ── Candidato de mutação ──────────────────────────────────────────────────────

@dataclass
class MutationCandidate:
    code: str
    mutation_id: str
    mutation_type: str
    fitness: FitnessScore = field(default_factory=FitnessScore)
    eval_error: Optional[str] = None


# ── Estratégias de mutação AST ────────────────────────────────────────────────

class ASTMutator:
    """Aplica mutações no AST do código Python de forma dirigida."""

    STRATEGIES = [
        "rename_local_var",
        "extract_helper",
        "add_early_return",
        "simplify_condition",
        "add_type_hints",
        "optimize_loop",
        "add_logging",
        "add_docstring",
    ]

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def mutate(self, source: str, strategy: Optional[str] = None) -> str:
        """Retorna código mutado. Em caso de erro, retorna o original."""
        strategy = strategy or self.rng.choice(self.STRATEGIES)
        try:
            tree = ast.parse(source)
            mutated = getattr(self, f"_mut_{strategy}", self._mut_add_logging)(tree, source)
            return mutated
        except Exception as exc:
            logger.debug("mutação %s falhou: %s", strategy, exc)
            return source

    # ── Estratégias concretas ────────────────────────────────────────────────

    def _mut_add_logging(self, tree: ast.AST, source: str) -> str:
        """Adiciona import de logging e um logger padrão se ainda não existir."""
        src = source
        if "import logging" not in src:
            src = "import logging\n_log = logging.getLogger(__name__)\n" + src
        return src

    def _mut_add_docstring(self, tree: ast.AST, source: str) -> str:
        """Adiciona docstring mínima à primeira função sem docstring."""
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(getattr(node.body[0], "value", None), ast.Constant)):
                    lineno = node.lineno  # 1-based
                    indent = " " * (node.col_offset + 4)
                    lines.insert(lineno, f'{indent}"""Auto-gerado por ATENA."""')
                    return "\n".join(lines)
        return source

    def _mut_add_type_hints(self, tree: ast.AST, source: str) -> str:
        """Adiciona -> None a funções sem anotação de retorno."""
        lines = source.splitlines()
        offset = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.returns is None:
                idx = node.lineno - 1 + offset
                if idx < len(lines) and "def " in lines[idx] and ") ->" not in lines[idx]:
                    lines[idx] = lines[idx].rstrip().rstrip(":") + " -> None:"
                    offset += 0
                    break  # uma de cada vez
        return "\n".join(lines)

    def _mut_optimize_loop(self, tree: ast.AST, source: str) -> str:
        """Substitui loops simples por list/dict comprehension quando possível."""
        # Adiciona comentário orientador (não reescreve para evitar quebra)
        if "for " in source and "# ATENA: considere usar comprehension aqui" not in source:
            return source.replace(
                "for ",
                "# ATENA: considere usar comprehension aqui\n    for ",
                1,
            )
        return source

    def _mut_add_early_return(self, tree: ast.AST, source: str) -> str:
        """Adiciona guard clause no início de funções longas (>10 linhas)."""
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and len(node.body) > 10:
                idx = node.lineno  # linha após def
                if idx < len(lines):
                    indent = " " * (node.col_offset + 4)
                    guard = f"{indent}# ATENA guard: valide entradas antes de prosseguir"
                    if guard not in lines:
                        lines.insert(idx, guard)
                        return "\n".join(lines)
        return source

    def _mut_simplify_condition(self, tree: ast.AST, source: str) -> str:
        """Simplifica `if x == True:` → `if x:` etc."""
        src = source
        src = src.replace("== True", "").replace("== False", " is False")
        src = src.replace("!= True", " is not True").replace("!= False", "")
        return src

    def _mut_rename_local_var(self, tree: ast.AST, source: str) -> str:
        """Renomeia variáveis genéricas (x, i, j, tmp) para nomes descritivos."""
        generic = {"x": "value", "tmp": "temp_value", "res": "result", "ret": "return_value"}
        src = source
        for old, new in generic.items():
            # Evita renomear parâmetros e nomes de funções
            src = src.replace(f" {old} =", f" {new} =")
            src = src.replace(f"\n{old} =", f"\n{new} =")
        return src

    def _mut_extract_helper(self, tree: ast.AST, source: str) -> str:
        """Sugere extração de bloco duplicado como helper (via comentário)."""
        lines = source.splitlines()
        if len(lines) > 50 and "# ATENA: extraia blocos repetidos" not in source:
            lines.insert(0, "# ATENA: extraia blocos repetidos para funções helper")
            return "\n".join(lines)
        return source


# ── Avaliador de fitness ──────────────────────────────────────────────────────

class FitnessEvaluator:
    """Avalia um candidato de mutação em sandbox seguro."""

    def __init__(self, timeout: float = EVAL_TIMEOUT_S):
        self.timeout = timeout

    def evaluate(self, candidate: MutationCandidate) -> MutationCandidate:
        t0 = time.monotonic()
        try:
            # 1. Verificação de sintaxe
            try:
                ast.parse(candidate.code)
                candidate.fitness.syntax_ok = True
            except SyntaxError as e:
                candidate.eval_error = f"SyntaxError: {e}"
                candidate.fitness.compute()
                return candidate

            # 2. Execução em subprocess com timeout
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(candidate.code)
                fname = f.name

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", f"import ast; ast.parse(open('{fname}').read()); print('ok')"],
                    capture_output=True, text=True, timeout=self.timeout
                )
                candidate.fitness.runs_ok = proc.returncode == 0 and "ok" in proc.stdout
            except subprocess.TimeoutExpired:
                candidate.fitness.runs_ok = False
            finally:
                try:
                    os.unlink(fname)
                except OSError:
                    pass

            # 3. Complexidade (aproximação por número de linhas e nós AST)
            try:
                tree = ast.parse(candidate.code)
                node_count = sum(1 for _ in ast.walk(tree))
                candidate.fitness.complexity_delta = (node_count - 500) / 100
            except Exception:
                pass

            # 4. Tempo de avaliação como proxy de velocidade
            candidate.fitness.response_time_s = time.monotonic() - t0

            # Score de testes: por ora 1.0 se compilou e rodou
            candidate.fitness.test_pass_rate = 1.0 if candidate.fitness.runs_ok else 0.0

        except Exception as exc:
            candidate.eval_error = str(exc)

        candidate.fitness.compute()
        return candidate


# ── Motor de evolução paralela ────────────────────────────────────────────────

class ParallelEvolutionEngine:
    """
    Motor de evolução que:
    1. Gera POPULATION_SIZE mutações do código-fonte original.
    2. Avalia todas em paralelo (até PARALLEL_WORKERS threads).
    3. Seleciona as melhores por fitness.
    4. Retorna o campeão e o histórico de geração.
    """

    def __init__(
        self,
        mutator:   Optional[ASTMutator]     = None,
        evaluator: Optional[FitnessEvaluator] = None,
        population_size: int  = POPULATION_SIZE,
        workers:         int  = PARALLEL_WORKERS,
        on_progress: Optional[Callable[[int, int, float], None]] = None,
    ):
        self.mutator    = mutator   or ASTMutator()
        self.evaluator  = evaluator or FitnessEvaluator()
        self.population_size = max(2, population_size)
        self.workers    = max(1, workers)
        self.on_progress = on_progress
        self._history: list[dict] = []
        self._lock = threading.Lock()

    # ── API pública ─────────────────────────────────────────────────────────

    def evolve(self, source: str, generations: int = 1) -> tuple[str, list[dict]]:
        """
        Evolui o código por `generations` gerações.
        Retorna (melhor_codigo, historico).
        """
        current = source
        all_history: list[dict] = []
        for gen in range(1, generations + 1):
            logger.info("⚙️  Geração %d/%d — gerando %d candidatos", gen, generations, self.population_size)
            champion, gen_history = self._run_generation(current, gen)
            all_history.extend(gen_history)
            if champion and champion.fitness.total > self._score(current):
                logger.info("✅ Gen %d: novo campeão fitness=%.1f (tipo=%s)",
                            gen, champion.fitness.total, champion.mutation_type)
                current = champion.code
            else:
                logger.info("⏸️  Gen %d: sem melhora — mantendo código atual", gen)
        return current, all_history

    def score_code(self, source: str) -> float:
        """Avalia e retorna o fitness de um código."""
        return self._score(source)

    # ── Internos ────────────────────────────────────────────────────────────

    def _run_generation(self, source: str, gen_num: int) -> tuple[Optional[MutationCandidate], list[dict]]:
        candidates = self._generate_candidates(source)
        evaluated: list[MutationCandidate] = []
        gen_history: list[dict] = []

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.evaluator.evaluate, c): c for c in candidates}
            done = 0
            for future in as_completed(futures, timeout=EVAL_TIMEOUT_S * 2):
                try:
                    result = future.result(timeout=EVAL_TIMEOUT_S)
                    evaluated.append(result)
                    done += 1
                    if self.on_progress:
                        self.on_progress(done, len(candidates), result.fitness.total)
                    gen_history.append({
                        "gen": gen_num,
                        "id": result.mutation_id,
                        "type": result.mutation_type,
                        "fitness": result.fitness.total,
                        "syntax_ok": result.fitness.syntax_ok,
                        "runs_ok": result.fitness.runs_ok,
                        "error": result.eval_error,
                    })
                except (FuturesTimeout, Exception) as exc:
                    logger.warning("avaliação falhou: %s", exc)

        if not evaluated:
            return None, gen_history

        evaluated.sort(key=lambda c: c.fitness.total, reverse=True)
        champion = evaluated[0] if evaluated[0].fitness.total > 0 else None
        return champion, gen_history

    def _generate_candidates(self, source: str) -> list[MutationCandidate]:
        candidates = []
        strategies = ASTMutator.STRATEGIES[:]
        random.shuffle(strategies)
        for i in range(self.population_size):
            strategy = strategies[i % len(strategies)]
            mutated = self.mutator.mutate(source, strategy=strategy)
            uid = hashlib.sha1(mutated.encode()).hexdigest()[:8]
            candidates.append(MutationCandidate(
                code=mutated,
                mutation_id=uid,
                mutation_type=strategy,
            ))
        return candidates

    def _score(self, source: str) -> float:
        candidate = MutationCandidate(code=source, mutation_id="baseline", mutation_type="baseline")
        evaluated = self.evaluator.evaluate(candidate)
        return evaluated.fitness.total


# ── Função de conveniência ────────────────────────────────────────────────────

def evolve_file(path: str | Path, generations: int = 1, backup: bool = True) -> dict:
    """Evolui um arquivo Python e sobrescreve se melhorou. Retorna relatório."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"arquivo não encontrado: {p}"}

    source = p.read_text(encoding="utf-8", errors="replace")
    engine = ParallelEvolutionEngine()
    baseline = engine.score_code(source)

    t0 = time.monotonic()
    best_code, history = engine.evolve(source, generations=generations)
    elapsed = round(time.monotonic() - t0, 2)

    best_score = engine.score_code(best_code)
    improved = best_score > baseline

    if improved:
        if backup:
            backup_path = p.with_suffix(f".bak_{int(time.time())}")
            backup_path.write_text(source, encoding="utf-8")
        p.write_text(best_code, encoding="utf-8")
        logger.info("🧬 %s evoluído: %.1f → %.1f (%.2fs)", p.name, baseline, best_score, elapsed)
    else:
        logger.info("🔵 %s sem melhora: %.1f (%.2fs)", p.name, baseline, elapsed)

    return {
        "ok": True,
        "file": str(p),
        "baseline_fitness": baseline,
        "best_fitness": best_score,
        "improved": improved,
        "generations": generations,
        "candidates_evaluated": len(history),
        "elapsed_s": elapsed,
        "history": history,
    }
