"""
Testes unitários para core/security_validator.py
"""
import pytest

from core.security_validator import (
    CodeSecurityValidator,
    SecurityLevel,
    ValidationResult,
    validate_code_safe
)


class TestSecurityValidatorBasics:
    """Testes básicos do validador de segurança."""
    
    def test_initialization_default(self):
        """Testa inicialização com nível padrão."""
        validator = CodeSecurityValidator()
        assert validator.security_level == SecurityLevel.STANDARD
        assert validator.violations == []
        assert validator.warnings == []
    
    def test_initialization_strict(self):
        """Testa inicialização em modo STRICT."""
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        assert validator.security_level == SecurityLevel.STRICT
    
    def test_initialization_permissive(self):
        """Testa inicialização em modo PERMISSIVE."""
        validator = CodeSecurityValidator(SecurityLevel.PERMISSIVE)
        assert validator.security_level == SecurityLevel.PERMISSIVE


class TestValidSafeCode:
    """Testes com código Python seguro."""
    
    def test_simple_arithmetic(self):
        """Testa código aritmético simples."""
        code = "result = 2 + 2"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
        assert len(result.violations) == 0
    
    def test_function_definition(self):
        """Testa definição de função."""
        code = """
def add(a, b):
    return a + b

result = add(2, 3)
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
        assert len(result.violations) == 0
    
    def test_list_comprehension(self):
        """Testa list comprehension."""
        code = "numbers = [x * 2 for x in range(10)]"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_dict_operations(self):
        """Testa operações com dicionários."""
        code = """
data = {'name': 'ATENA', 'version': '3.2'}
name = data.get('name')
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_string_formatting(self):
        """Testa formatação de strings."""
        code = """
name = "World"
greeting = f"Hello, {name}!"
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True


class TestDangerousCode:
    """Testes com código perigoso que deve ser bloqueado."""
    
    def test_os_import_blocked(self):
        """Testa bloqueio de import os."""
        code = "import os"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("os" in v for v in result.violations)
    
    def test_subprocess_import_blocked(self):
        """Testa bloqueio de import subprocess."""
        code = "import subprocess"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("subprocess" in v for v in result.violations)
    
    def test_eval_blocked(self):
        """Testa bloqueio de eval()."""
        code = "result = eval('2 + 2')"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("eval" in v for v in result.violations)
    
    def test_exec_blocked(self):
        """Testa bloqueio de exec()."""
        code = "exec('print(\"danger\")')"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("exec" in v for v in result.violations)
    
    def test_import_blocked(self):
        """Testa bloqueio de __import__()."""
        code = "m = __import__('os')"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
    
    def test_multiple_violations(self):
        """Testa código com múltiplas violações."""
        code = """
import os
import subprocess
exec('danger')
eval('more danger')
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert len(result.violations) >= 4
    
    def test_dangerous_from_import(self):
        """Testa bloqueio de from ... import."""
        code = "from os import system"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("os" in v for v in result.violations)


class TestSecurityLevels:
    """Testes de diferentes níveis de segurança."""
    
    def test_strict_blocks_with_statement(self):
        """STRICT deve bloquear with statements."""
        code = """
with open('file.txt') as f:
    content = f.read()
"""
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("with" in v.lower() for v in result.violations)
    
    def test_standard_allows_with_statement_warning(self):
        """STANDARD deve permitir with mas com aviso."""
        code = """
data = {'key': 'value'}
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_strict_blocks_try_except(self):
        """STRICT deve bloquear try/except."""
        code = """
try:
    x = 1 / 0
except ZeroDivisionError:
    x = 0
"""
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        result = validator.validate(code)
        
        assert result.is_valid is False
    
    def test_permissive_allows_more(self):
        """PERMISSIVE deve ser mais permissivo."""
        code = """
global x
x = 10
"""
        validator_strict = CodeSecurityValidator(SecurityLevel.STRICT)
        validator_permissive = CodeSecurityValidator(SecurityLevel.PERMISSIVE)
        
        result_strict = validator_strict.validate(code)
        result_permissive = validator_permissive.validate(code)
        
        # STRICT deve bloquear global
        assert result_strict.is_valid is False
        # PERMISSIVE deve permitir
        assert result_permissive.is_valid is True


class TestDangerousAttributes:
    """Testes de acesso a atributos perigosos."""
    
    def test_code_attribute_blocked(self):
        """Testa bloqueio de __code__."""
        code = "x = some_func.__code__"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("__code__" in v for v in result.violations)
    
    def test_globals_attribute_blocked(self):
        """Testa bloqueio de __globals__."""
        code = "x = some_func.__globals__"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert any("__globals__" in v for v in result.violations)
    
    def test_class_attribute_blocked(self):
        """Testa bloqueio de __class__."""
        code = "x = obj.__class__"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False


class TestValidationResult:
    """Testes da classe ValidationResult."""
    
    def test_validation_result_structure(self):
        """Testa estrutura do resultado."""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate("x = 1")
        
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'violations')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'security_level')
        assert hasattr(result, 'analyzed_nodes')
    
    def test_analyzed_nodes_count(self):
        """Testa contagem de nós analisados."""
        code = """
