#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Module Preloader v2.0 - Pré-carregador Inteligente de Módulos
Prontidão imediata para todos os componentes do ecossistema.

Recursos Aprimorados:
- ⚡ Pré-carregamento paralelo multi-thread
- 🧠 Carregamento inteligente baseado em dependências
- 🔄 Cache de módulos compilados (.pyc)
- 📊 Métricas de performance de carregamento
- 🛡️ Isolamento de falhas com fallback
- 🌐 Pré-carregamento recursivo de submódulos
- 📈 Análise de impacto de memória
"""

from __future__ import annotations

import importlib
import importlib.util
import marshal
import re
import sys
import threading
import time
import types
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

# Configura logging silencioso para pré-carregador
logger = logging.getLogger("ATenaPreloader")
logger.setLevel(logging.WARNING)


@dataclass
class ModuleMetrics:
    """Métricas de carregamento de módulo."""
    name: str
    size_bytes: int = 0
    load_time_ms: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    submodules: List[str] = field(default_factory=list)
    compiled_pyc: bool = False
    loaded_successfully: bool = False
    error: Optional[str] = None


class ModuleDependencyGraph:
    """Gerencia dependências entre módulos para carregamento otimizado."""
    
    def __init__(self):
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
    
    def add_dependency(self, module: str, depends_on: str):
        """Adiciona dependência entre módulos."""
        self.graph[module].add(depends_on)
        self.reverse_graph[depends_on].add(module)
    
    def get_load_order(self) -> List[str]:
        """Retorna ordem de carregamento topológica."""
        visited = set()
        order = []
        
        def dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            for dep in self.graph.get(node, []):
                dfs(dep)
            order.append(node)
        
        for module in list(self.graph.keys()):
            dfs(module)
        
        return order
    
    def get_parallel_groups(self) -> List[List[str]]:
        """Retorna grupos de módulos que podem ser carregados em paralelo."""
        load_order = self.get_load_order()
        groups = []
        loaded = set()
        
        for module in load_order:
            deps_met = all(dep in loaded for dep in self.graph.get(module, []))
            if deps_met and module not in loaded:
                group = [module]
                # Adiciona módulos no mesmo nível
                for other in load_order:
                    if other != module and other not in loaded:
                        other_deps_met = all(dep in loaded for dep in self.graph.get(other, []))
                        if other_deps_met and not self._have_circular_deps(module, other):
                            group.append(other)
                groups.append(group)
                loaded.update(group)
        
        return groups
    
    def _have_circular_deps(self, a: str, b: str) -> bool:
        """Verifica se há dependência circular entre a e b."""
        return a in self.reverse_graph.get(b, set()) or b in self.reverse_graph.get(a, set())


class AtenaModulePreloader:
    """
    Pré-carregador avançado de módulos da ATENA.
    Otimiza tempo de inicialização e gerencia dependências.
    """
    
    def __init__(self, modules_dir: Path, cache_dir: Optional[Path] = None):
        self.modules_dir = Path(modules_dir)
        self.cache_dir = cache_dir or self.modules_dir / "__pycache__"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics: Dict[str, ModuleMetrics] = {}
        self.dep_graph = ModuleDependencyGraph()
        self._loaded_modules: Dict[str, types.ModuleType] = {}
        self._lock = threading.RLock()
        
        # Configurações
        self.max_workers = min(8, (os.cpu_count() or 4) // 2)
        self.use_compiled_cache = True
        self.recursive_preload = True
        self.max_depth = 3
        
        logger.info(f"🔱 AtenaModulePreloader inicializado")
        logger.info(f"   Diretório: {self.modules_dir}")
        logger.info(f"   Workers: {self.max_workers}")
        logger.info(f"   Cache: {self.cache_dir}")
    
    def analyze_module(self, module_path: Path) -> ModuleMetrics:
        """Analisa um módulo sem carregá-lo."""
        metrics = ModuleMetrics(name=module_path.name)
        
        try:
            metrics.size_bytes = module_path.stat().st_size
            code = module_path.read_text(encoding='utf-8', errors='ignore')
            
            # Extrai imports para análise de dependências
            import_pattern = r'^(?:from\s+(\S+)\s+import|import\s+(\S+))'
            for line in code.split('\n'):
                match = re.match(import_pattern, line.strip())
                if match:
                    module = match.group(1) or match.group(2)
                    if module and not module.startswith('.'):
                        metrics.dependencies.append(module.split('.')[0])
            
            # Procura por submódulos
            if self.recursive_preload:
                module_dir = self.modules_dir / module_path.stem
                if module_dir.is_dir():
                    for sub in module_dir.glob("*.py"):
                        if sub.name != "__init__.py":
                            metrics.submodules.append(sub.name)
            
            # Verifica se existe .pyc cacheado
            pyc_path = self.cache_dir / f"{module_path.stem}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
            metrics.compiled_pyc = pyc_path.exists()
            
        except Exception as e:
            metrics.error = str(e)
        
        return metrics
    
    def _safe_module_name(self, path: Path) -> str:
        """Gera nome seguro para o módulo."""
        # Mantém estrutura de diretórios para evitar conflitos
        rel_path = path.relative_to(self.modules_dir.parent) if path.parent != self.modules_dir else path
        parts = list(rel_path.parts)
        parts[-1] = parts[-1].replace('.py', '')
        
        slug = "_".join(re.sub(r"[^a-zA-Z0-9_]", "_", p) for p in parts)
        return f"atena_preload_{slug}"
    
    def preload_module(self, module_path: Path, depth: int = 0) -> Tuple[bool, Optional[str]]:
        """
        Pré-carrega um único módulo.
        
        Returns:
            Tuple[success, error_message]
        """
        if depth > self.max_depth:
            return False, f"Profundidade máxima excedida: {depth}"
        
        module_name = self._safe_module_name(module_path)
        
        with self._lock:
            if module_name in self._loaded_modules:
                return True, None
        
        start_time = time.time()
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Spec inválida para {module_path}")
            
            module = importlib.util.module_from_spec(spec)
            
            # Tenta carregar de cache .pyc se disponível e mais novo
            if self.use_compiled_cache:
                pyc_path = self.cache_dir / f"{module_path.stem}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
                if pyc_path.exists() and pyc_path.stat().st_mtime > module_path.stat().st_mtime:
                    try:
                        with open(pyc_path, 'rb') as f:
                            marshal.load(f)  # Valida o cache
                        spec.loader = None  # Força uso do cache
                    except Exception:
                        pass
            
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            load_time_ms = (time.time() - start_time) * 1000
            
            with self._lock:
                self._loaded_modules[module_name] = module
                metrics = ModuleMetrics(
                    name=module_path.name,
                    size_bytes=module_path.stat().st_size,
                    load_time_ms=load_time_ms,
                    loaded_successfully=True
                )
                self.metrics[module_path.name] = metrics
            
            logger.debug(f"✅ Pré-carregado: {module_path.name} ({load_time_ms:.2f}ms)")
            return True, None
            
        except Exception as e:
            error_msg = str(e)[:200]
            logger.warning(f"❌ Falha ao pré-carregar {module_path.name}: {error_msg}")
            
            with self._lock:
                metrics = ModuleMetrics(
                    name=module_path.name,
                    loaded_successfully=False,
                    error=error_msg
                )
                self.metrics[module_path.name] = metrics
            
            return False, error_msg
    
    def preload_parallel(self, module_paths: List[Path], max_workers: Optional[int] = None) -> Dict[str, Any]:
        """
        Pré-carrega módulos em paralelo.
        
        Args:
            module_paths: Lista de caminhos dos módulos
            max_workers: Número máximo de workers (padrão: self.max_workers)
        
        Returns:
            Dict com resultados do pré-carregamento
        """
        workers = max_workers or self.max_workers
        results = []
        
        def _preload_worker(path: Path) -> Tuple[Path, bool, Optional[str]]:
            success, error = self.preload_module(path)
            return path, success, error
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_preload_worker, path): path for path in module_paths}
            for future in as_completed(futures):
                path, success, error = future.result()
                results.append({
                    "module": path.name,
                    "success": success,
                    "error": error
                })
        
        return {
            "total": len(results),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results
        }
    
    def preload_all(self, recursive: bool = True, analyze_first: bool = True) -> Dict[str, Any]:
        """
        Pré-carrega todos os módulos disponíveis.
        
        Args:
            recursive: Se deve pré-carregar submódulos recursivamente
            analyze_first: Se deve analisar dependências antes do carregamento
        
        Returns:
            Dict com estatísticas completas
        """
        if not self.modules_dir.exists():
            return {
                "status": "error",
                "error": f"Diretório não encontrado: {self.modules_dir}",
                "loaded": [],
                "failed": [],
                "total": 0
            }
        
        start_total = time.time()
        
        # Coleta todos os módulos
        modules = []
        if recursive:
            modules = list(self.modules_dir.rglob("*.py"))
            # Remove __init__.py
            modules = [m for m in modules if m.name != "__init__.py"]
        else:
            modules = list(self.modules_dir.glob("*.py"))
            modules = [m for m in modules if m.name != "__init__.py"]
        
        # Análise prévia de dependências
        if analyze_first:
            logger.info(f"🔍 Analisando {len(modules)} módulos...")
            for module_path in modules:
                metrics = self.analyze_module(module_path)
                self.metrics[module_path.name] = metrics
                
                # Constrói grafo de dependências
                for dep in metrics.dependencies:
                    self.dep_graph.add_dependency(module_path.name, dep)
        
        # Determina ordem de carregamento
        parallel_groups = self.dep_graph.get_parallel_groups()
        if parallel_groups:
            logger.info(f"📊 Ordem otimizada: {len(parallel_groups)} grupos paralelos")
        else:
            # Fallback: carregamento simples
            parallel_groups = [[p.name] for p in modules]
        
        # Carregamento paralelo por grupos
        loaded = []
        failed = []
        
        for group_idx, group in enumerate(parallel_groups):
            logger.debug(f"🔄 Carregando grupo {group_idx + 1}/{len(parallel_groups)} ({len(group)} módulos)")
            
            # Filtra módulos existentes
            group_paths = [m for m in modules if m.name in group]
            if not group_paths:
                continue
            
            result = self.preload_parallel(group_paths)
            loaded.extend([r["module"] for r in result["results"] if r["success"]])
            failed.extend([r["module"] for r in result["results"] if not r["success"]])
        
        # Pré-carregamento recursivo de submódulos detectados
        if recursive:
            submodules_found = []
            for metric in self.metrics.values():
                submodules_found.extend(metric.submodules)
            
            if submodules_found:
                logger.info(f"📦 Detectados {len(submodules_found)} submódulos para pré-carregamento")
                for sub in set(submodules_found):
                    sub_path = self.modules_dir / sub
                    if sub_path.exists():
                        self.preload_module(sub_path, depth=1)
        
        total_time_ms = (time.time() - start_total) * 1000
        
        # Estatísticas de memória
        memory_mb = self._get_memory_usage()
        
        result = {
            "status": "success" if len(failed) == 0 else "partial",
            "total": len(modules),
            "loaded_count": len(loaded),
            "failed_count": len(failed),
            "loaded": loaded[:50],  # Limita para não poluir saída
            "failed": failed,
            "total_time_ms": round(total_time_ms, 2),
            "avg_load_time_ms": round(total_time_ms / len(modules), 2) if modules else 0,
            "memory_usage_mb": round(memory_mb, 2),
            "modules_with_deps": len(self.dep_graph.graph),
            "parallel_groups": len(parallel_groups),
            "compiled_cache_hits": sum(1 for m in self.metrics.values() if m.compiled_pyc),
            "timestamp": datetime.now().isoformat()
        }
        
        # Log resumido
        logger.info(f"✅ Pré-carregamento concluído: {result['loaded_count']}/{result['total']} módulos")
        logger.info(f"   Tempo total: {result['total_time_ms']:.2f}ms")
        logger.info(f"   Memória estimada: {result['memory_usage_mb']:.2f}MB")
        
        if result["failed_count"] > 0:
            logger.warning(f"   ⚠️ {result['failed_count']} módulos com falha")
        
        return result
    
    def _get_memory_usage(self) -> float:
        """Estima uso de memória dos módulos carregados."""
        total_bytes = 0
        for module in self._loaded_modules.values():
            try:
                # Estima tamanho do módulo em memória
                total_bytes += sys.getsizeof(module)
                for attr in dir(module):
                    try:
                        obj = getattr(module, attr)
                        if hasattr(obj, '__sizeof__'):
                            total_bytes += obj.__sizeof__()
                    except Exception:
                        pass
            except Exception:
                pass
        return total_bytes / (1024 * 1024)
    
    def get_module(self, module_name: str) -> Optional[types.ModuleType]:
        """Recupera módulo pré-carregado pelo nome do arquivo."""
        with self._lock:
            for name, module in self._loaded_modules.items():
                if name.endswith(module_name) or module_name in name:
                    return module
        return None
    
    def get_all_modules(self) -> Dict[str, types.ModuleType]:
        """Retorna todos os módulos pré-carregados."""
        with self._lock:
            return self._loaded_modules.copy()
    
    def warmup_critical_modules(self) -> Dict[str, Any]:
        """
        Pré-carrega módulos críticos para inicialização rápida.
        Retorna estatísticas do warmup.
        """
        critical_patterns = [
            r"atena.*core",
            r".*router",
            r".*orchestrator",
            r".*memory",
            r".*agent",
            r".*llm",
            r".*embedding"
        ]
        
        critical_modules = []
        for py_file in self.modules_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            for pattern in critical_patterns:
                if re.search(pattern, str(py_file), re.IGNORECASE):
                    critical_modules.append(py_file)
                    break
        
        if not critical_modules:
            return {"status": "no_critical_modules_found"}
        
        logger.info(f"🔥 Warmup de {len(critical_modules)} módulos críticos...")
        result = self.preload_parallel(critical_modules)
        
        return {
            "status": "success",
            "critical_modules_count": len(critical_modules),
            "loaded": result["successful"],
            "failed": result["failed"]
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Gera relatório detalhado do pré-carregamento."""
        modules_with_deps = [m for m in self.metrics.values() if m.dependencies]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "modules_dir": str(self.modules_dir),
            "cache_dir": str(self.cache_dir),
            "total_modules_analyzed": len(self.metrics),
            "modules_loaded": len(self._loaded_modules),
            "modules_with_dependencies": len(modules_with_deps),
            "average_load_time_ms": round(
                sum(m.load_time_ms for m in self.metrics.values() if m.loaded_successfully) / 
                max(1, len([m for m in self.metrics.values() if m.loaded_successfully])), 2
            ),
            "total_size_mb": round(sum(m.size_bytes for m in self.metrics.values()) / (1024 * 1024), 2),
            "dependency_graph_size": len(self.dep_graph.graph),
            "loading_metrics": [
                {"module": m.name, "load_time_ms": m.load_time_ms, "size_kb": round(m.size_bytes / 1024, 1)}
                for m in self.metrics.values() if m.loaded_successfully
            ][:20]  # Top 20
        }


