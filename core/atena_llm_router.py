#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Roteador de LLM da ATENA para seleção dinâmica de provider/modelo no terminal."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Optional
from urllib import request, error

from core.atena_local_lm import AtenaUltraBrain

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None


DEFAULT_QWEN_MODEL = os.getenv("ATENA_QWEN_MODEL") or "qwen-turbo"
LOCAL_MODEL_CANDIDATES = [
    os.getenv("ATENA_FREE_MODEL_NAME") or "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-0.5B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
]


@dataclass
class LLMConfig:
    provider: str = "local"  # local | openai | compat | custom | deepseek | anthropic | qwen
    model: str = "local-brain"
    base_url: Optional[str] = None


class AtenaLLMRouter:
    def __init__(self):
        self.cfg = LLMConfig()
        self._local_brain: Optional[AtenaUltraBrain] = None
        self._openai_client = None
        self.auto_prepare_result: Optional[tuple[bool, str]] = None
        self._auto_select_default_backend()
        self._maybe_prepare_default_local_model()

    def _auto_select_default_backend(self) -> None:
        """Seleciona backend remoto por padrão quando chaves estão disponíveis."""
        if os.getenv("DASHSCOPE_API_KEY") and OpenAI is not None:
            self.set_backend(f"qwen:{DEFAULT_QWEN_MODEL}")

    def _maybe_prepare_default_local_model(self) -> None:
        """
        Tenta preparar automaticamente um LLM local no boot, quando o provider atual é local.
        Pode ser desativado com ATENA_AUTO_PREPARE_LOCAL_MODEL=0.
        """
        if os.getenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1") != "1":
            return
        # Evita downloads/instalações em suíte de testes por padrão.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        if self.cfg.provider != "local":
            return
        try:
            if os.getenv("ATENA_AUTO_LLM_ORCHESTRATION", "1") == "1":
                self.auto_prepare_result = self.auto_orchestrate_llm()
            else:
                self.auto_prepare_result = self.prepare_free_local_model()
        except Exception as exc:  # noqa: BLE001
            self.auto_prepare_result = (False, f"falha no auto-prepare local: {exc}")

    def list_options(self) -> list[str]:
        opts = ["local:local-brain (transformers + fallback heurístico)"]
        opts.append("auto:orchestrate (escolhe provider/modelo e prepara runtime)")
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
            opts.append("custom indisponível (faltando pacote openai + chave)")
        if os.getenv("ANTHROPIC_API_KEY"):
            opts.append("anthropic:<model> (usa ANTHROPIC_API_KEY)")
        else:
            opts.append("anthropic indisponível (faltando ANTHROPIC_API_KEY)")
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
        if ":" in spec:
            provider, model = spec.split(":", 1)
        else:
            provider, model = spec, ""
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
            if not model:
                return False, "informe modelo no formato anthropic:modelo"
            self.cfg = LLMConfig(provider="anthropic", model=model, base_url="https://api.anthropic.com/v1")
            return True, f"backend anthropic ativado com modelo {model}"

        return False, f"provider desconhecido: {provider}"

    def _get_local_brain(self) -> AtenaUltraBrain:
        if self._local_brain is None:
            self._local_brain = AtenaUltraBrain()
        return self._local_brain

    def auto_orchestrate_llm(self) -> tuple[bool, str]:
        """
        Escolhe e prepara automaticamente o melhor backend/modelo disponível.
        Prioriza APIs quando há credencial; caso contrário cai para LLM local.
        """
        # 1) Backends remotos, quando disponíveis
        if os.getenv("DASHSCOPE_API_KEY") and OpenAI is not None:
            ok, msg = self.set_backend(f"qwen:{DEFAULT_QWEN_MODEL}")
            return ok, f"{msg} (seleção automática)"
        if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"):
            ok, msg = self.set_backend("deepseek:light")
            if ok:
                return True, f"{msg} (seleção automática)"

        # 2) Fallback local: tenta modelos candidatos e baixa automaticamente
        ok, _ = self.set_backend("local:local-brain")
        if not ok:
            return False, "falha ao ativar backend local"
        brain = self._get_local_brain()
        tried: list[str] = []
        for model_name in LOCAL_MODEL_CANDIDATES:
            if not model_name:
                continue
            model_name = model_name.strip()
            if not model_name or model_name in tried:
                continue
            tried.append(model_name)
            os.environ["LLM_MODEL_NAME"] = model_name
            brain.cfg.base_model_name = model_name
            ok_local, msg_local = brain.prepare_runtime_model()
            if ok_local:
                return True, f"local-brain pronto com {model_name} (seleção automática)"
        return False, f"não foi possível preparar LLM automaticamente. modelos tentados: {', '.join(tried)}"

    def prepare_free_local_model(self) -> tuple[bool, str]:
        """
        Prepara automaticamente um modelo local gratuito (Qwen) quando em provider local.
        """
        if self.cfg.provider != "local":
            return False, "Preparação de modelo local disponível apenas para provider local."
        brain = self._get_local_brain()
        return brain.prepare_runtime_model()

    def generate(self, prompt: str, context: str = "") -> str:
        if self.cfg.provider == "local":
            return self._get_local_brain().think(prompt, context=context)
        if self.cfg.provider == "deepseek":
            return self._generate_deepseek(prompt, context=context)
        if self.cfg.provider == "anthropic":
            return self._generate_anthropic(prompt, context=context)

        # openai/compat
        response = self._openai_client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": "Você é ATENA-Like, assistente técnico de terminal."},
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}"},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_deepseek(self, prompt: str, context: str = "") -> str:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "❌ DEEPSEEK_API_KEY não configurada."
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": "Você é ATENA-Like, assistente técnico de terminal."},
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}"},
            ],
            "temperature": 0.3,
            "max_tokens": 900,
        }
        req = request.Request(
            url=f"{self.cfg.base_url or 'https://api.deepseek.com/v1'}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=90) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except error.HTTPError as exc:
            return f"❌ DeepSeek HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return f"❌ Falha DeepSeek: {exc}"

    def _generate_anthropic(self, prompt: str, context: str = "") -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return "❌ ANTHROPIC_API_KEY não configurada."
        payload = {
            "model": self.cfg.model,
            "max_tokens": 900,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": f"Contexto: {context}\n\nPrompt: {prompt}",
                }
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
        try:
            with request.urlopen(req, timeout=90) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", [])
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict):
                    return (first.get("text") or "").strip()
            return ""
        except error.HTTPError as exc:
            return f"❌ Anthropic HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return f"❌ Falha Anthropic: {exc}"

    def learn_from_feedback(self, prompt: str, response: str, success: bool, score: float) -> None:
        if self.cfg.provider == "local":
            self._get_local_brain().learn_from_feedback(prompt, response, success, score)