def func():
    x = 1
    y = 2
    return x + y
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.analyzed_nodes > 0


class TestSyntaxErrors:
    """Testes de tratamento de erros de sintaxe."""
    
    def test_syntax_error_detection(self):
        """Testa detecção de erro de sintaxe."""
        code = "def func("  # Sintaxe inválida
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False
        assert len(result.violations) > 0
        assert any("sintaxe" in v.lower() for v in result.violations)
    
    def test_indentation_error(self):
        """Testa erro de indentação."""
        code = """
def func():
x = 1
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is False


class TestHelperFunction:
    """Testes da função helper validate_code_safe."""
    
    def test_validate_code_safe_valid(self):
        """Testa função helper com código válido."""
        is_valid, violations = validate_code_safe("x = 1 + 2")
        
        assert is_valid is True
        assert len(violations) == 0
    
    def test_validate_code_safe_invalid(self):
        """Testa função helper com código inválido."""
        is_valid, violations = validate_code_safe("import os")
        
        assert is_valid is False
        assert len(violations) > 0
    
    def test_validate_code_safe_custom_level(self):
        """Testa função helper com nível customizado."""
        code = "global x"
        
        is_valid_strict, _ = validate_code_safe(code, SecurityLevel.STRICT)
        is_valid_permissive, _ = validate_code_safe(code, SecurityLevel.PERMISSIVE)
        
        assert is_valid_strict is False
        assert is_valid_permissive is True


class TestComplexScenarios:
    """Testes de cenários complexos."""
    
    def test_nested_functions(self):
        """Testa funções aninhadas."""
        code = """
def outer():
    def inner():
        return 42
    return inner()
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_class_definition(self):
        """Testa definição de classe."""
        code = """
class MyClass:
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_lambda_functions(self):
        """Testa funções lambda."""
        code = "square = lambda x: x ** 2"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_generator_expression(self):
        """Testa expressão geradora."""
        code = "gen = (x ** 2 for x in range(10))"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_multiple_safe_imports(self):
        """Testa múltiplos imports seguros."""
        code = """
import math
import json
from typing import List, Dict
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        # math, json e typing são seguros
        assert result.is_valid is True
    
    def test_realistic_data_processing(self):
        """Testa código realista de processamento de dados."""
        code = """
def process_data(items):
    filtered = [x for x in items if x > 0]
    squared = [x ** 2 for x in filtered]
    total = sum(squared)
    average = total / len(squared) if squared else 0
    return {
        'total': total,
        'average': average,
        'count': len(squared)
    }

data = [1, -2, 3, -4, 5]
result = process_data(data)
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
        assert len(result.violations) == 0


class TestEdgeCases:
    """Testes de casos extremos."""
    
    def test_empty_code(self):
        """Testa código vazio."""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate("")
        
        assert result.is_valid is True
        assert result.analyzed_nodes >= 0
    
    def test_only_comments(self):
        """Testa código com apenas comentários."""
        code = """
# This is a comment
# Another comment
"""
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
    
    def test_very_long_code(self):
        """Testa código muito longo."""
        code = "\n".join([f"x{i} = {i}" for i in range(1000)])
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        
        assert result.is_valid is True
        assert result.analyzed_nodes > 1000


# Fixtures específicas
@pytest.fixture
def safe_fibonacci_code():
    """Código seguro de Fibonacci."""
    return """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
"""


@pytest.fixture
def dangerous_system_code():
    """Código perigoso com chamadas de sistema."""
    return """
import os
import subprocess

os.system('rm -rf /')
subprocess.run(['malicious', 'command'])
"""


def test_fixture_safe_code(safe_fibonacci_code):
    """Testa fixture de código seguro."""
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    result = validator.validate(safe_fibonacci_code)
    assert result.is_valid is True


def test_fixture_dangerous_code(dangerous_system_code):
    """Testa fixture de código perigoso."""
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    result = validator.validate(dangerous_system_code)
    assert result.is_valid is False
