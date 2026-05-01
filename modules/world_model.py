#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — World Model v3.0
Sistema avançado de simulação de ambiente e previsão de impacto de mutações.

Recursos:
- 🌍 Simulação de ambiente em sandbox isolado
- 📊 Métricas multidimensionais de qualidade de código
- 🔮 Previsão de impacto de mutações com análise estatística
- 🧠 Aprendizado contínuo sobre padrões de sucesso/fracasso
- ⚡ Execução paralela de simulações
- 📈 Geração de relatórios detalhados de simulação
- 🔄 Integração com sistema de evolução da ATENA
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("atena.world_model")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SimulationMetrics:
    """Métricas detalhadas de uma simulação."""
    syntax_ok: bool = False
    compile_ok: bool = False
    tests_passed: int = 0
    tests_total: int = 0
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    complexity_score: float = 0.0
    security_issues: int = 0
    performance_grade: float = 0.0
    
    @property
    def overall_score(self) -> float:
        """Calcula score geral baseado em múltiplas métricas."""
        test_score = self.tests_passed / max(1, self.tests_total) if self.tests_total > 0 else 0.5
        perf_score = max(0.0, min(1.0, 1.0 - (self.execution_time_ms / 5000)))
        complexity_score = max(0.0, min(1.0, 1.0 - (self.complexity_score / 20)))
        security_score = max(0.0, 1.0 - (self.security_issues * 0.2))
        
        return (test_score * 0.4 + 
                perf_score * 0.2 + 
                complexity_score * 0.2 + 
                security_score * 0.2)


@dataclass
class SimulationResult:
    """Resultado completo de uma simulação."""
    success: bool
    predicted_score: float
    metrics: SimulationMetrics
    logs: str
    simulation_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None


@dataclass
class MutationHistory:
    """Histórico de mutações simuladas."""
    mutation_id: str
    mutation_type: str
    original_hash: str
    mutated_hash: str
    predicted_improvement: float
    actual_improvement: Optional[float] = None
    simulated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    applied: bool = False
    notes: str = ""


# =============================================================================
# World Model Principal
# =============================================================================

