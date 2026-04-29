#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
                ATENA NEURAL v4.2 - ULTIMATE EDITION (CORRIGIDO)
  LLM leve (phi-2) | Gerao de cdigo vlido | Fallback robusto
"""

import os
import sys
import json
import time
import random
import logging
import sqlite3
import subprocess
import tempfile
import re
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# =============================================================================
# IMPORTAES OBRIGATRIAS
# =============================================================================
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logging.warning("PyTorch no instalado. Motor ultimate ter funcionalidade reduzida.")

# =============================================================================
# 1. CONFIGURAO ULTRA (AJUSTADA)
# =============================================================================
@dataclass
class UltraConfig:
    BASE_DIR: Path = Path("./atena_evolution")
    use_llm: bool = True
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
    llm_device: str = "cpu"
    llm_max_length: int = 2048        # Aumentado para suportar Chain-of-Thought
    temperature: float = 0.6          # Ajustado para melhor raciocínio
    num_beams: int = 1                # DeepSeek-R1 prefere amostragem simples
    max_new_tokens: int = 1024        # Aumentado para o bloco <think> e resposta

cfg = UltraConfig()

# =============================================================================
# 2. SANDBOX SIMPLES
# =============================================================================
class SecureSandbox:
    def execute(self, code: str, input_data: str = "") -> Tuple[bool, str, float]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            fname = f.name
        start = time.time()
        try:
            proc = subprocess.run([sys.executable, fname], input=input_data, capture_output=True, text=True, timeout=10)
            elapsed = time.time() - start
            return proc.returncode == 0, proc.stdout + proc.stderr, elapsed
        except subprocess.TimeoutExpired:
            return False, "Timeout", 10.0
        finally:
            os.unlink(fname)

# =============================================================================
# 3. GERADOR CORRIGIDO
# =============================================================================
class AdvancedGenerator:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer

    def generate(self, prompt: str, max_new_tokens: int = 1024) -> str:
        # Prompt otimizado para DeepSeek-R1 (Reasoning)
        full_prompt = f"""<system>You are an expert autonomous AI agent. Use your internal reasoning to solve the task.</system>
