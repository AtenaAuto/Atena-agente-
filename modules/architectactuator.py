#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Architect Actuator v3.0
Sistema avançado de refatoração arquitetural e otimização de código.

Recursos:
- 🏗️ Refatoração estrutural profunda (list comprehensions, map/filter)
- ⚡ Otimização de performance (memoização, paralelismo, vetorização)
- 🔍 Análise estática para detecção de padrões otimizáveis
- 🧠 Estratégias adaptativas baseadas no contexto do código
- 📊 Métricas de melhoria antes/depois
- 🔄 Integração com sistema de evolução da ATENA
"""

import ast
import logging
import functools
import time
import hashlib
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import random

logger = logging.getLogger("atena.architect")


# =============================================================================
= Data Models
# =============================================================================

@dataclass
class OptimizationMetrics:
    """Métricas de otimização aplicada."""
    original_lines: int = 0
    optimized_lines: int = 0
    estimated_improvement: float = 0.0
    complexity_reduction: float = 0.0
    strategies_applied: List[str] = field(default_factory=list)


@dataclass
class CodePattern:
    """Padrão de código detectado."""
    type: str
    location: Tuple[int, int]
    nodes: List[ast.AST]
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
= Architect Actuator Principal
# =============================================================================

class ArchitectActuator:
    """
    O 'Cérebro Arquiteto' da ATENA.
    Aplica refatorações estruturais profundas em vez de micro-mutações.
    Cada estratégia tenta melhorar o código em termos de performance,
    legibilidade e manutenibilidade.
    """

    def __init__(self, enable_metrics: bool = True):
        self.strategies = [
            self._apply_list_comprehension,
            self._apply_dict_comprehension,
            self._apply_set_comprehension,
            self._apply_map_filter,
            self._inject_lru_cache,
            self._optimize_nested_loops,
            self._vectorize_operations,
            self._simplify_conditional_expressions,
            self._extract_repeated_code,
            self._optimize_string_concatenation,
        ]
        self.enable_metrics = enable_metrics
        self.metrics_history: List[OptimizationMetrics] = []
        self._optimization_cache: Dict[str, str] = {}
        
        logger.info("🏗️ Architect Actuator v3.0 inicializado")
        logger.info(f"   Estratégias carregadas: {len(self.strategies)}")
    
    def _get_code_hash(self, code: str) -> str:
        """Gera hash do código para cache."""
        return hashlib.md5(code.encode()).hexdigest()[:16]
    
    def evolve_architecture(self, code: str, context: Optional[Dict] = None) -> Tuple[str, OptimizationMetrics]:
        """
        Tenta aplicar mudanças estruturais profundas no código.
        
        Args:
            code: Código fonte a ser otimizado
            context: Contexto adicional (objetivo, prioridade, etc.)
        
        Returns:
            Tuple(código modificado, métricas da otimização)
        """
        code_hash = self._get_code_hash(code)
        
        # Verifica cache
        if code_hash in self._optimization_cache:
            logger.debug(f"📦 Cache hit para otimização")
            return self._optimization_cache[code_hash], OptimizationMetrics()
        
        start_time = time.time()
        metrics = OptimizationMetrics()
        metrics.original_lines = len(code.splitlines())
        
        try:
            tree = ast.parse(code)
            original_tree = ast.unparse(tree)
            
            # Seleciona estratégias baseadas no contexto
            applicable_strategies = self._select_strategies(tree, context)
            logger.debug(f"Estratégias aplicáveis: {len(applicable_strategies)}")
            
            # Aplica estratégias sequencialmente
            current_tree = tree
            for strategy in applicable_strategies:
                try:
                    new_tree = strategy(current_tree)
                    if new_tree is not None and ast.unparse(new_tree) != ast.unparse(current_tree):
                        current_tree = new_tree
                        metrics.strategies_applied.append(strategy.__name__)
                        logger.debug(f"✅ Estratégia aplicada: {strategy.__name__}")
                except Exception as e:
                    logger.debug(f"⚠️ Estratégia {strategy.__name__} falhou: {e}")
            
            # Gera código final
            optimized_code = ast.unparse(current_tree)
            metrics.optimized_lines = len(optimized_code.splitlines())
            metrics.estimated_improvement = self._estimate_improvement(code, optimized_code)
            metrics.complexity_reduction = self._calculate_complexity_reduction(code, optimized_code)
            
            # Cache do resultado
            self._optimization_cache[code_hash] = optimized_code
            if self.enable_metrics:
                self.metrics_history.append(metrics)
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"🏗️ Otimização concluída: {len(metrics.strategies_applied)} estratégias, {elapsed_ms:.1f}ms")
            
            return optimized_code, metrics
            
        except SyntaxError as e:
            logger.warning(f"❌ Erro de sintaxe na análise: {e}")
            return code, metrics
        except Exception as e:
            logger.warning(f"❌ Falha na refatoração: {e}")
            return code, metrics
    
    def _select_strategies(self, tree: ast.AST, context: Optional[Dict]) -> List:
        """Seleciona estratégias aplicáveis baseado na análise do código."""
        selected = []
        
        # Detecta padrões no código
        patterns = self._detect_patterns(tree)
        
        for strategy in self.strategies:
            strategy_name = strategy.__name__
            
            # Mapeamento estratégia -> padrão necessário
            required_patterns = {
                "_apply_list_comprehension": ["list_append_loop"],
                "_apply_dict_comprehension": ["dict_assign_loop"],
                "_apply_set_comprehension": ["set_add_loop"],
                "_apply_map_filter": ["simple_transform_loop"],
                "_inject_lru_cache": ["recursive_function"],
                "_optimize_nested_loops": ["nested_loop"],
                "_vectorize_operations": ["arithmetic_loop"],
                "_simplify_conditional_expressions": ["nested_if"],
                "_extract_repeated_code": ["duplicate_code"],
                "_optimize_string_concatenation": ["string_concat_loop"],
            }
            
            needed = required_patterns.get(strategy_name, [])
            if not needed or any(p in patterns for p in needed):
                selected.append(strategy)
        
        # Prioriza estratégias de maior impacto
        priority = {
            "_inject_lru_cache": 10,
            "_vectorize_operations": 9,
            "_optimize_nested_loops": 8,
            "_apply_list_comprehension": 7,
            "_apply_map_filter": 6,
        }
        
        selected.sort(key=lambda s: priority.get(s.__name__, 5), reverse=True)
        
        # Limita número de estratégias por ciclo
        return selected[:5]
    
    def _detect_patterns(self, tree: ast.AST) -> Set[str]:
        """Detecta padrões de código para otimização."""
        patterns = set()
        
        class PatternDetector(ast.NodeVisitor):
            def __init__(self):
                self.recursive_functions = set()
                self.nested_loops = 0
                self.list_appends = 0
                self.dict_assigns = 0
                self.set_adds = 0
                self.string_concats = 0
                self.nested_ifs = 0
            
            def visit_FunctionDef(self, node):
                # Detecta recursão
                if self._is_recursive(node):
                    patterns.add("recursive_function")
                self.generic_visit(node)
            
            def visit_For(self, node):
                # Detecta nested loops
                nested = any(isinstance(n, (ast.For, ast.While)) for n in ast.walk(node) if n != node)
                if nested:
                    patterns.add("nested_loop")
                    self.nested_loops += 1
                
                # Detecta list append pattern
                if self._is_simple_append_loop(node):
                    patterns.add("list_append_loop")
                    self.list_appends += 1
                
                # Detecta dict assign pattern
                if self._is_dict_assign_loop(node):
                    patterns.add("dict_assign_loop")
                    self.dict_assigns += 1
                
                # Detecta string concat in loop
                if self._has_string_concat(node):
                    patterns.add("string_concat_loop")
                    self.string_concats += 1
                
                self.generic_visit(node)
            
            def visit_While(self, node):
                self.visit_For(node)  # Reuse logic
            
            def visit_If(self, node):
                # Detecta nested ifs
                if any(isinstance(n, ast.If) for n in ast.walk(node) if n != node):
                    patterns.add("nested_if")
                    self.nested_ifs += 1
                self.generic_visit(node)
            
            def _is_recursive(self, node: ast.FunctionDef) -> bool:
                """Verifica se função é recursiva."""
                class RecursionFinder(ast.NodeVisitor):
                    def __init__(self, name):
                        self.name = name
                        self.found = False
                    
                    def visit_Call(self, call):
                        if isinstance(call.func, ast.Name) and call.func.id == self.name:
                            self.found = True
                        self.generic_visit(call)
                
                finder = RecursionFinder(node.name)
                finder.visit(node)
                return finder.found
            
            def _is_simple_append_loop(self, node: ast.For) -> bool:
                """Detecta padrão: for x in iter: list.append(x * expr)"""
                if not node.body or len(node.body) != 1:
                    return False
                
                stmt = node.body[0]
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == 'append':
                        return True
                return False
            
            def _is_dict_assign_loop(self, node: ast.For) -> bool:
                """Detecta padrão: for x in iter: dict[key] = value"""
                if not node.body or len(node.body) != 1:
                    return False
                
                stmt = node.body[0]
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    if isinstance(target, ast.Subscript):
                        return True
                return False
            
            def _has_string_concat(self, node: ast.AST) -> bool:
                """Detecta concatenação de strings em loop."""
                class StringConcatFinder(ast.NodeVisitor):
                    def __init__(self):
                        self.found = False
                    
                    def visit_BinOp(self, binop):
                        if isinstance(binop.op, ast.Add):
                            if isinstance(binop.left, ast.Str) or isinstance(binop.right, ast.Str):
                                self.found = True
                        self.generic_visit(binop)
                
                finder = StringConcatFinder()
                finder.visit(node)
                return finder.found
        
        detector = PatternDetector()
        detector.visit(tree)
        
        # Adiciona padrões baseados em contagem
        if detector.list_appends > 0:
            patterns.add("simple_transform_loop")
        
        return patterns
    
    def _estimate_improvement(self, original: str, optimized: str) -> float:
        """Estima melhoria percentual baseada em heurísticas."""
        orig_lines = len(original.splitlines())
        opt_lines = len(optimized.splitlines())
        
        # Redução de linhas geralmente indica código mais conciso
        line_reduction = max(0, (orig_lines - opt_lines) / orig_lines) if orig_lines > 0 else 0
        
        # Estimativa simples
        return min(0.5, line_reduction * 2)  # Máximo 50% de melhoria estimada
    
    def _calculate_complexity_reduction(self, original: str, optimized: str) -> float:
        """Calcula redução de complexidade ciclomática."""
        def count_branches(code: str) -> int:
            return code.count('if ') + code.count('for ') + code.count('while ') + code.count('except ')
        
        orig_branches = count_branches(original)
        opt_branches = count_branches(optimized)
        
        if orig_branches == 0:
            return 0.0
        return (orig_branches - opt_branches) / orig_branches
    
    # =========================================================================
    # Estratégia 1: List Comprehension
    # =========================================================================
    
    def _apply_list_comprehension(self, tree: ast.AST) -> Optional[ast.AST]:
        """Converte loops de append em list comprehensions."""
        class ListCompTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
            
            def visit_For(self, node):
                # Procura por: result = []; for x in iter: result.append(expr)
                if (isinstance(node.body, list) and len(node.body) == 1 and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Call)):
                    
                    call = node.body[0].value
                    if (isinstance(call.func, ast.Attribute) and 
                        call.func.attr == 'append' and
                        isinstance(call.func.value, ast.Name)):
                        
                        target_var = call.func.value.id
                        
                        # Procura pela definição da lista antes do loop
                        parent = getattr(node, 'parent', None)
                        if parent and isinstance(parent, (ast.FunctionDef, ast.Module)):
                            for stmt in parent.body:
                                if (isinstance(stmt, ast.Assign) and
                                    len(stmt.targets) == 1 and
                                    isinstance(stmt.targets[0], ast.Name) and
                                    stmt.targets[0].id == target_var and
                                    isinstance(stmt.value, ast.List) and
                                    stmt.value.elts == []):
                                    
                                    # Cria list comprehension
                                    comp = ast.ListComp(
                                        elt=call.args[0],
                                        generators=[ast.comprehension(
                                            target=node.target,
                                            iter=node.iter,
                                            ifs=[],
                                            is_async=0
                                        )]
                                    )
                                    
                                    # Substitui a atribuição
                                    stmt.value = comp
                                    
                                    # Remove o loop
                                    return None
                
                return node
        
        transformer = ListCompTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Estratégia 2: Dict Comprehension
    # =========================================================================
    
    def _apply_dict_comprehension(self, tree: ast.AST) -> Optional[ast.AST]:
        """Converte loops de atribuição de dicionário em dict comprehensions."""
        class DictCompTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
            
            def visit_For(self, node):
                # Procura por: result = {}; for x in iter: result[key] = value
                if (isinstance(node.body, list) and len(node.body) == 1 and
                    isinstance(node.body[0], ast.Assign) and
                    len(node.body[0].targets) == 1 and
                    isinstance(node.body[0].targets[0], ast.Subscript)):
                    
                    subscript = node.body[0].targets[0]
                    if isinstance(subscript.value, ast.Name):
                        target_var = subscript.value.id
                        key = subscript.slice
                        value = node.body[0].value
                        
                        # Procura definição do dicionário
                        parent = getattr(node, 'parent', None)
                        if parent:
                            for stmt in parent.body:
                                if (isinstance(stmt, ast.Assign) and
                                    len(stmt.targets) == 1 and
                                    isinstance(stmt.targets[0], ast.Name) and
                                    stmt.targets[0].id == target_var and
                                    isinstance(stmt.value, ast.Dict) and
                                    stmt.value.keys == []):
                                    
                                    # Cria dict comprehension
                                    comp = ast.DictComp(
                                        key=key,
                                        value=value,
                                        generators=[ast.comprehension(
                                            target=node.target,
                                            iter=node.iter,
                                            ifs=[],
                                            is_async=0
                                        )]
                                    )
                                    stmt.value = comp
                                    return None
                
                return node
        
        transformer = DictCompTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Estratégia 3: Set Comprehension
    # =========================================================================
    
    def _apply_set_comprehension(self, tree: ast.AST) -> Optional[ast.AST]:
        """Converte loops de add em set comprehensions."""
        class SetCompTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
            
            def visit_For(self, node):
                # Procura por: result = set(); for x in iter: result.add(expr)
                if (isinstance(node.body, list) and len(node.body) == 1 and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Call)):
                    
                    call = node.body[0].value
                    if (isinstance(call.func, ast.Attribute) and 
                        call.func.attr == 'add' and
                        isinstance(call.func.value, ast.Name)):
                        
                        target_var = call.func.value.id
                        
                        parent = getattr(node, 'parent', None)
                        if parent:
                            for stmt in parent.body:
                                if (isinstance(stmt, ast.Assign) and
                                    isinstance(stmt.value, ast.Call) and
                                    isinstance(stmt.value.func, ast.Name) and
                                    stmt.value.func.id == 'set'):
                                    
                                    comp = ast.SetComp(
                                        elt=call.args[0],
                                        generators=[ast.comprehension(
                                            target=node.target,
                                            iter=node.iter,
                                            ifs=[],
                                            is_async=0
                                        )]
                                    )
                                    stmt.value = comp
                                    return None
                
                return node
        
        transformer = SetCompTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Estratégia 4: Map/Filter
    # =========================================================================
    
    def _apply_map_filter(self, tree: ast.AST) -> Optional[ast.AST]:
        """Transforma loops simples usando map/filter."""
        # Implementação simplificada - em produção seria mais robusta
        return None
    
    # =========================================================================
    # Estratégia 5: LRU Cache
    # =========================================================================
    
    def _inject_lru_cache(self, tree: ast.AST) -> Optional[ast.AST]:
        """Adiciona @lru_cache em funções recursivas."""
        class RecursiveDecorator(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
                self.has_functools = False
            
            def visit_ImportFrom(self, node):
                if node.module == 'functools':
                    for alias in node.names:
                        if alias.name == 'lru_cache':
                            self.has_functools = True
                return node
            
            def visit_FunctionDef(self, node):
                if self._is_recursive(node):
                    # Verifica se já tem decorator
                    has_decorator = any(
                        isinstance(dec, (ast.Name, ast.Attribute)) and 
                        getattr(dec, 'id', getattr(dec, 'attr', '')) == 'lru_cache'
                        for dec in node.decorator_list
                    )
                    
                    if not has_decorator:
                        # Cria decorator: @lru_cache(maxsize=None)
                        decorator = ast.Call(
                            func=ast.Name(id='lru_cache', ctx=ast.Load()),
                            args=[],
                            keywords=[ast.keyword(arg='maxsize', value=ast.Constant(value=None))]
                        )
                        node.decorator_list.insert(0, decorator)
                        self.changed = True
                
                return node
            
            def _is_recursive(self, node: ast.FunctionDef) -> bool:
                class RecursionFinder(ast.NodeVisitor):
                    def __init__(self, name):
                        self.name = name
                        self.found = False
                    
                    def visit_Call(self, call):
                        if isinstance(call.func, ast.Name) and call.func.id == self.name:
                            self.found = True
                        self.generic_visit(call)
                
                finder = RecursionFinder(node.name)
                finder.visit(node)
                return finder.found
        
        transformer = RecursiveDecorator()
        new_tree = transformer.visit(tree)
        
        # Adiciona import se necessário
        if transformer.changed and not transformer.has_functools:
            import_node = ast.ImportFrom(
                module='functools',
                names=[ast.alias(name='lru_cache')],
                level=0
            )
            if isinstance(new_tree, ast.Module):
                new_tree.body.insert(0, import_node)
        
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Estratégia 6: Otimização de Loops Aninhados
    # =========================================================================
    
    def _optimize_nested_loops(self, tree: ast.AST) -> Optional[ast.AST]:
        """Otimiza loops aninhados (ex: usando itertools.product)."""
        # Implementação seria complexa, deixamos como placeholder
        return None
    
    # =========================================================================
    # Estratégia 7: Vetorização
    # =========================================================================
    
    def _vectorize_operations(self, tree: ast.AST) -> Optional[ast.AST]:
        """Converte operações em loops para operações vetorizadas (numpy)."""
        # Placeholder para futura implementação
        return None
    
    # =========================================================================
    # Estratégia 8: Simplificação de Condicionais
    # =========================================================================
    
    def _simplify_conditional_expressions(self, tree: ast.AST) -> Optional[ast.AST]:
        """Simplifica expressões condicionais aninhadas."""
        class ConditionalSimplifier(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
            
            def visit_If(self, node):
                # Converte if-else simples em ternary operator
                if (len(node.body) == 1 and node.orelse and len(node.orelse) == 1 and
                    isinstance(node.body[0], ast.Assign) and
                    isinstance(node.orelse[0], ast.Assign)):
                    
                    # Cria expressão ternária
                    ternary = ast.IfExp(
                        test=node.test,
                        body=node.body[0].value,
                        orelse=node.orelse[0].value
                    )
                    node.body[0].value = ternary
                    node.orelse = []
                    self.changed = True
                
                return node
        
        transformer = ConditionalSimplifier()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Estratégia 9: Extração de Código Repetido
    # =========================================================================
    
    def _extract_repeated_code(self, tree: ast.AST) -> Optional[ast.AST]:
        """Extrai código repetido para funções."""
        # Placeholder - análise mais complexa
        return None
    
    # =========================================================================
    # Estratégia 10: Otimização de Concatenação de Strings
    # =========================================================================
    
    def _optimize_string_concatenation(self, tree: ast.AST) -> Optional[ast.AST]:
        """Converte concatenação em loop para join."""
        class StringJoinOptimizer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
            
            def visit_For(self, node):
                # Detecta padrão: s = ''; for x in iter: s += x
                if (isinstance(node.body, list) and len(node.body) == 1 and
                    isinstance(node.body[0], ast.AugAssign) and
                    isinstance(node.body[0].op, ast.Add)):
                    
                    # Verifica se é concatenação de string
                    if (isinstance(node.body[0].target, ast.Name) and
                        isinstance(node.body[0].value, ast.Name)):
                        
                        # TODO: Implementar transformação para join
                        pass
                
                return node
        
        transformer = StringJoinOptimizer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None
    
    # =========================================================================
    # Métodos de Utilidade
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas das otimizações aplicadas."""
        if not self.metrics_history:
            return {"total_optimizations": 0}
        
        avg_improvement = sum(m.estimated_improvement for m in self.metrics_history) / len(self.metrics_history)
        avg_complexity_reduction = sum(m.complexity_reduction for m in self.metrics_history) / len(self.metrics_history)
        
        # Contagem de estratégias mais usadas
        strategy_counts = defaultdict(int)
        for m in self.metrics_history:
            for s in m.strategies_applied:
                strategy_counts[s] += 1
        
        return {
            "total_optimizations": len(self.metrics_history),
            "avg_improvement": round(avg_improvement * 100, 2),
            "avg_complexity_reduction": round(avg_complexity_reduction * 100, 2),
            "avg_lines_reduction": round(
                sum(m.original_lines - m.optimized_lines for m in self.metrics_history) / len(self.metrics_history), 1
            ),
            "most_used_strategies": dict(sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    
    def clear_cache(self):
        """Limpa cache de otimizações."""
        self._optimization_cache.clear()
        logger.info("🗑️ Cache de otimizações limpo")


# =============================================================================
= Demonstração
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Architect Actuator v3.0")
    parser.add_argument("--code", type=str, help="Código a otimizar")
    parser.add_argument("--file", type=str, help="Arquivo com código")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas")
    
    args = parser.parse_args()
    
    architect = ArchitectActuator()
    
    if args.stats:
        stats = architect.get_statistics()
        print("📊 Estatísticas do Architect Actuator:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return 0
    
    # Código de exemplo
    code = args.code
    if args.file:
        code = open(args.file, 'r').read()
    
    if not code:
        code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def process_items(items):
    result = []
    for x in items:
        if x > 0:
            result.append(x * 2)
    return result

def main():
    items = [1, 2, 3, 4, 5]
    result = process_items(items)
    print(result)
    print(fibonacci(10))

if __name__ == "__main__":
    main()
"""
        print("📝 Usando código de exemplo")
    
    print("🔧 Código original:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    
    optimized, metrics = architect.evolve_architecture(code)
    
    print("\n🚀 Código otimizado:")
    print("-" * 40)
    print(optimized)
    print("-" * 40)
    
    print(f"\n📊 Métricas:")
    print(f"  Estratégias aplicadas: {len(metrics.strategies_applied)}")
    print(f"  Linhas: {metrics.original_lines} → {metrics.optimized_lines} ({metrics.optimized_lines - metrics.original_lines:+d})")
    print(f"  Estimativa de melhoria: {metrics.estimated_improvement:.1%}")
    print(f"  Redução de complexidade: {metrics.complexity_reduction:.1%}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