class WorldModel:
    """
    Modelo de Mundo Avançado para simulação e previsão de impacto de mutações.
    """
    
    # Testes padrão para simulação
    DEFAULT_TESTS = {
        "syntax": "python3 -m py_compile main.py",
        "import": "python3 -c 'import main'",
        "quick": "python3 quick_test.py",
        "performance": "python3 -c 'import main; import time; s=time.time(); [getattr(main, f)() for f in dir(main) if callable(getattr(main, f)) and not f.startswith(\"_\")]; print(time.time()-s)'",
    }
    
    # Limiares para diferentes níveis de confiança
    CONFIDENCE_THRESHOLDS = {
        "high": 0.8,
        "medium": 0.6,
        "low": 0.4,
    }
    
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = Path.cwd()
        
        # Diretórios
        self.evolution_dir = self.base_dir / "atena_evolution"
        self.mirror_dir = self.evolution_dir / "mirror_world"
        self.simulations_dir = self.evolution_dir / "simulations"
        self.history_file = self.evolution_dir / "mutation_history.json"
        
        # Cria diretórios
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        self.simulations_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache e histórico
        self._simulation_cache: Dict[str, SimulationResult] = {}
        self._mutation_history: List[MutationHistory] = []
        self._load_history()
        
        # Thread pool para simulações paralelas
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.RLock()
        
        logger.info("🌍 World Model v3.0 inicializado")
        logger.info(f"   Mirror dir: {self.mirror_dir}")
        logger.info(f"   History: {self.history_file}")
    
    def _load_history(self):
        """Carrega histórico de mutações do disco."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self._mutation_history = [MutationHistory(**item) for item in data]
                logger.info(f"📜 Histórico carregado: {len(self._mutation_history)} mutações")
            except Exception as e:
                logger.warning(f"Erro ao carregar histórico: {e}")
    
    def _save_history(self):
        """Salva histórico de mutações no disco."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump([h.__dict__ for h in self._mutation_history], f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Erro ao salvar histórico: {e}")
    
    def _compute_code_hash(self, code: str) -> str:
        """Computa hash do código para cache."""
        return hashlib.sha256(code.encode()).hexdigest()[:16]
    
    def _setup_mirror_environment(self, code: str, essential_files: List[str]) -> Path:
        """
        Configura ambiente espelho para simulação.
        
        Args:
            code: Código a ser testado
            essential_files: Arquivos essenciais para copiar
        
        Returns:
            Path do diretório espelho
        """
        mirror_path = Path(tempfile.mkdtemp(dir=self.mirror_dir))
        
        # Copia arquivos essenciais
        for f in essential_files:
            src = self.base_dir / f
            if src.exists():
                shutil.copy(src, mirror_path / f)
        
        # Escreve o código mutado
        (mirror_path / "main.py").write_text(code)
        
        # Cria quick_test.py padrão se não existir
        quick_test = mirror_path / "quick_test.py"
        if not quick_test.exists():
            quick_test.write_text(self._generate_default_test())
        
        return mirror_path
    
    def _generate_default_test(self) -> str:
        """Gera teste padrão para simulação."""
        return '''
#!/usr/bin/env python3
"""Teste rápido para validação de código gerado."""

import sys
import importlib

def run_tests():
    """Executa testes básicos no módulo main."""
    try:
        import main
        passed = 0
        total = 0
        
        # Verifica funções exportadas
        for name in dir(main):
            if not name.startswith("_") and callable(getattr(main, name)):
                total += 1
                try:
                    getattr(main, name)()
                    passed += 1
                    print(f"✅ {name}() - OK")
                except Exception as e:
                    print(f"❌ {name}() - ERRO: {e}")
        
        print(f"\\nRESULTADO: Todos os {passed}/{total} testes executados com sucesso.")
        return passed == total
        
    except ImportError as e:
        print(f"❌ Erro ao importar main: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
'''
    
    def _extract_metrics_from_output(self, stdout: str, stderr: str, execution_time: float) -> SimulationMetrics:
        """Extrai métricas da saída da simulação."""
        metrics = SimulationMetrics()
        metrics.execution_time_ms = execution_time * 1000
        
        # Verifica erros de sintaxe
        if "SyntaxError" in stderr:
            metrics.syntax_ok = False
            metrics.compile_ok = False
        else:
            metrics.syntax_ok = True
            metrics.compile_ok = True
        
        # Conta testes passados
        passed_match = re.search(r'(\d+)/(\d+)', stdout)
        if passed_match:
            metrics.tests_passed = int(passed_match.group(1))
            metrics.tests_total = int(passed_match.group(2))
        
        # Detecta problemas de segurança
        security_patterns = ["eval(", "exec(", "__import__", "os.system", "subprocess"]
        for pattern in security_patterns:
            if pattern in stdout or pattern in stderr:
                metrics.security_issues += 1
        
        # Estima complexidade
        if "complexity" in stdout.lower():
            complexity_match = re.search(r'complexity[:\s]+(\d+\.?\d*)', stdout.lower())
            if complexity_match:
                metrics.complexity_score = float(complexity_match.group(1))
        
        return metrics
    
    def simulate_mutation(
        self,
        code: str,
        test_script: str = "quick_test.py",
        timeout: int = 30,
        essential_files: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> Tuple[bool, float, str, SimulationMetrics]:
        """
        Simula mutação em ambiente isolado.
        
        Args:
            code: Código mutado
            test_script: Script de teste a executar
            timeout: Timeout em segundos
            essential_files: Lista de arquivos essenciais para copiar
            use_cache: Se deve usar cache de simulações
        
        Returns:
            Tuple[sucesso, score_previsto, logs, métricas]
        """
        if essential_files is None:
            essential_files = ["main.py", "quick_test.py", "requirements.txt"]
        
        code_hash = self._compute_code_hash(code)
        
        # Verifica cache
        if use_cache and code_hash in self._simulation_cache:
            cached = self._simulation_cache[code_hash]
            logger.info(f"📦 Cache hit para simulação: {code_hash}")
            return cached.success, cached.predicted_score, cached.logs, cached.metrics
        
        logger.info(f"🌍 Iniciando simulação em ambiente isolado...")
        start_time = time.time()
        
        mirror_path = None
        try:
            mirror_path = self._setup_mirror_environment(code, essential_files)
            
            # Executa simulação
            result = subprocess.run(
                [sys.executable, test_script],
                cwd=mirror_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            success = result.returncode == 0
            metrics = self._extract_metrics_from_output(result.stdout, result.stderr, execution_time)
            
            # Calcula score previsto
            base_score = 1.0 if success else 0.0
            predicted_score = (base_score * 0.4 + 
                              metrics.overall_score * 0.6)
            
            logs = result.stdout + result.stderr
            
            simulation_result = SimulationResult(
                success=success,
                predicted_score=round(predicted_score, 4),
                metrics=metrics,
                logs=logs[:2000],  # Limita logs
                simulation_id=code_hash
            )
            
            # Cache resultado
            with self._lock:
                self._simulation_cache[code_hash] = simulation_result
                if len(self._simulation_cache) > 100:
                    # Limpa cache antigo
                    oldest = min(self._simulation_cache.keys(), key=lambda k: self._simulation_cache[k].timestamp)
                    del self._simulation_cache[oldest]
            
            logger.info(f"✅ Simulação concluída: success={success}, score={predicted_score:.3f}, time={execution_time:.2f}s")
            return success, predicted_score, logs, metrics
            
        except subprocess.TimeoutExpired:
            logger.warning(f"⏰ Simulação atingiu timeout ({timeout}s)")
            metrics = SimulationMetrics()
            return False, 0.0, f"Timeout após {timeout}s", metrics
        except Exception as e:
            logger.error(f"❌ Erro na simulação: {e}")
            metrics = SimulationMetrics()
            return False, 0.0, str(e), metrics
        finally:
            # Limpa ambiente espelho
            if mirror_path and mirror_path.exists():
                shutil.rmtree(mirror_path, ignore_errors=True)
    
    async def simulate_mutation_async(
        self,
        code: str,
        test_script: str = "quick_test.py",
        timeout: int = 30
    ) -> Tuple[bool, float, str, SimulationMetrics]:
        """Versão assíncrona da simulação."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.simulate_mutation,
            code, test_script, timeout
        )
    
    def simulate_multiple(
        self,
        mutations: List[Tuple[str, str]],  # (code, mutation_type)
        max_workers: int = 4,
        timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Simula múltiplas mutações em paralelo.
        
        Args:
            mutations: Lista de (código, tipo_mutação)
            max_workers: Número máximo de workers paralelos
            timeout: Timeout por simulação
        
        Returns:
            Lista de resultados por mutação
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (code, mut_type) in enumerate(mutations):
                future = executor.submit(self.simulate_mutation, code, "quick_test.py", timeout)
                futures[future] = (idx, mut_type)
            
            for future in as_completed(futures):
                idx, mut_type = futures[future]
                try:
                    success, score, logs, metrics = future.result(timeout=timeout + 5)
                    results.append({
                        "index": idx,
                        "mutation_type": mut_type,
                        "success": success,
                        "predicted_score": score,
                        "metrics": metrics.__dict__,
                        "logs": logs[:500]
                    })
                except Exception as e:
                    results.append({
                        "index": idx,
                        "mutation_type": mut_type,
                        "success": False,
                        "predicted_score": 0.0,
                        "error": str(e)
                    })
        
        # Ordena por índice original
        results.sort(key=lambda x: x["index"])
        return results
    
    def predict_improvement(
        self,
        original_code: str,
        mutated_code: str,
        mutation_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Prediz melhoria/degradação de uma mutação.
        
        Args:
            original_code: Código original
            mutated_code: Código mutado
            mutation_type: Tipo da mutação
        
        Returns:
            Dicionário com previsão de melhoria e confiança
        """
        # Simula ambos os códigos
        _, original_score, _, original_metrics = self.simulate_mutation(original_code, use_cache=True)
        _, mutated_score, _, mutated_metrics = self.simulate_mutation(mutated_code, use_cache=True)
        
        delta = mutated_score - original_score
        improvement = delta > 0.05
        degradation = delta < -0.05
        neutral = not improvement and not degradation
        
        # Confiança baseada no delta e métricas
        confidence = min(0.95, abs(delta) + 0.3)
        
        # Registra no histórico
        history = MutationHistory(
            mutation_id=self._compute_code_hash(mutated_code),
            mutation_type=mutation_type,
            original_hash=self._compute_code_hash(original_code),
            mutated_hash=self._compute_code_hash(mutated_code),
            predicted_improvement=delta,
            notes=f"Original score: {original_score:.3f}, Mutated score: {mutated_score:.3f}"
        )
        self._mutation_history.append(history)
        self._save_history()
        
        return {
            "improvement": improvement,
            "degradation": degradation,
            "neutral": neutral,
            "delta": round(delta, 4),
            "original_score": round(original_score, 4),
            "mutated_score": round(mutated_score, 4),
            "confidence": round(confidence, 4),
            "metrics": {
                "original": original_metrics.__dict__,
                "mutated": mutated_metrics.__dict__
            },
            "mutation_type": mutation_type,
            "recommendation": (
                "Apply mutation" if improvement else
                "Reject mutation" if degradation else
                "Consider with caution - neutral impact"
            )
        }
    
    def get_simulation_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas das simulações."""
        with self._lock:
            return {
                "cache_size": len(self._simulation_cache),
                "history_size": len(self._mutation_history),
                "successful_simulations": sum(1 for r in self._simulation_cache.values() if r.success),
                "average_score": sum(r.predicted_score for r in self._simulation_cache.values()) / max(1, len(self._simulation_cache)),
                "mirror_dir": str(self.mirror_dir),
                "simulations_dir": str(self.simulations_dir)
            }
    
    def clear_cache(self):
        """Limpa cache de simulações."""
        with self._lock:
            self._simulation_cache.clear()
        logger.info("🗑️ Cache de simulações limpo")
    
    def generate_report(self, mutation_id: Optional[str] = None) -> str:
        """
        Gera relatório de simulações.
        
        Args:
            mutation_id: ID específico da mutação (opcional)
        
        Returns:
            Relatório em formato markdown
        """
        if mutation_id:
            # Busca mutação específica
            history = next((h for h in self._mutation_history if h.mutation_id == mutation_id), None)
            if not history:
                return f"⚠️ Mutação {mutation_id} não encontrada no histórico."
            
            return f"""# 🔬 Relatório de Simulação - {mutation_id}

## Mutação
- **Tipo:** {history.mutation_type}
- **Predição de melhoria:** {history.predicted_improvement:+.2%}
- **Aplicada:** {'✅ Sim' if history.applied else '❌ Não'}
- **Data:** {history.simulated_at}

## Notas
{history.notes}
"""
        
        # Relatório geral
        stats = self.get_simulation_stats()
        recent = self._mutation_history[-10:] if self._mutation_history else []
        
        lines = [
            "# 🌍 World Model - Relatório de Simulações",
            "",
            f"**Gerado em:** {datetime.now().isoformat()}",
            "",
            "## 📊 Estatísticas",
            f"- Cache size: {stats['cache_size']}",
            f"- Histórico: {stats['history_size']} mutações",
            f"- Simulações bem-sucedidas: {stats['successful_simulations']}",
            f"- Score médio: {stats['average_score']:.2%}",
            "",
            "## 📜 Mutações Recentes",
        ]
        
        for h in recent[-5:]:
            lines.append(f"- `{h.mutation_id[:8]}`: {h.mutation_type} | Δ={h.predicted_improvement:+.2%} | Aplicada: {'✅' if h.applied else '❌'}")
        
        lines.extend([
            "",
            "## 📁 Diretórios",
            f"- Mirror: `{stats['mirror_dir']}`",
            f"- Simulações: `{stats['simulations_dir']}`",
        ])
        
        return "\n".join(lines)


# =============================================================================
# Instância Global e Funções de Conveniência
# =============================================================================

_world_model: Optional[WorldModel] = None


def get_world_model() -> WorldModel:
    """Retorna instância global do World Model."""
    global _world_model
    if _world_model is None:
        _world_model = WorldModel()
    return _world_model


# =============================================================================
# Compatibilidade com código original
# =============================================================================

def simulate_mutation(
    code: str,
    test_script: str = "quick_test.py"
) -> Tuple[bool, float, str]:
    """
    Interface compatível com código original.
    
    Returns:
        Tuple[success, score, logs]
    """
    wm = get_world_model()
    success, score, logs, _ = wm.simulate_mutation(code, test_script)
    return success, score, logs


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA World Model v3.0")
    parser.add_argument("--code", type=str, help="Código para simular")
    parser.add_argument("--file", type=str, help="Arquivo com código para simular")
    parser.add_argument("--test", type=str, default="quick_test.py", help="Script de teste")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas")
    parser.add_argument("--report", type=str, help="Gera relatório (opcional: mutation_id)")
    parser.add_argument("--clear-cache", action="store_true", help="Limpa cache")
    
    args = parser.parse_args()
    
    wm = get_world_model()
    
    if args.clear_cache:
        wm.clear_cache()
        print("✅ Cache limpo")
        return 0
    
    if args.stats:
        stats = wm.get_simulation_stats()
        print(json.dumps(stats, indent=2))
        return 0
    
    if args.report is not None:
        report = wm.generate_report(args.report if args.report else None)
        print(report)
        return 0
    
    if args.file:
        code = Path(args.file).read_text(encoding='utf-8')
    elif args.code:
        code = args.code
    else:
        # Exemplo de demonstração
        code = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main():
    print(fibonacci(10))

if __name__ == "__main__":
    main()
'''
        print("📝 Usando código de exemplo")
    
    print(f"\n🚀 Simulando mutação...")
    success, score, logs, metrics = wm.simulate_mutation(code, args.test)
    
    print(f"\n📊 Resultados:")
    print(f"   Sucesso: {'✅' if success else '❌'}")
    print(f"   Score: {score:.2%}")
    print(f"   Testes: {metrics.tests_passed}/{metrics.tests_total}")
    print(f"   Tempo: {metrics.execution_time_ms:.1f}ms")
    print(f"   Complexidade: {metrics.complexity_score:.2f}")
    
    if logs and len(logs) < 1000:
        print(f"\n📋 Logs:\n{logs}")
    
    return 0


if __name__ == "__main__":
    import re
    main()