<user>{prompt}</user>
<think>"""
        inputs = self.tokenizer(full_prompt, return_tensors="pt", truncation=True, max_length=cfg.llm_max_length).to(self.model.device)
        with torch.no_grad():
            output = self.model.generate(
                inputs.input_ids,
                max_new_tokens=max_new_tokens,
                temperature=cfg.temperature,
                num_beams=cfg.num_beams,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        result = self.tokenizer.decode(output[0], skip_special_tokens=True)
        
        # Extração inteligente para DeepSeek-R1 (remove o bloco <think> se presente)
        if "</think>" in result:
            thought_process = result.split("</think>")[0].replace("<think>", "").strip()
            result = result.split("</think>")[-1].strip()
            logging.info(f"🧠 Raciocínio da IA: {thought_process[:200]}...")

        # Extrai apenas o código (remove markdown)
        if "```python" in result:
            result = result.split("```python")[-1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1]
        # Remove linhas que no comeam com 'def ' ou 'class '
        lines = result.split('\n')
        code_lines = []
        in_function = False
        for line in lines:
            if line.strip().startswith('def ') or line.strip().startswith('class '):
                in_function = True
            if in_function:
                code_lines.append(line)
                if line.strip() == '' and len(code_lines) > 5:
                    break
        result = '\n'.join(code_lines)
        return result.strip()

# =============================================================================
# 4. AVALIADOR SIMPLES
# =============================================================================
class CodeEvaluator:
    def __init__(self):
        self.sandbox = SecureSandbox()

    def security_scan(self, code: str) -> bool:
        dangerous = [r'os\.system', r'subprocess\.call', r'eval\(', r'exec\(', r'__import__\(']
        return not any(re.search(p, code) for p in dangerous)

    def evaluate(self, code: str) -> Dict:
        if not self.security_scan(code):
            return {"score": 0.0, "valid": False}
        try:
            ast.parse(code)  # verifica sintaxe
        except SyntaxError:
            return {"score": 0.0, "valid": False, "syntax_error": True}
        success, output, exec_time = self.sandbox.execute(code)
        if not success:
            return {"score": 0.0, "valid": False, "runtime_error": output}
        lines = len(code.splitlines())
        score = min(100, max(0, 100 - lines/10 + exec_time*5))
        return {"score": round(score, 2), "valid": True, "lines": lines}

# =============================================================================
# 5. DUMMY MUTATION ENGINE (COMPATIBILIDADE)
# =============================================================================
class DummyMutationEngine:
    def __init__(self):
        self.grok = None
        self.mutation_types = ["add_comment"]
    def mutate(self, code, mtype): return code, "dummy"
    def generate_candidates(self, code, types, n=None): return []

class DummyLearner:
    def start(self): pass
    def stop(self): pass
class DummyNewsClient:
    def update_objectives(self): pass
class DummyPredictor:
    def train(self): pass
class DummyLanguageTrainer: pass
class DummyVocabularyHarvester:
    def start(self): pass
    def stop(self): pass
class DummyEpisodicMemory: pass
class DummyRewardSystem: pass
class DummyFeedbackLoop: pass

# =============================================================================
# 6. ORQUESTRADOR PRINCIPAL
# =============================================================================
class AtenaUltimateCore:
    def __init__(self, problem=None):
        self.problem = problem
        self.model = None
        self.tokenizer = None
        self._init_llm()
        self.evaluator = CodeEvaluator()
        self.generator = AdvancedGenerator(self.model, self.tokenizer) if (cfg.use_llm and self.model) else None
        self.current_code = self._load_current_code()
        self.best_score = self._evaluate(self.current_code)["score"]
        self.generation = 0
        # Compatibilidade
        self.mutation_engine = DummyMutationEngine()
        self.learner = DummyLearner()
        self.news = DummyNewsClient()
        self.predictor = DummyPredictor()
        self.lang_trainer = DummyLanguageTrainer()
        self.vocab_harvester = DummyVocabularyHarvester()
        self.episodic_memory = DummyEpisodicMemory()
        self.reward_system = DummyRewardSystem()
        self.feedback_loop = DummyFeedbackLoop()
        self.v3 = None
        self.rag = None
        self.original_code = self.current_code
        self.engine_path = cfg.BASE_DIR / "code" / "atena_engine.py"

    def _init_llm(self):
        if not cfg.use_llm or not HAS_TORCH:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                cfg.llm_model_name,
                device_map="cpu",
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                torch_dtype=torch.float32
            )
            self.tokenizer = AutoTokenizer.from_pretrained(cfg.llm_model_name, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.eval()
            logging.info("LLM carregado com sucesso")
        except Exception as e:
            logging.error(f"Falha ao carregar LLM: {e}")

    def _load_current_code(self) -> str:
        code_file = cfg.BASE_DIR / "code" / "atena_current.py"
        if code_file.exists():
            return code_file.read_text()
        return "def main():\n    print('Atena v4')\n"

    def _evaluate(self, code: str) -> Dict:
        return self.evaluator.evaluate(code)

    def generate_code(self, prompt: str) -> str:
        if not self.generator:
            return "def dummy():\n    return 0"
        # Tenta at 3 vezes gerar cdigo vlido
        for attempt in range(3):
            code = self.generator.generate(prompt)
            if code and 'def ' in code and '(' in code:
                # Verifica sintaxe
                try:
                    ast.parse(code)
                    return code
                except:
                    pass
            # Se falhou, aumenta temperatura e tenta de novo
            if attempt < 2:
                logging.warning(f"Tentativa {attempt+1} falhou, regenerando...")
                time.sleep(1)
        return "def fallback():\n    return 0"

    def evolve_one_cycle(self) -> Dict:
        self.generation += 1
        prompt = f"Write a Python function that {random.choice(['sorts a list in ascending order', 'computes the nth Fibonacci number efficiently', 'checks if a number is prime'])}"
        new_code = self.generate_code(prompt)
        metrics = self._evaluate(new_code)
        score = metrics["score"]
        replaced = score > self.best_score
        if replaced:
            self.best_score = score
            self.current_code = new_code
            code_file = cfg.BASE_DIR / "code" / "atena_current.py"
            code_file.parent.mkdir(parents=True, exist_ok=True)
            code_file.write_text(new_code)
        logging.info(f"Gen {self.generation}: score={score:.2f} best={self.best_score:.2f}")
        return {"generation": self.generation, "score": score, "replaced": replaced}

# =============================================================================
# 7. PATCH PARA COMPATIBILIDADE
# =============================================================================
def patch_atena_core(original_core):
    new_core = AtenaUltimateCore(getattr(original_core, 'problem', None))
    original_core.__class__ = type('PatchedCore', (original_core.__class__,), {})
    original_core.ultra = new_core
    def evolve_one_cycle(self):
        return new_core.evolve_one_cycle()
    def generate_code(self, prompt):
        return new_core.generate_code(prompt)
    original_core.evolve_one_cycle = evolve_one_cycle.__get__(original_core)
    original_core.generate_code = generate_code.__get__(original_core)
    return new_core

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    core = AtenaUltimateCore()
    for _ in range(3):
        print(core.evolve_one_cycle())
