#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — MISSÃO: CRIPTOGRAFIA QUÂNTICA PÓS-SINGULARIDADE
    Geração 358 — Proteção de Dados via Lógica de Fronteira
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from openai import OpenAI

# Adicionar o diretório core ao path para importar os novos pilares
sys.path.append(str(Path(__file__).parent.parent))
from core.atena_neuro_symbolic_verifier import NeuroSymbolicVerifier
from core.atena_swarm_intelligence import SwarmOrchestrator

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ATENA Ω — %(message)s")
logger = logging.getLogger("AtenaCrypto")

BASE_DIR = Path(__file__).parent.parent
EVOLUTION_DIR = BASE_DIR / "evolution"

class AtenaCryptoBrain:
    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4.1-mini"
        self.verifier = NeuroSymbolicVerifier()
        self.swarm = SwarmOrchestrator()

    def execute_mission(self) -> str:
        logger.info("🧠 ATENA Ω iniciando missão de Criptografia Quântica...")
        
        # 1. Debate no Enxame
        proposal = "Desenvolver um módulo de criptografia pós-quântica baseado em reticulados (Lattice-based cryptography) para proteger o DNA da ATENA."
        debate_result = self.swarm.debate(proposal)
        
        if debate_result["verdict"] != "APROVADO":
            return "Missão abortada pelo Enxame: Consenso não atingido."

        # 2. Geração de Código
        system_prompt = """Você é ATENA Ω, uma ASI na Geração 358.
Sua tarefa é criar o módulo 'atena_post_quantum_crypto.py'.
Este módulo deve implementar uma lógica avançada de criptografia inspirada em problemas de reticulados (Lattice-based), 
sendo resistente a ataques de computadores quânticos.

O código deve ser:
- Altamente técnico e funcional.
- Incluir classes para Geração de Chaves, Criptografia e Descriptografia.
- Ser seguro e passar no Verificador Neuro-Simbólico (sem os.system, eval, etc).
"""

        user_prompt = """Gere o código completo para 'modules/atena_post_quantum_crypto.py'.
Inclua um teste unitário no final do arquivo que demonstre a eficácia da proteção."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        code = response.choices[0].message.content.strip()
        
        # Limpar markdown se houver
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()

        # 3. Validação Neuro-Simbólica
        validation = self.verifier.validate(code)
        if validation["status"] != "APPROVED":
            logger.error(f"❌ Código REJEITADO pelo Verificador: {validation['reason']}")
            return f"Falha na validação: {validation['reason']}"

        # 4. Salvar Módulo
        output_path = BASE_DIR / "modules" / "atena_post_quantum_crypto.py"
        output_path.write_text(code)
        
        logger.info(f"✅ Módulo {output_path} criado e validado com sucesso.")
        return code

def run_mission():
    brain = AtenaCryptoBrain()
    code = brain.execute_mission()
    
    # Atualizar estado
    state_file = EVOLUTION_DIR / "states" / "atena_state.json"
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        state["generation"] = 358
        state["last_mission"] = "post_quantum_cryptography"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

if __name__ == "__main__":
    run_mission()
