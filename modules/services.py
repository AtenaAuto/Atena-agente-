#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω Advanced Services v3.0 — Serviços Auxiliares e Integrações
Sistema completo de integração com APIs externas, cache, rate limiting e fallbacks.

Recursos:
- 🌐 Integração com múltiplas APIs (Grok, OpenAI, Claude, Gemini, etc.)
- 💾 Cache inteligente com TTL
- 🚦 Rate limiting automático
- 🔄 Fallback entre provedores
- 📊 Telemetria e monitoramento
- 🛡️ Tratamento robusto de erros
- ⚡ Execução assíncrona
- 📈 Métricas de uso e performance
"""

import os
import logging
import json
import hashlib
import time
import asyncio
import threading
from typing import Optional, Dict, Any, List, Tuple, Callable
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from functools import wraps

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    """Métricas de uso de serviços."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_call: Optional[datetime] = None
    last_error: Optional[str] = None
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls
    
    def record_success(self, latency_ms: float):
        self.total_calls += 1
        self.successful_calls += 1
        self.total_latency_ms += latency_ms
        self.last_call = datetime.now()
    
    def record_failure(self, error: str):
        self.total_calls += 1
        self.failed_calls += 1
        self.last_error = error
        self.last_call = datetime.now()
    
    def record_cache_hit(self):
        self.cache_hits += 1
    
    def record_cache_miss(self):
        self.cache_misses += 1
    
    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_call": self.last_call.isoformat() if self.last_call else None,
            "last_error": self.last_error,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hits / max(1, self.cache_hits + self.cache_misses), 4)
        }


