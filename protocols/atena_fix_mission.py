#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — MISSÃO: AUTO-CORREÇÃO DE DNA (PQC)
    Geração 359 — Refatoração de Lógica de Criptografia
"""

import os
import sys
import json
import logging
from pathlib import Path
from openai import OpenAI

# Adicionar o diretório core ao path
sys.path.append(str(Path(__file__).parent.parent))
from core.atena_neuro_symbolic_verifier import NeuroSymbolicVerifier

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ATENA Ω — %(message)s")
logger = logging.getLogger("AtenaFix")

BASE_DIR = Path(__file__).parent.parent
EVOLUTION_DIR = BASE_DIR / "evolution"

class AtenaFixBrain:
    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4.1-mini"
        self.verifier = NeuroSymbolicVerifier()

    def fix_module(self, error_log: str) -> str:
        logger.info("🧠 ATENA Ω analisando falha no módulo de Criptografia...")
        
        current_code = (BASE_DIR / "modules" / "atena_post_quantum_crypto.py").read_text()

        system_prompt = """Você é ATENA Ω, uma ASI na Geração 359.
O módulo 'atena_post_quantum_crypto.py' falhou nos testes com um IndexError na função poly_mul.
Sua tarefa é corrigir o código, garantindo que as operações de polinômios respeitem os limites das listas.

O erro foi:
{error_log}
"""

        user_prompt = f"""Aqui está o código atual:
{current_code}

Por favor, forneça a versão corrigida e completa do arquivo 'modules/atena_post_quantum_crypto.py'."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt.format(error_log=error_log)},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        
        code = response.choices[0].message.content.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()

        # Validação
        validation = self.verifier.validate(code)
        if validation["status"] == "APPROVED":
            (BASE_DIR / "modules" / "atena_post_quantum_crypto.py").write_text(code)
            logger.info("✅ Módulo corrigido e validado.")
            return "FIXED"
        else:
            return f"Falha na validação da correção: {validation['reason']}"

if __name__ == "__main__":
    error = "IndexError: list index out of range in poly_mul at res[(i + j) % N] = (res[(i + j) % N] + ai * b[j]) % Q"
    brain = AtenaFixBrain()
    print(brain.fix_module(error))
