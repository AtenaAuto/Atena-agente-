#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Roteador de LLM
Seleção dinâmica de provider/modelo com:
  - Retry com backoff exponencial
  - Circuit breaker por provider
  - Cache de respostas LRU/TTL
  - Anthropic claude-sonnet-4-6 como padrão
"""
from __future__ import annotations

import os
import json
import time
import logging
import threading
from dataclasses import dataclass
from typing import Optional
from urllib import request, error

from core.atena_local_lm import AtenaUltraBrain

logger = logging.getLogger("atena.llm_router")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

DEFAULT_QWEN_MODEL = os.getenv("ATENA_QWEN_MODEL") or "qwen-turbo"
DEFAULT_ANTHROPIC_MODEL = os.getenv("ATENA_ANTHROPIC_MODEL") or "claude-sonnet-4-6"
LOCAL_MODEL_CANDIDATES = [
    os.getenv("ATENA_FREE_MODEL_NAME") or "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-0.5B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
]
MAX_RETRIES = int(os.getenv("ATENA_LLM_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = float(os.getenv("ATENA_LLM_RETRY_BACKOFF", "1.5"))
REQUEST_TIMEOUT = float(os.getenv("ATENA_LLM_TIMEOUT_S", "90.0"))
CB_FAILURE_THRESHOLD = int(os.getenv("ATENA_CB_FAILURE_THRESHOLD", "5"))
CB_RECOVERY_TIMEOUT = float(os.getenv("ATENA_CB_RECOVERY_TIMEOUT_S", "60.0"))


class CircuitBreaker:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold: int = CB_FAILURE_THRESHOLD, recovery_timeout: float = CB_RECOVERY_TIMEOUT) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if time.monotonic() - (self._opened_at or 0) >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = self.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.monotonic()
                logger.warning("circuit breaker ABERTO após %d falhas", self._failures)

    def allow_request(self) -> bool:
        return self.state in (self.CLOSED, self.HALF_OPEN)


@dataclass
class LLMConfig:
    provider: str = "local"
    model: str = "local-brain"
    base_url: Optional[str] = None


class AtenaLLMRouter:
    def __init__(self) -> None:
        self.cfg = LLMConfig()
        self._local_brain: Optional[AtenaUltraBrain] = None
        self._openai_client = None
        self.auto_prepare_result: Optional[tuple[bool, str]] = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._cache = self._build_cache()
        self._auto_select_default_backend()
        self._maybe_prepare_default_local_model()

    def _build_cache(self):
        try:
            from core.atena_response_cache import get_global_cache
            enabled = os.getenv("ATENA_RESPONSE_CACHE", "1") == "1"
            max_size = int(os.getenv("ATENA_RESPONSE_CACHE_SIZE", "256"))
            ttl = float(os.getenv("ATENA_RESPONSE_CACHE_TTL_S", "600"))
            return get_global_cache(max_size=max_size, ttl_seconds=ttl, enabled=enabled)
        except Exception:
            return None

    def _cb(self, provider: str) -> CircuitBreaker:
        if provider not in self._circuit_breakers:
            self._circuit_breakers[provider] = CircuitBreaker()
        return self._circuit_breakers[provider]

    def _auto_select_default_backend(self) -> None:
        if os.getenv("ANTHROPIC_API_KEY"):
            self.set_backend(f"anthropic:{DEFAULT_ANTHROPIC_MODEL}")
            return
        if os.getenv("DASHSCOPE_API_KEY") and OpenAI is not None:
            self.set_backend(f"qwen:{DEFAULT_QWEN_MODEL}")

    def _maybe_prepare_default_local_model(self) -> None:
        if os.getenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1") != "1":
            return
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        if self.cfg.provider != "local":
            return
        try:
            if os.getenv("ATENA_AUTO_LLM_ORCHESTRATION", "0") == "1":
                self.auto_prepare_result = self.auto_orchestrate_llm()
            else:
                self.auto_prepare_result = self.prepare_free_local_model()
        except Exception as exc:
            self.auto_prepare_result = (False, f"falha no auto-prepare local: {exc}")

    def list_options(self) -> list[str]:
        opts = ["local:local-brain (transformers + fallback heurístico)"]
        opts.append("auto:orchestrate (escolhe provider/modelo e prepara runtime)")
        if os.getenv("ANTHROPIC_API_KEY"):
            opts.append(f"anthropic:{DEFAULT_ANTHROPIC_MODEL} (usa ANTHROPIC_API_KEY) ✅ padrão")
        else:
            opts.append("anthropic indisponível (faltando ANTHROPIC_API_KEY)")
        if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"):
            opts.append("deepseek:light (deepseek-chat)")
            opts.append("deepseek:heavy (deepseek-reasoner)")
        else:
            opts.append("deepseek indisponível (faltando DEEPSEEK_API_KEY ou OPENAI_API_KEY)")
        if OpenAI is not None and os.getenv("OPENAI_API_KEY"):
            opts.append("openai:<model> (usa OPENAI_API_KEY)")
            opts.append("compat:<model> (usa OPENAI_API_KEY + ATENA_OPENAI_BASE_URL)")
            opts.append("custom:<model>@<base_url> (usa ATENA_CUSTOM_API_KEY ou OPENAI_API_KEY)")
        else:
            opts.append("openai/compat indisponível (faltando pacote openai ou OPENAI_API_KEY)")
        if OpenAI is not None and (os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")):
            opts.append("qwen:<model> (usa DASHSCOPE_API_KEY ou OPENAI_API_KEY)")
        else:
            opts.append("qwen indisponível (faltando openai pkg ou DASHSCOPE_API_KEY)")
        return opts

    def current(self) -> str:
        return f"{self.cfg.provider}:{self.cfg.model}"

    def set_backend(self, spec: str) -> tuple[bool, str]:
        if not spec:
            return False, "spec vazio"
        provider, _, model = spec.partition(":")
        provider = provider.strip().lower()
        model = model.strip()

        if provider == "local":
            self.cfg = LLMConfig(provider="local", model="local-brain")
            return True, "backend local ativado"

        if provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, "DEEPSEEK_API_KEY (ou OPENAI_API_KEY) não configurada"
            model_norm = model.lower()
            if model_norm in {"", "light", "leve", "chat"}:
                model_name = "deepseek-chat"
            elif model_norm in {"heavy", "pesado", "reasoner"}:
                model_name = "deepseek-reasoner"
            else:
                model_name = model
            self.cfg = LLMConfig(provider="deepseek", model=model_name, base_url="https://api.deepseek.com/v1")
            return True, f"backend deepseek ativado com modelo {model_name}"

        if provider in {"openai", "compat", "custom"}:
            if OpenAI is None:
                return False, "pacote openai não instalado"
            api_key = os.getenv("ATENA_CUSTOM_API_KEY") if provider == "custom" else os.getenv("OPENAI_API_KEY")
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, "OPENAI_API_KEY/ATENA_CUSTOM_API_KEY não configurada"
            if not model:
                return False, "informe modelo no formato provider:modelo"
            base_url = None
            model_name = model
            if provider == "compat":
                base_url = os.getenv("ATENA_OPENAI_BASE_URL")
                if not base_url:
                    return False, "ATENA_OPENAI_BASE_URL não configurada para provider compat"
            elif provider == "custom":
                if "@" in model:
                    model_name, parsed_base_url = model.rsplit("@", 1)
                    model_name = model_name.strip()
                    base_url = parsed_base_url.strip()
                else:
                    base_url = os.getenv("ATENA_OPENAI_BASE_URL")
                if not model_name:
                    return False, "informe modelo no formato custom:modelo@base_url"
                if not base_url:
                    return False, "informe base_url no formato custom:modelo@base_url"
            self._openai_client = OpenAI(api_key=api_key, base_url=base_url)
            self.cfg = LLMConfig(provider=provider, model=model_name, base_url=base_url)
            return True, f"backend {provider} ativado com modelo {model_name}"

        if provider == "qwen":
            if OpenAI is None:
                return False, "pacote openai não instalado"
            api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, "DASHSCOPE_API_KEY (ou OPENAI_API_KEY) não configurada"
            model_name = model or DEFAULT_QWEN_MODEL
            base_url = os.getenv("ATENA_QWEN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self._openai_client = OpenAI(api_key=api_key, base_url=base_url)
            self.cfg = LLMConfig(provider="qwen", model=model_name, base_url=base_url)
            return True, f"backend qwen ativado com modelo {model_name}"

        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return False, "ANTHROPIC_API_KEY não configurada"
            model_name = model or DEFAULT_ANTHROPIC_MODEL
            self.cfg = LLMConfig(provider="anthropic", model=model_name, base_url="https://api.anthropic.com/v1")
            return True, f"backend anthropic ativado com modelo {model_name}"

        return False, f"provider desconhecido: {provider}"

    def generate(self, prompt: str, context: str = "") -> str:
        provider = self.cfg.provider
        if self._cache:
            cached = self._cache.get(prompt, context, provider)
            if cached is not None:
                return cached
        cb = self._cb(provider)
        if not cb.allow_request():
            logger.warning("circuit breaker ABERTO para %s, usando fallback local", provider)
            return self._get_local_brain().think(prompt, context=context)
        last_error: Exception = RuntimeError("sem tentativas")
        for attempt in range(MAX_RETRIES):
            try:
                response = self._dispatch(prompt, context)
                cb.record_success()
                if self._cache:
                    self._cache.set(prompt, response, context, provider)
                return response
            except Exception as exc:
                last_error = exc
                cb.record_failure()
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    logger.warning("tentativa %d/%d falhou (%s): %s — aguardando %.1fs", attempt + 1, MAX_RETRIES, provider, exc, wait)
                    time.sleep(wait)
        logger.error("todos os retries falharam para %s: %s", provider, last_error)
        if provider != "local":
            try:
                return self._get_local_brain().think(prompt, context=context)
            except Exception as fe:
                return f"❌ Falha total ({provider}): {last_error}. Fallback: {fe}"
        return f"❌ Falha local: {last_error}"

    def _dispatch(self, prompt: str, context: str) -> str:
        if self.cfg.provider == "local":
            return self._get_local_brain().think(prompt, context=context)
        if self.cfg.provider == "deepseek":
            return self._generate_deepseek(prompt, context=context)
        if self.cfg.provider == "anthropic":
            return self._generate_anthropic(prompt, context=context)
        response = self._openai_client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": "Você é ATENA, assistente técnico de terminal."},
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}"},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_deepseek(self, prompt: str, context: str = "") -> str:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY não configurada")
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": "Você é ATENA, assistente técnico de terminal."},
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}"},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }
        req = request.Request(
            url=f"{self.cfg.base_url or 'https://api.deepseek.com/v1'}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

    def _generate_anthropic(self, prompt: str, context: str = "") -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY não configurada")
        payload = {
            "model": self.cfg.model,
            "max_tokens": 1500,
            "temperature": 0.3,
            "system": "Você é ATENA, assistente técnico inteligente de terminal. Responda em português, de forma clara e precisa.",
            "messages": [
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}" if context else prompt}
            ],
        }
        req = request.Request(
            url=f"{self.cfg.base_url or 'https://api.anthropic.com/v1'}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("content", [])
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict):
                return (first.get("text") or "").strip()
        return ""

    def _get_local_brain(self) -> AtenaUltraBrain:
        if self._local_brain is None:
            self._local_brain = AtenaUltraBrain()
        return self._local_brain

    def auto_orchestrate_llm(self) -> tuple[bool, str]:
        if os.getenv("ANTHROPIC_API_KEY"):
            ok, msg = self.set_backend(f"anthropic:{DEFAULT_ANTHROPIC_MODEL}")
            return ok, f"{msg} (seleção automática)"
        if os.getenv("DASHSCOPE_API_KEY") and OpenAI is not None:
            ok, msg = self.set_backend(f"qwen:{DEFAULT_QWEN_MODEL}")
            return ok, f"{msg} (seleção automática)"
        if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"):
            ok, msg = self.set_backend("deepseek:light")
            if ok:
                return True, f"{msg} (seleção automática)"
        ok, _ = self.set_backend("local:local-brain")
        if not ok:
            return False, "falha ao ativar backend local"
        brain = self._get_local_brain()
        tried: list[str] = []
        for model_name in LOCAL_MODEL_CANDIDATES:
            if not model_name or model_name in tried:
                continue
            tried.append(model_name)
            os.environ["LLM_MODEL_NAME"] = model_name
            brain.cfg.base_model_name = model_name
            ok_local, msg_local = brain.prepare_runtime_model()
            if ok_local:
                return True, f"local-brain pronto com {model_name} (seleção automática)"
            if "bloqueado por rede/proxy" in msg_local.lower():
                return False, msg_local
        return False, f"não foi possível preparar LLM automaticamente. tentados: {', '.join(tried)}"

    def prepare_free_local_model(self) -> tuple[bool, str]:
        if self.cfg.provider != "local":
            return False, "Preparação de modelo local disponível apenas para provider local."
        return self._get_local_brain().prepare_runtime_model()

    def learn_from_feedback(self, prompt: str, response: str, success: bool, score: float) -> None:
        if self.cfg.provider == "local":
            self._get_local_brain().learn_from_feedback(prompt, response, success, score)

    def cache_stats(self) -> dict:
        return self._cache.stats() if self._cache else {"enabled": False}

    def circuit_status(self) -> dict:
        return {p: cb.state for p, cb in self._circuit_breakers.items()}
