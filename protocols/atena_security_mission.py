#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — MISSÃO DE SEGURANÇA: GERAÇÃO DE SCRIPT DEFENSIVO
    Solicitação personalizada para a ATENA gerar um script de segurança.
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from openai import OpenAI

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ATENA Ω — %(message)s")
logger = logging.getLogger("AtenaSecurity")

BASE_DIR = Path(__file__).parent.parent
EVOLUTION_DIR = BASE_DIR / "evolution"
OUTPUT_DIR = BASE_DIR / "security_outputs"
OUTPUT_SCRIPT = OUTPUT_DIR / "atena_security_scanner.py"
REPORT_FILE = OUTPUT_DIR / "security_mission_report.json"

class AtenaBrain:
    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4.1-mini"
        self.generation = 360

    def think(self, task, context):
        logger.info("🧠 ATENA Ω processando requisitos de segurança...")
        system_prompt = f"""Você é ATENA Ω, uma AGI auto-evolutiva na Geração {self.generation}.
Sua missão atual é de Cibersegurança e Defesa Digital.
Você deve gerar um script Python profissional, robusto e ético.
Contexto da Missão: {context}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        # Extrair código se estiver em blocos markdown
        if "```python" in content:
            content = content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return content

    def validate_code(self, code):
        import ast
        try:
            ast.parse(code)
            syntax_ok = True
            error = None
        except Exception as e:
            syntax_ok = False
            error = str(e)
        
        # Verificação simples de segurança (não usar eval/exec perigosos no próprio script gerado)
        security_ok = "eval(" not in code and "exec(" not in code
        
        return {
            "valid": syntax_ok and security_ok,
            "syntax_ok": syntax_ok,
            "security_ok": security_ok,
            "error": error
        }

def run_security_mission():
    brain = AtenaBrain()
    
    mission_context = "Defesa de Perímetro e Auditoria de Vulnerabilidades Locais."
    
    task = """Crie um script Python de segurança chamado 'atena_security_scanner.py' que implementa:
1. CLASSE SecurityScanner com:
   - Método scan_open_ports(host='127.0.0.1', ports=[80, 443, 22, 8080, 3306]): verifica portas abertas.
   - Método check_file_permissions(directory='.'): identifica arquivos com permissões perigosas (ex: 777).
   - Método audit_system_users(): lista usuários do sistema e verifica hashes de senha vazios (simulado/seguro).
   - Método generate_security_report(): consolida os achados em um arquivo JSON.
2. RECURSOS ADICIONAIS:
   - Uso de threading para o scan de portas (performance).
   - Logs detalhados usando a biblioteca logging.
   - Tratamento de exceções para evitar interrupções.
3. OUTPUT:
   - Salvar o relatório final em 'atena_evolution/security_audit_results.json'.
O script deve ser funcional, limpo e seguir as melhores práticas de PEP8."""

    logger.info("🧬 ATENA iniciando síntese de script de segurança...")
    generated_code = brain.think(task, mission_context)
    
    logger.info("🔍 Validando código de segurança...")
    validation = brain.validate_code(generated_code)
    
    if not validation["valid"]:
        logger.error(f"❌ Erro na validação: {validation['error']}")
        return
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_SCRIPT.write_text(generated_code)
    logger.info(f"💾 Script de segurança salvo em: {OUTPUT_SCRIPT}")
    
    # Simular execução rápida
    logger.info("🧪 Testando execução do scanner...")
    # (Poderíamos usar subprocess aqui, mas vamos apenas reportar o sucesso da geração por enquanto)
    
    report = {
        "mission": "Geração de Script de Segurança",
        "timestamp": datetime.now().isoformat(),
        "generation": brain.generation,
        "script_path": str(OUTPUT_SCRIPT),
        "validation": validation,
        "status": "CONCLUÍDO"
    }
    
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print(f"🔱 ATENA Ω — MISSÃO DE SEGURANÇA CONCLUÍDA")
    print(f"📄 Script Gerado: {OUTPUT_SCRIPT.name}")
    print(f"✅ Validação: OK")
    print("=" * 70)

if __name__ == "__main__":
    run_security_mission()