# Importações necessárias para paralelismo
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


# =============================================================================
# FUNÇÕES DE COMPATIBILIDADE (API original)
# =============================================================================

def _safe_module_name_legacy(path: Path) -> str:
    """Versão legada do safe_module_name para compatibilidade."""
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", path.stem)
    return f"atena_preload_{slug}"


def preload_all_modules(modules_dir: Path) -> dict[str, object]:
    """
    Versão legada para compatibilidade com código existente.
    Recomenda-se usar AtenaModulePreloader diretamente.
    """
    preloader = AtenaModulePreloader(modules_dir)
    result = preloader.preload_all(recursive=False, analyze_first=False)
    
    return {
        "loaded": result.get("loaded", []),
        "failed": [
            {"module": m, "error": "unknown"} 
            for m in result.get("failed", [])
        ] if result.get("failed") else [],
        "total": result.get("total", 0),
        "loaded_count": result.get("loaded_count", 0),
        "failed_count": result.get("failed_count", 0),
    }


def quick_preload(modules_dir: Path, max_workers: int = 4) -> Dict[str, Any]:
    """
    Pré-carregamento rápido sem análises avançadas.
    Utilitário para inicialização ágil.
    """
    preloader = AtenaModulePreloader(modules_dir)
    preloader.max_workers = max_workers
    preloader.use_compiled_cache = True
    preloader.recursive_preload = False
    
    return preloader.preload_all(recursive=False, analyze_first=False)


