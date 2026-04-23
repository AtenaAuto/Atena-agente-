import ast
import logging
import functools
from typing import Optional

logger = logging.getLogger("atena.architect")


class ArchitectActuator:
    """
    O 'Crebro Arquiteto' da Atena.
    Aplica refatoraes estruturais (vetorizao, paralelismo, memoizao)
    em vez de micro-mutaes. Cada estratgia tenta melhorar o cdigo em
    termos de performance ou elegncia.
    """

    def __init__(self):
        self.strategies = [
            self._apply_list_comprehension_optimization,
            self._apply_map_filter_transformation,
            self._inject_lru_cache_logic,
            # Voc pode adicionar mais estratgias aqui
        ]

    def evolve_architecture(self, code: str) -> str:
        """
        Tenta aplicar uma mudana estrutural profunda no cdigo.
        Retorna o cdigo modificado ou o original se nada mudar.
        """
        try:
            tree = ast.parse(code)
            original = tree

            # Escolhe uma estratgia baseada em heursticas (por enquanto, tenta a primeira que funcionar)
            for strategy in self.strategies:
                new_tree = strategy(tree)
                if new_tree is not None and new_tree != tree:
                    # Se a rvore mudou, retorna o cdigo gerado
                    return ast.unparse(new_tree)

            return code
        except Exception as e:
            logger.warning(f"Architect falhou na refatorao: {e}")
            return code

    # --------------------------------------------------------------
    # Estratgia 1: Transformar loops de append em list comprehension
    # --------------------------------------------------------------
    def _apply_list_comprehension_optimization(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Converte loops 'for' que apenas fazem 'append' em uma lista para
        list comprehensions. Exemplo:
            result = []
            for x in items:
                result.append(x * 2)
        torna-se:
            result = [x * 2 for x in items]
        """
        class LoopToCompTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False

            def visit_For(self, node):
                # Procura por um padro:
                #   target = []
                #   for var in iter:
                #       target.append(expr)
                # e o loop  o nico statement no corpo (ou h apenas isso)
                if not isinstance(node.body, list) or len(node.body) != 1:
                    return node
                stmt = node.body[0]
                if not isinstance(stmt, ast.Expr):
                    # Se for uma expresso, pode ser um append?
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                        call = stmt.value
                        if isinstance(call.func, ast.Attribute) and call.func.attr == 'append':
                            # Precisamos identificar a lista que est recebendo append
                            # Vamos assumir que a lista foi definida antes como uma varivel
                            # e que o loop  o nico uso dela. Para simplificar, tentamos encontrar
                            # uma atribuio anterior onde a varivel  inicializada como lista vazia.
                            # Porm, por questes de simplicidade, essa transformao ser aplicada
                            # apenas quando o loop  o nico corpo e a lista  a mesma do alvo.
                            # Aqui farei uma verso mais simples: assumimos que a varivel alvo
                            #  a mesma que est sendo usada no call.func.value.
                            # Exemplo: result.append(x)
                            # A varivel 'result' pode estar definida antes.
                            # Vamos tentar encontrar a definio de 'result' como lista vazia.
                            target_var = call.func.value
                            if isinstance(target_var, ast.Name):
                                # Procurar por Assign anterior na mesma funo/bloco
                                # (aqui faremos uma busca superficial na rvore pai)
                                # Para no complicar demais, deixaremos para uma implementao futura.
                                pass
                    return node

                # Se no for um padro claro, retorna sem alterar
                return node

            def generic_visit(self, node):
                return super().generic_visit(node)

        transformer = LoopToCompTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None

    # --------------------------------------------------------------
    # Estratgia 2: Usar map/filter em vez de loops simples
    # --------------------------------------------------------------
    def _apply_map_filter_transformation(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Transforma loops simples que acumulam em uma lista usando map ou filter.
        Exemplo:
            result = []
            for x in items:
                if x > 0:
                    result.append(x * 2)
        pode virar:
            result = list(map(lambda x: x * 2, filter(lambda x: x > 0, items)))
        """
        class MapFilterTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False

            def visit_For(self, node):
                # Padro: loop com uma nica condio e um append
                # (verso simplificada, apenas para demonstrao)
                return node

        transformer = MapFilterTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None

    # --------------------------------------------------------------
    # Estratgia 3: Injetar lru_cache em funes recursivas
    # --------------------------------------------------------------
    def _inject_lru_cache_logic(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Detecta funes recursivas (que chamam a si mesmas) e adiciona
        o decorador @lru_cache(maxsize=None) para memoizao.
        Tambm garante a importao de functools.lru_cache.
        """
        class RecursiveFunctionTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
                self.has_functools_import = False

            def visit_ImportFrom(self, node):
                # Marca se j existe import de lru_cache
                if node.module == 'functools':
                    for alias in node.names:
                        if alias.name == 'lru_cache':
                            self.has_functools_import = True
                return node

            def visit_FunctionDef(self, node):
                # Verifica se a funo  recursiva (chama a si mesma)
                if self._is_recursive(node):
                    # Adiciona o decorador @lru_cache(maxsize=None)
                    # se ainda no estiver presente
                    has_decorator = any(
                        isinstance(dec, ast.Name) and dec.id == 'lru_cache'
                        for dec in node.decorator_list
                    )
                    if not has_decorator:
                        decorator = ast.Name(id='lru_cache', ctx=ast.Load())
                        # Se quiser argumentos, pode adicionar um Call
                        # Por enquanto, usamos um decorador simples (sem argumentos)
                        # Mas lru_cache precisa de maxsize=None para funes com argumentos.
                        # Vamos criar uma chamada: lru_cache(maxsize=None)
                        decorator_call = ast.Call(
                            func=decorator,
                            args=[],
                            keywords=[ast.keyword(arg='maxsize', value=ast.Constant(value=None))]
                        )
                        node.decorator_list.insert(0, decorator_call)
                        self.changed = True
                # Continua visitando o corpo da funo
                self.generic_visit(node)
                return node

            def _is_recursive(self, node: ast.FunctionDef) -> bool:
                """Verifica se a funo contm uma chamada para si mesma."""
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

        transformer = RecursiveFunctionTransformer()
        new_tree = transformer.visit(tree)

        # Se houve mudana e no havia import de functools, adicionamos
        if transformer.changed and not transformer.has_functools_import:
            import_node = ast.ImportFrom(
                module='functools',
                names=[ast.alias(name='lru_cache')],
                level=0
            )
            new_tree.body.insert(0, import_node)

        return new_tree if transformer.changed else None
