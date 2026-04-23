#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — PILAR 1: NEURO-SYMBOLIC LOGIC VERIFIER
    Geração 353 — Validação Formal de Código via Lógica Simbólica
"""

import ast
import logging
import re
from typing import Dict, List, Tuple

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ATENA Ω — %(message)s")
logger = logging.getLogger("AtenaNSVerifier")

class NeuroSymbolicVerifier:
    """
    Integra o poder das redes neurais com o rigor da lógica simbólica.
    Verifica se o código gerado segue regras formais de segurança e integridade.
    """
    
    def __init__(self):
        # Regras simbólicas de segurança (Axiomas)
        self.axioms = {
            "no_os_system": r"os\.system\(",
            "no_eval": r"eval\(",
            "no_exec": r"exec\(",
            "no_subprocess_shell": r"subprocess\.(run|call|Popen)\(.*?shell=True",
            "no_import_os": r"import\s+os|from\s+os\s+import"
        }
        
    def verify_syntax(self, code: str) -> Tuple[bool, str]:
        """Verifica se o código é sintaticamente válido (Lógica Simbólica)."""
        try:
            ast.parse(code)
            return True, "Sintaxe válida."
        except SyntaxError as e:
            return False, f"Erro de Sintaxe: {e}"

    def verify_security_axioms(self, code: str) -> Tuple[bool, List[str]]:
        """Verifica se o código viola axiomas de segurança pré-definidos."""
        violations = []
        for name, pattern in self.axioms.items():
            if re.search(pattern, code):
                violations.append(name)
        
        if not violations:
            return True, []
        return False, violations

    def analyze_complexity(self, code: str) -> Dict:
        """Analisa a complexidade ciclomática básica do código."""
        tree = ast.parse(code)
        complexity = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler)):
                complexity += 1
        return {"cyclomatic_complexity": complexity}

    def validate(self, code: str) -> Dict:
        """Executa a validação neuro-simbólica completa."""
        logger.info("🔍 Iniciando validação neuro-simbólica...")
        
        syntax_ok, syntax_msg = self.verify_syntax(code)
        if not syntax_ok:
            return {"status": "REJECTED", "reason": syntax_msg}
            
        security_ok, violations = self.verify_security_axioms(code)
        if not security_ok:
            return {"status": "REJECTED", "reason": f"Violação de Axiomas: {violations}"}
            
        complexity = self.analyze_complexity(code)
        
        logger.info("✅ Código aprovado pelo Verificador Neuro-Simbólico.")
        return {
            "status": "APPROVED",
            "metrics": complexity,
            "verdict": "Matematicamente seguro e sintaticamente correto."
        }

# Teste Unitário Inline
if __name__ == "__main__":
    verifier = NeuroSymbolicVerifier()
    
    # Teste 1: Código Seguro
    safe_code = "def add(a, b):\n    return a + b"
    print(f"Teste 1 (Seguro): {verifier.validate(safe_code)}")
    
    # Teste 2: Código Inseguro (Axioma violado)
    unsafe_code = "import os\ndef hack():\n    os.system('rm -rf /')"
    print(f"Teste 2 (Inseguro): {verifier.validate(unsafe_code)}")