class RateLimiter:
    """Implementa rate limiting para APIs."""
    
    def __init__(self, max_calls: int = 60, time_window_seconds: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window_seconds
        self.calls: deque = deque()
        self._lock = threading.RLock()
    
    def acquire(self) -> bool:
        """Tenta adquirir permissão para fazer uma chamada."""
        with self._lock:
            now = time.time()
            # Remove chamadas antigas
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()
            
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            return False
    
    def wait_if_needed(self) -> float:
        """Espera se necessário e retorna tempo de espera."""
        with self._lock:
            now = time.time()
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()
            
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return 0.0
            
            # Calcula tempo de espera
            oldest = self.calls[0]
            wait_time = max(0, (oldest + self.time_window) - now)
            return wait_time


class SmartCache:
    """Cache inteligente com TTL e tamanho máximo."""
    
    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = threading.RLock()
    
    def _get_key(self, prefix: str, *args, **kwargs) -> str:
        """Gera chave de cache a partir dos argumentos."""
        content = f"{prefix}:{str(args)}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Recupera valor do cache."""
        key = self._get_key(prefix, *args, **kwargs)
        with self._lock:
            if key in self._cache:
                value, expires = self._cache[key]
                if expires > datetime.now():
                    return value
                else:
                    del self._cache[key]
        return None
    
    def set(self, value: Any, prefix: str, ttl_seconds: Optional[int] = None, *args, **kwargs):
        """Armazena valor no cache."""
        key = self._get_key(prefix, *args, **kwargs)
        ttl = ttl_seconds or self.default_ttl
        expires = datetime.now() + timedelta(seconds=ttl)
        
        with self._lock:
            # Se cache está cheio, remove o item mais antigo
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest = min(self._cache.items(), key=lambda x: x[1][1])
                del self._cache[oldest[0]]
            
            self._cache[key] = (value, expires)
    
    def clear(self):
        """Limpa todo o cache."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "usage_percent": round(len(self._cache) / self.max_size * 100, 2)
            }


class ExternalServices:
    """
    Gerencia chamadas a serviços externos com cache, rate limiting e fallbacks.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        # Configurações
        self.xai_api_key: Optional[str] = os.getenv("XAI_API_KEY")
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.news_api_key: Optional[str] = os.getenv("NEWS_API_KEY")
        self.github_token: Optional[str] = os.getenv("GITHUB_TOKEN")
        
        # Cache e rate limiting
        self.cache = SmartCache(max_size=500, default_ttl_seconds=3600)
        self.rate_limiters: Dict[str, RateLimiter] = {
            "grok": RateLimiter(max_calls=30, time_window_seconds=60),
            "openai": RateLimiter(max_calls=60, time_window_seconds=60),
            "newsapi": RateLimiter(max_calls=100, time_window_seconds=60),
            "github": RateLimiter(max_calls=5000, time_window_seconds=3600),
        }
        
        # Métricas
        self.metrics: Dict[str, ServiceMetrics] = {
            "grok": ServiceMetrics(),
            "openai": ServiceMetrics(),
            "anthropic": ServiceMetrics(),
            "gemini": ServiceMetrics(),
            "newsapi": ServiceMetrics(),
            "github": ServiceMetrics(),
        }
        
        # Sessão HTTP com retry
        self.session = self._create_session()
        
        # Cache persistence
        self.cache_dir = cache_dir or Path("atena_evolution/cache/services")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("🔌 ExternalServices v3.0 inicializado")
        logger.info(f"   Grok: {'✅' if self.xai_api_key else '❌'}")
        logger.info(f"   OpenAI: {'✅' if self.openai_api_key else '❌'}")
        logger.info(f"   Anthropic: {'✅' if self.anthropic_api_key else '❌'}")
        logger.info(f"   Gemini: {'✅' if self.gemini_api_key else '❌'}")
        logger.info(f"   NewsAPI: {'✅' if self.news_api_key else '❌'}")
        logger.info(f"   GitHub: {'✅' if self.github_token else '❌'}")
    
    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com retry e pooling."""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=retry_strategy
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": "ATENA-Omega/3.3",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        })
        
        return session
    
    def _call_with_retry(
        self,
        func: Callable,
        service: str,
        max_retries: int = 3,
        fallback_value: Any = None
    ) -> Any:
        """Executa chamada com retry e fallback."""
        for attempt in range(max_retries):
            start_time = time.time()
            
            try:
                # Verifica rate limit
                limiter = self.rate_limiters.get(service)
                if limiter:
                    wait_time = limiter.wait_if_needed()
                    if wait_time > 0:
                        time.sleep(wait_time)
                
                result = func()
                latency_ms = (time.time() - start_time) * 1000
                self.metrics[service].record_success(latency_ms)
                return result
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self.metrics[service].record_failure(str(e))
                logger.warning(f"Chamada {service} falhou (tentativa {attempt+1}): {e}")
                
                if attempt == max_retries - 1:
                    if fallback_value is not None:
                        return fallback_value
                    raise
                
                time.sleep(2 ** attempt)  # Backoff exponencial
        
        return fallback_value
    
    # =========================================================================
    # LLM PROVIDERS
    # =========================================================================
    
    def call_grok(
        self,
        prompt: str,
        model: str = "grok-beta",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Chama a API do Grok (xAI) para geração de texto.
        
        Args:
            prompt: Prompt de entrada
            model: Modelo a usar (grok-beta, grok-1)
            max_tokens: Número máximo de tokens
            temperature: Temperatura (0-1)
            use_cache: Se deve usar cache
        """
        if not self.xai_api_key:
            logger.warning("XAI_API_KEY não configurada — Grok indisponível")
            return self._fallback_llm(prompt)
        
        cache_key = f"grok:{model}:{prompt}:{max_tokens}:{temperature}"
        
        if use_cache:
            cached = self.cache.get("grok", prompt, model, max_tokens, temperature)
            if cached:
                self.metrics["grok"].record_cache_hit()
                return cached
        
        self.metrics["grok"].record_cache_miss()
        
        def _call():
            response = self.session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.xai_api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are ATENA, an advanced AI assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        
        result = self._call_with_retry(_call, "grok", fallback_value=self._fallback_llm(prompt))
        
        if result and use_cache:
            self.cache.set(result, "grok", ttl_seconds=3600, prompt=prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        
        return result
    
    def call_openai(
        self,
        prompt: str,
        model: str = "gpt-4-turbo-preview",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Chama a API da OpenAI."""
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY não configurada — OpenAI indisponível")
            return self._fallback_llm(prompt)
        
        if use_cache:
            cached = self.cache.get("openai", prompt, model, max_tokens, temperature)
            if cached:
                self.metrics["openai"].record_cache_hit()
                return cached
        
        self.metrics["openai"].record_cache_miss()
        
        def _call():
            response = self.session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        
        result = self._call_with_retry(_call, "openai", fallback_value=self._fallback_llm(prompt))
        
        if result and use_cache:
            self.cache.set(result, "openai", ttl_seconds=3600, prompt=prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        
        return result
    
    def call_best_llm(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        preferred: List[str] = None
    ) -> Optional[str]:
        """
        Chama o melhor LLM disponível, com fallback automático.
        
        Args:
            prompt: Prompt de entrada
            max_tokens: Número máximo de tokens
            temperature: Temperatura
            preferred: Lista de provedores preferidos (ex: ["grok", "openai"])
        """
        preferred = preferred or ["grok", "openai", "anthropic", "gemini"]
        
        for provider in preferred:
            if provider == "grok" and self.xai_api_key:
                result = self.call_grok(prompt, max_tokens=max_tokens, temperature=temperature)
                if result:
                    return result
            elif provider == "openai" and self.openai_api_key:
                result = self.call_openai(prompt, max_tokens=max_tokens, temperature=temperature)
                if result:
                    return result
            elif provider == "anthropic" and self.anthropic_api_key:
                result = self.call_anthropic(prompt, max_tokens=max_tokens, temperature=temperature)
                if result:
                    return result
            elif provider == "gemini" and self.gemini_api_key:
                result = self.call_gemini(prompt, max_tokens=max_tokens, temperature=temperature)
                if result:
                    return result
        
        return self._fallback_llm(prompt)
    
    def call_anthropic(
        self,
        prompt: str,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Chama a API da Anthropic (Claude)."""
        if not self.anthropic_api_key:
            return self._fallback_llm(prompt)
        
        if use_cache:
            cached = self.cache.get("anthropic", prompt, model, max_tokens, temperature)
            if cached:
                return cached
        
        def _call():
            response = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        
        result = self._call_with_retry(_call, "anthropic", fallback_value=self._fallback_llm(prompt))
        
        if result and use_cache:
            self.cache.set(result, "anthropic", ttl_seconds=3600, prompt=prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        
        return result
    
    def call_gemini(
        self,
        prompt: str,
        model: str = "gemini-pro",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Chama a API do Google Gemini."""
        if not self.gemini_api_key:
            return self._fallback_llm(prompt)
        
        if use_cache:
            cached = self.cache.get("gemini", prompt, model, max_tokens, temperature)
            if cached:
                return cached
        
        def _call():
            response = self.session.post(
                f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
                params={"key": self.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        
        result = self._call_with_retry(_call, "gemini", fallback_value=self._fallback_llm(prompt))
        
        if result and use_cache:
            self.cache.set(result, "gemini", ttl_seconds=3600, prompt=prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        
        return result
    
    def _fallback_llm(self, prompt: str) -> str:
        """Fallback local quando APIs não estão disponíveis."""
        prompt_lower = prompt.lower()
        
        # Templates de resposta local
        if "olá" in prompt_lower or "hello" in prompt_lower:
            return "Olá! Sou a ATENA, seu assistente de IA. Infelizmente o serviço de LLM remoto não está disponível no momento. Estou operando em modo offline com capacidades limitadas."
        
        if "ajuda" in prompt_lower or "help" in prompt_lower:
            return """## ATENA - Modo Offline

Estou operando em modo offline. Disponho das seguintes capacidades:

1. **Pesquisa na internet** - Use `/internet <tema>`
2. **Execução de tarefas** - Use `/task-exec <objetivo>`
3. **Auto-evolução** - Use `/self-test` para diagnóstico
4. **Documentação** - Consulte docs/ para informações

Para funcionalidades completas, configure as chaves de API."""
        
        return f"Processando solicitação em modo offline...\n\n**Nota:** APIs de LLM não configuradas. Configure XAI_API_KEY, OPENAI_API_KEY ou similar para respostas avançadas.\n\nPrompt recebido: {prompt[:200]}..."
    
    # =========================================================================
    # NEWS API
    # =========================================================================
    
    def fetch_news(
        self,
        query: str,
        page_size: int = 5,
        use_cache: bool = True,
        language: str = "en"
    ) -> List[Dict]:
        """
        Busca notícias via NewsAPI.
        
        Args:
            query: Termo de busca
            page_size: Número de resultados
            use_cache: Se deve usar cache
            language: Idioma (en, pt, es, etc.)
        """
        if not self.news_api_key:
            logger.warning("NEWS_API_KEY não configurada — NewsAPI indisponível")
            return []
        
        if use_cache:
            cached = self.cache.get("newsapi", query, page_size, language)
            if cached:
                self.metrics["newsapi"].record_cache_hit()
                return cached
        
        self.metrics["newsapi"].record_cache_miss()
        
        def _call():
            response = self.session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "pageSize": page_size,
                    "apiKey": self.news_api_key,
                    "language": language,
                    "sortBy": "publishedAt",
                },
                timeout=15,
            )
            response.raise_for_status()
            return response.json().get("articles", [])
        
        result = self._call_with_retry(_call, "newsapi", fallback_value=[])
        
        if result and use_cache:
            self.cache.set(result, "newsapi", ttl_seconds=1800, query=query, page_size=page_size, language=language)
        
        return result
    
    # =========================================================================
    # GITHUB API
    # =========================================================================
    
    def search_github_repos(
        self,
        query: str,
        per_page: int = 10,
        sort: str = "stars",
        use_cache: bool = True
    ) -> List[Dict]:
        """Busca repositórios no GitHub."""
        if not self.github_token:
            logger.warning("GITHUB_TOKEN não configurado")
            return []
        
        if use_cache:
            cached = self.cache.get("github", query, per_page, sort)
            if cached:
                self.metrics["github"].record_cache_hit()
                return cached
        
        self.metrics["github"].record_cache_miss()
        
        def _call():
            response = self.session.get(
                "https://api.github.com/search/repositories",
                headers={"Authorization": f"token {self.github_token}"},
                params={
                    "q": query,
                    "per_page": per_page,
                    "sort": sort,
                    "order": "desc",
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("items", [])
        
        result = self._call_with_retry(_call, "github", fallback_value=[])
        
        if result and use_cache:
            self.cache.set(result, "github", ttl_seconds=7200, query=query, per_page=per_page, sort=sort)
        
        return result
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de todos os serviços."""
        return {
            service: metrics.to_dict()
            for service, metrics in self.metrics.items()
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        return {
            "cache": self.cache.get_stats(),
            "rate_limiters": {
                name: {
                    "calls_remaining": limiter.max_calls - len(limiter.calls),
                    "window_seconds": limiter.time_window,
                }
                for name, limiter in self.rate_limiters.items()
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Retorna o status detalhado dos serviços."""
        return {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "grok": {
                    "available": bool(self.xai_api_key),
                    "metrics": self.metrics["grok"].to_dict(),
                },
                "openai": {
                    "available": bool(self.openai_api_key),
                    "metrics": self.metrics["openai"].to_dict(),
                },
                "anthropic": {
                    "available": bool(self.anthropic_api_key),
                    "metrics": self.metrics["anthropic"].to_dict(),
                },
                "gemini": {
                    "available": bool(self.gemini_api_key),
                    "metrics": self.metrics["gemini"].to_dict(),
                },
                "news_api": {
                    "available": bool(self.news_api_key),
                    "metrics": self.metrics["newsapi"].to_dict(),
                },
                "github": {
                    "available": bool(self.github_token),
                    "metrics": self.metrics["github"].to_dict(),
                },
            },
            "cache_stats": self.get_cache_stats(),
        }
    
    def clear_cache(self):
        """Limpa todo o cache."""
        self.cache.clear()
        logger.info("🗑️ Cache de serviços limpo")


# Instância global para uso em toda a aplicação
services = ExternalServices()


# =============================================================================
# DEMONSTRAÇÃO
# =============================================================================

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    
    print("🔌 ExternalServices v3.0 - Demonstração")
    print("=" * 50)
    
    # Verifica saúde
    health = services.health_check()
    print(f"\n📊 Status dos Serviços:")
    for name, info in health["services"].items():
        status = "✅" if info["available"] else "❌"
        print(f"  {status} {name}: {info['metrics']['success_rate']*100:.1f}% sucesso")
    
    # Exemplo de chamada
    print("\n💬 Testando LLM (modo offline fallback):")
    result = services.call_best_llm("Olá, me ajude com Python")
    print(f"\n{result}")
    
    # Métricas
    print(f"\n📈 Métricas do Cache:")
    cache_stats = services.get_cache_stats()
    print(f"  Tamanho do cache: {cache_stats['cache']['size']}/{cache_stats['cache']['max_size']}")
    
    for service, metrics in services.get_metrics().items():
        if metrics["total_calls"] > 0:
            print(f"\n🔍 {service.upper()}:")
            print(f"  Chamadas: {metrics['total_calls']} | Taxa de sucesso: {metrics['success_rate']*100:.1f}%")
            print(f"  Latência média: {metrics['avg_latency_ms']:.2f}ms | Cache hit: {metrics['cache_hit_rate']*100:.1f}%")


if __name__ == "__main__":
    main()
