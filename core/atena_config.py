#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Configuração Centralizada
Todas as variáveis de ambiente e defaults em um único lugar.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Diretórios raiz ──────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR  = REPO_ROOT / "core"
MODULES_DIR = REPO_ROOT / "modules"
EVOLUTION_DIR = REPO_ROOT / "evolution"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
BRAIN_DIR = REPO_ROOT / "atena_brain"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "")
    if v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ── Configuração LLM ─────────────────────────────────────────────────────────
@dataclass
class LLMSettings:
    # Anthropic
    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
    )
    anthropic_default_model: str = field(
        default_factory=lambda: os.getenv(
            "ATENA_ANTHROPIC_MODEL", "claude-sonnet-4-6"
        )
    )
    anthropic_max_tokens: int = field(
        default_factory=lambda: _env_int("ATENA_ANTHROPIC_MAX_TOKENS", 1500)
    )

    # OpenAI / DeepSeek / Qwen
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    deepseek_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY")
    )
    dashscope_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("DASHSCOPE_API_KEY")
    )
    custom_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ATENA_CUSTOM_API_KEY")
    )

    # Timeouts e retries
    request_timeout_s: float = field(
        default_factory=lambda: _env_float("ATENA_LLM_TIMEOUT_S", 90.0)
    )
    max_retries: int = field(
        default_factory=lambda: _env_int("ATENA_LLM_MAX_RETRIES", 3)
    )
    retry_backoff_base: float = field(
        default_factory=lambda: _env_float("ATENA_LLM_RETRY_BACKOFF", 1.5)
    )

    # Circuit breaker
    circuit_failure_threshold: int = field(
        default_factory=lambda: _env_int("ATENA_CB_FAILURE_THRESHOLD", 5)
    )
    circuit_recovery_timeout_s: float = field(
        default_factory=lambda: _env_float("ATENA_CB_RECOVERY_TIMEOUT_S", 60.0)
    )

    # Cache de respostas
    response_cache_enabled: bool = field(
        default_factory=lambda: _env_bool("ATENA_RESPONSE_CACHE", True)
    )
    response_cache_max_size: int = field(
        default_factory=lambda: _env_int("ATENA_RESPONSE_CACHE_SIZE", 256)
    )
    response_cache_ttl_s: float = field(
        default_factory=lambda: _env_float("ATENA_RESPONSE_CACHE_TTL_S", 600.0)
    )


# ── Configuração geral ────────────────────────────────────────────────────────
@dataclass
class AtenaConfig:
    llm: LLMSettings = field(default_factory=LLMSettings)

    # Dashboard
    dashboard_port: int = field(
        default_factory=lambda: _env_int("ATENA_DASHBOARD_PORT", 8765)
    )
    dashboard_enabled: bool = field(
        default_factory=lambda: _env_bool("ATENA_DASHBOARD_ENABLED", False)
    )

    # Terminal
    router_timeout_s: float = field(
        default_factory=lambda: _env_float("ATENA_ROUTER_TIMEOUT_S", 90.0)
    )
    auto_prepare_local_model: bool = field(
        default_factory=lambda: _env_bool("ATENA_AUTO_PREPARE_LOCAL_MODEL", True)
    )
    auto_llm_orchestration: bool = field(
        default_factory=lambda: _env_bool("ATENA_AUTO_LLM_ORCHESTRATION", False)
    )

    # Logs
    log_level: str = field(
        default_factory=lambda: os.getenv("ATENA_LOG_LEVEL", "INFO").upper()
    )
    log_json: bool = field(
        default_factory=lambda: _env_bool("ATENA_LOG_JSON", False)
    )


# Instância global — importar e usar: `from core.atena_config import CONFIG`
CONFIG = AtenaConfig()