# =============================================================================
# MAIN - DEMONSTRAÇÃO
# =============================================================================

def main():
    """Demonstra o pré-carregador avançado."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Module Preloader v2.0")
    parser.add_argument("--modules-dir", type=str, default="./modules", help="Diretório de módulos")
    parser.add_argument("--recursive", action="store_true", help="Pré-carregamento recursivo")
    parser.add_argument("--warmup", action="store_true", help="Pré-carrega apenas módulos críticos")
    parser.add_argument("--report", action="store_true", help="Gera relatório detalhado")
    parser.add_argument("--workers", type=int, default=4, help="Número de workers paralelos")
    
    args = parser.parse_args()
    
    modules_path = Path(args.modules_dir)
    if not modules_path.exists():
        print(f"❌ Diretório não encontrado: {modules_path}")
        return 1
    
    # Inicializa pré-carregador
    preloader = AtenaModulePreloader(modules_path)
    preloader.max_workers = args.workers
    preloader.recursive_preload = args.recursive
    
    print("🔱 ATENA Module Preloader v2.0")
    print(f"   Diretório: {modules_path}")
    print(f"   Recursivo: {args.recursive}")
    print(f"   Workers: {args.workers}")
    print("-" * 50)
    
    start_time = time.time()
    
    if args.warmup:
        result = preloader.warmup_critical_modules()
        print(f"🔥 Warmup: {result.get('loaded', 0)} módulos críticos carregados")
    else:
        result = preloader.preload_all(recursive=args.recursive, analyze_first=True)
        
        print(f"📊 Resultado:")
        print(f"   Total: {result['total']} módulos")
        print(f"   Carregados: {result['loaded_count']}")
        print(f"   Falhas: {result['failed_count']}")
        print(f"   Tempo total: {result['total_time_ms']:.2f}ms")
        print(f"   Memória estimada: {result['memory_usage_mb']:.2f}MB")
        
        if result['failed']:
            print(f"\n⚠️ Módulos com falha:")
            for mod in result['failed'][:10]:
                print(f"   - {mod}")
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ Tempo total de execução: {elapsed*1000:.2f}ms")
    
    if args.report:
        report = preloader.generate_report()
        report_path = Path("atena_evolution/preload_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        report_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"📄 Relatório salvo: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
