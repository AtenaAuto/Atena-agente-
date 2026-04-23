#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modules/services.py — Serviços auxiliares da ATENA Ω
Fornece utilitários de integração com APIs externas e serviços locais.

NOTA: Este arquivo foi recriado pois o original continha código TypeScript/JavaScript
      que impedia a importação pelo Python.
"""

import os
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ExternalServices:
    """Gerencia chamadas a serviços externos (APIs, webhooks, etc.)."""

    def __init__(self):
        self.xai_api_key: Optional[str] = os.getenv("XAI_API_KEY")
        self.news_api_key: Optional[str] = os.getenv("NEWS_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ATENA-Omega/3.3"})

    def call_grok(
        self,
        prompt: str,
        model: str = "grok-beta",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Chama a API do Grok (xAI) para geração de texto."""
        if not self.xai_api_key:
            logger.warning("XAI_API_KEY não configurada — Grok indisponível")
            return None
        try:
            resp = self.session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.xai_api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Erro ao chamar Grok: {e}")
            return None

    def fetch_news(self, query: str, page_size: int = 5) -> List[Dict]:
        """Busca notícias via NewsAPI."""
        if not self.news_api_key:
            logger.warning("NEWS_API_KEY não configurada — NewsAPI indisponível")
            return []
        try:
            resp = self.session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "pageSize": page_size,
                    "apiKey": self.news_api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as e:
            logger.error(f"Erro ao buscar notícias: {e}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """Retorna o status dos serviços configurados."""
        return {
            "grok_available": bool(self.xai_api_key),
            "news_api_available": bool(self.news_api_key),
        }


# Instância global para uso nos módulos
services = ExternalServices()
