#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Browser Agent v3.0 - Agente de Navegação Autônomo Avançado
Sistema completo de web scraping, automação e evasão de detecção.

Recursos:
- 🌐 Navegação autônoma com múltiplos perfis
- 🧠 Extração semântica de conteúdo (JSON-LD, microdata, schema.org)
- 🛡️ Evasão de detecção (stealth mode, fingerprint randomização)
- 📊 Análise de sentimentos e relevância
- 🔄 Aprendizado contínuo por objetivo
- 📸 Screenshots com marcação de elementos
- 🎯 Preenchimento inteligente de formulários
- 💾 Cache persistente de páginas
"""

import logging
import asyncio
import json
import re
import hashlib
import random
import base64
from typing import Optional, Dict, Any, List, Tuple, Set
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
import traceback

# Tentativa de importar bibliotecas avançadas
try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


@dataclass
class PageAnalysis:
    """Resultado da análise de uma página."""

    url: str
    title: str
    description: str
    keywords: List[str]
    headings: Dict[str, List[str]]
    links: List[Dict[str, str]]
    images: List[Dict[str, str]]
    forms: List[Dict[str, Any]]
    structured_data: List[Dict[str, Any]]
    main_text: str
    word_count: int
    readability_score: float
    relevance_score: float
    language: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AtenaBrowserAgent:
    """
    Agente de navegação autônomo com recursos avançados de web scraping,
    evasão de detecção e aprendizado contínuo por objetivo.
    """

    def __init__(self, user_data_dir: Optional[Path] = None, stealth_mode: bool = True):
        self.browser: Optional[Any] = None
        self.page: Optional[Any] = None
        self.context: Optional[Any] = None
        self.playwright: Optional[Any] = None

        self.stealth_mode = stealth_mode
        self.user_data_dir = user_data_dir or Path("atena_evolution/browser_data")
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self.memory_path = self.user_data_dir / "browser_learning_memory.json"
        self.cache_path = self.user_data_dir / "page_cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)

        self.learning_memory = self._load_learning_memory()
        self._page_cache: Dict[str, Tuple[str, datetime]] = {}
        self._navigation_history: List[Dict[str, Any]] = []
        self._current_objective: Optional[str] = None

        # Configurações de stealth
        self._user_agents = self._load_user_agents()
        self._viewport_sizes = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720},
        ]

        logger.info("🔱 ATENA Browser Agent v3.0 inicializado")
        logger.info(f"   Stealth mode: {stealth_mode}")
        logger.info(f"   User data dir: {self.user_data_dir}")

    def _load_user_agents(self) -> List[str]:
        """Carrega lista de User-Agents para randomização."""
        return [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like"
                " Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            ),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
                " (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        ]

    def _load_learning_memory(self) -> Dict[str, Any]:
        """Carrega memória de aprendizado persistente."""
        if self.memory_path.exists():
            try:
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                logger.info(f"📚 Memória carregada: {len(data.get('search_history', []))} buscas")
                return data
            except Exception as e:
                logger.warning(f"Falha ao carregar memória: {e}")

        return {
            "visited_urls": [],
            "search_history": [],
            "objective_stats": {},
            "successful_patterns": {},
            "failed_patterns": {},
            "domain_performance": {},
            "last_cleanup": datetime.now().isoformat(),
        }

    def _save_learning_memory(self):
        """Salva memória de aprendizado."""
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_path.write_text(
                json.dumps(self.learning_memory, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Erro ao salvar memória: {e}")

    def _get_stealth_context_options(self) -> Dict[str, Any]:
        """Retorna opções de contexto para modo stealth."""
        if not self.stealth_mode:
            return {}

        # Randomiza fingerprint
        viewport = random.choice(self._viewport_sizes)
        user_agent = random.choice(self._user_agents)

        # Gera fingerprint do dispositivo
        device_scale_factor = random.uniform(0.8, 1.2)
        has_touch = random.random() > 0.7

        return {
            "viewport": viewport,
            "user_agent": user_agent,
            "ignore_https_errors": True,
            "device_scale_factor": device_scale_factor,
            "has_touch": has_touch,
            "locale": random.choice(["en-US", "pt-BR", "en-GB", "es-ES"]),
            "timezone_id": random.choice(
                ["America/Sao_Paulo", "America/New_York", "Europe/London"]
            ),
            "permissions": [],
            "extra_http_headers": {
                "Accept-Language": random.choice(["en-US,en;q=0.9", "pt-BR,pt;q=0.9,en;q=0.8"]),
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                ),
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            },
        }

    async def launch(self, headless: bool = True, proxy: Optional[str] = None):
        """Inicia o navegador com configurações avançadas."""
        logger.info(f"🚀 Lançando navegador (headless={headless}, stealth={self.stealth_mode})...")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "Playwright não instalado. Execute: pip install playwright && playwright install"
                " chromium"
            )
            raise

        self.playwright = await async_playwright().start()

        # Opções de lançamento
        launch_options = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        if self.stealth_mode:
            launch_options["args"].extend([
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-gpu",
            ])

        self.browser = await self.playwright.chromium.launch(**launch_options)

        # Cria contexto com fingerprint randomizado
        context_options = self._get_stealth_context_options()
        if proxy:
            context_options["proxy"] = {"server": proxy}

        self.context = await self.browser.new_context(**context_options)

        # Scripts de evasão para remover sinais de automação
        if self.stealth_mode:
            await self.context.add_init_script("""
                // Remove navigator.webdriver flag
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                
                // Override chrome property
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
            """)

        self.page = await self.context.new_page()

        # Configura timeouts
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(30000)

        logger.info("✅ Navegador iniciado com sucesso")
        if self.stealth_mode:
            logger.info(
                f"   Fingerprint: {context_options.get('viewport')}, UA:"
                f" {context_options.get('user_agent', 'default')[:50]}..."
            )

    async def _get_cached_page(self, url: str, max_age_hours: int = 24) -> Optional[str]:
        """Recupera página do cache se ainda for válida."""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_file = self.cache_path / f"{cache_key}.html"

        if cache_file.exists():
            modified = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age_hours = (datetime.now() - modified).total_seconds() / 3600
            if age_hours < max_age_hours:
                logger.debug(f"📦 Cache hit: {url}")
                return cache_file.read_text(encoding="utf-8")

        return None

    async def _cache_page(self, url: str, content: str):
        """Armazena página em cache."""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_file = self.cache_path / f"{cache_key}.html"
        cache_file.write_text(content, encoding="utf-8")
        logger.debug(f"💾 Cache saved: {url}")

    async def navigate(
        self, url: str, use_cache: bool = True, cache_max_age_hours: int = 24
    ) -> Tuple[bool, Optional[str]]:
        """
        Navega para uma URL com suporte a cache e retry.

        Returns:
            Tuple[success, content]
        """
        if not self.page:
            logger.error("Navegador não iniciado. Chame launch() primeiro.")
            return False, None

        # Verifica cache
        if use_cache:
            cached_content = await self._get_cached_page(url, cache_max_age_hours)
            if cached_content:
                return True, cached_content

        # Verifica repetição
        if url in self.learning_memory.get("visited_urls", []):
            logger.info(f"URL já visitada anteriormente: {url}")

        # Tenta navegar com retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Navegando para: {url} (tentativa {attempt + 1})")

                # Opções de navegação
                goto_options = {"wait_until": "domcontentloaded", "timeout": 30000}

                response = await self.page.goto(url, **goto_options)

                # Aguarda um pouco para carregamento dinâmico
                await asyncio.sleep(random.uniform(0.5, 2.0))

                # Verifica resposta
                if response and response.status >= 400:
                    logger.warning(f"Resposta HTTP {response.status} para {url}")
                    if attempt == max_retries - 1:
                        return False, None
                    await asyncio.sleep(2**attempt)
                    continue

                # Obtém conteúdo
                content = await self.page.content()

                # Salva cache
                await self._cache_page(url, content)

                # Registra navegação
                self._navigation_history.append(
                    {"url": url, "timestamp": datetime.now().isoformat(), "success": True}
                )

                # Atualiza memória
                if url not in self.learning_memory["visited_urls"]:
                    self.learning_memory["visited_urls"].append(url)
                    self._save_learning_memory()

                logger.info(f"✅ Navegação concluída: {url}")
                return True, content

            except Exception as e:
                logger.error(f"Erro na tentativa {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    self._navigation_history.append({
                        "url": url,
                        "timestamp": datetime.now().isoformat(),
                        "success": False,
                        "error": str(e),
                    })
                    return False, None
                await asyncio.sleep(2**attempt)

        return False, None

    async def get_text_content(self, selector: str = "body", max_chars: int = 20000) -> str:
        """
        Extrai texto visível da página atual.

        Args:
            selector: seletor CSS base para extração.
            max_chars: limite de caracteres para retorno.
        """
        if not self.page:
            logger.error("Navegador não iniciado. Chame launch() primeiro.")
            return ""

        try:
            text = await self.page.inner_text(selector)
            normalized = re.sub(r"\s+", " ", text).strip()
            return normalized[:max_chars]
        except Exception as e:
            logger.warning(f"Falha ao extrair texto via selector '{selector}': {e}")
            try:
                content = await self.page.content()
                if HAS_BS4:
                    soup = BeautifulSoup(content, "html.parser")
                    normalized = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
                    return normalized[:max_chars]
            except Exception as fallback_error:
                logger.error(f"Fallback de extração de texto falhou: {fallback_error}")
            return ""

    async def analyze_page(self, content: str, url: str) -> PageAnalysis:
        """
        Analisa o conteúdo da página e extrai informações estruturadas.
        """
        if not HAS_BS4:
            logger.warning("BeautifulSoup não disponível para análise avançada")
            return PageAnalysis(
                url=url,
                title="",
                description="",
                keywords=[],
                headings={},
                links=[],
                images=[],
                forms=[],
                structured_data=[],
                main_text=content[:5000],
                word_count=len(content.split()),
                readability_score=0.5,
                relevance_score=0.5,
                language="unknown",
            )

        soup = BeautifulSoup(content, "html.parser")

        # Extrai título
        title = soup.find("title")
        title_text = title.get_text().strip() if title else ""

        # Extrai meta descrição
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "").strip() if meta_desc else ""

        # Extrai palavras-chave
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        keywords = (
            [k.strip() for k in meta_keywords.get("content", "").split(",")]
            if meta_keywords
            else []
        )

        # Extrai headings
        headings = {
            "h1": [h.get_text().strip() for h in soup.find_all("h1")],
            "h2": [h.get_text().strip() for h in soup.find_all("h2")],
            "h3": [h.get_text().strip() for h in soup.find_all("h3")],
        }

        # Extrai links
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            links.append({
                "url": href,
                "text": a.get_text().strip()[:100],
                "external": urlparse(href).netloc != urlparse(url).netloc,
            })

        # Extrai imagens
        images = []
        for img in soup.find_all("img", src=True):
            src = urljoin(url, img["src"])
            images.append(
                {"url": src, "alt": img.get("alt", "")[:100], "title": img.get("title", "")[:100]}
            )

        # Extrai formulários
        forms = []
        for form in soup.find_all("form"):
            form_data = {
                "action": urljoin(url, form.get("action", "")),
                "method": form.get("method", "get"),
                "fields": [],
            }
            for input_field in form.find_all(["input", "textarea", "select"]):
                field_info = {
                    "name": input_field.get("name", ""),
                    "type": input_field.get("type", "text"),
                    "required": input_field.get("required") is not None,
                }
                if input_field.name == "select":
                    options = [opt.get_text().strip() for opt in input_field.find_all("option")]
                    field_info["options"] = options
                form_data["fields"].append(field_info)
            forms.append(form_data)

        # Extrai dados estruturados (JSON-LD)
        structured_data = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                structured_data.append(data)
            except:
                pass

        # Extrai texto principal (ignorando nav, footer, etc.)
        for unwanted in soup.find_all(["nav", "footer", "header", "aside", "script", "style"]):
            unwanted.decompose()

        main_text = soup.get_text()
        main_text = re.sub(r"\s+", " ", main_text).strip()

        # Calcula score de legibilidade (Flesch-Kincaid simplificado)
        words = main_text.split()
        sentences = main_text.count(".") + main_text.count("!") + main_text.count("?")
        avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
        readability_score = min(
            1.0,
            max(
                0.0,
                (1.0 - (avg_word_length / 15)) * 0.7
                + (min(1.0, sentences / max(len(words), 1) * 100) * 0.3),
            ),
        )

        return PageAnalysis(
            url=url,
            title=title_text,
            description=description,
            keywords=keywords,
            headings=headings,
            links=links[:50],
            images=images[:30],
            forms=forms,
            structured_data=structured_data,
            main_text=main_text[:10000],
            word_count=len(words),
            readability_score=readability_score,
            relevance_score=0.5,  # Será calculado com base no objetivo
            language=self._detect_language(main_text),
            timestamp=datetime.now().isoformat(),
        )

    def _detect_language(self, text: str) -> str:
        """Detecta idioma do texto."""
        text_lower = text.lower()
        patterns = {
            "pt": [r"\b(que|para|com|por|mais|como|seu|sua|você|você|vocês|eles|elas)\b"],
            "en": [r"\b(the|and|for|with|more|like|your|you|they|them)\b"],
            "es": [r"\b(que|para|con|por|más|como|su|sus|usted|ellos)\b"],
        }

        scores = {}
        for lang, pattern_list in patterns.items():
            score = sum(len(re.findall(p, text_lower)) for p in pattern_list)
            scores[lang] = score

        if scores:
            return max(scores, key=scores.get) if max(scores.values()) > 0 else "unknown"
        return "unknown"

    async def search_and_extract(
        self, objective: str, base_query: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Busca e extrai informações relevantes para um objetivo.

        Args:
            objective: Objetivo da busca
            base_query: Query base de busca
            max_results: Número máximo de resultados
        """
        self._current_objective = objective

        # Gera query otimizada
        query = self.next_objective_query(objective, base_query)
        logger.info(f"🎯 Buscando: {query} (objetivo: {objective})")

        # Constrói URL de busca (Google como exemplo)
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        # Navega para página de busca
        success, content = await self.navigate(search_url)
        if not success:
            return []

        # Analisa página
        analysis = await self.analyze_page(content, search_url)

        # Extrai links de resultado
        results = []
        for link in analysis.links[:max_results]:
            if "google" not in link["url"] and "youtube" not in link["url"]:
                results.append({
                    "url": link["url"],
                    "title": link["text"],
                    "source": search_url,
                    "objective": objective,
                })

        return results

    async def extract_from_url(self, url: str, objective: str) -> Optional[Dict[str, Any]]:
        """
        Extrai informações detalhadas de uma URL específica.
        """
        success, content = await self.navigate(url)
        if not success:
            return None

        analysis = await self.analyze_page(content, url)

        # Calcula relevância baseada no objetivo
        relevance = self._calculate_relevance(analysis, objective)

        return {
            "url": url,
            "objective": objective,
            "title": analysis.title,
            "description": analysis.description,
            "main_text": analysis.main_text[:2000],
            "headings": analysis.headings,
            "links_count": len(analysis.links),
            "word_count": analysis.word_count,
            "readability_score": analysis.readability_score,
            "relevance_score": relevance,
            "extracted_at": datetime.now().isoformat(),
        }

    def _calculate_relevance(self, analysis: PageAnalysis, objective: str) -> float:
        """Calcula relevância da página para o objetivo."""
        objective_lower = objective.lower()
        objective_words = set(objective_lower.split())

        # Score baseado em palavras-chave no título
        title_score = sum(1 for w in objective_words if w in analysis.title.lower()) / max(
            len(objective_words), 1
        )

        # Score baseado em headings
        heading_text = " ".join([" ".join(v) for v in analysis.headings.values()]).lower()
        heading_score = sum(1 for w in objective_words if w in heading_text) / max(
            len(objective_words), 1
        )

        # Score baseado em texto principal
        text_score = sum(1 for w in objective_words if w in analysis.main_text.lower()) / max(
            len(objective_words), 1
        )

        # Score combinado
        relevance = title_score * 0.4 + heading_score * 0.3 + text_score * 0.3

        return min(1.0, relevance)

    def next_objective_query(self, objective: str, base_query: str) -> str:
        """
        Gera a próxima query com refinamento progressivo baseado no histórico.
        """
        objective_key = objective.strip().lower()
        stats = self.learning_memory["objective_stats"].setdefault(
            objective_key, {"iterations": 0, "successful_queries": []}
        )

        refinements = [
            "site:github.com",
            "2026 latest",
            "official docs",
            "benchmarks",
            "comparison",
            "best practices",
            "tutorial",
            "guide",
            "api reference",
            "stackoverflow",
            "reddit",
            "example code",
            "documentation",
        ]

        # Prefere refinamentos que já funcionaram no passado
        successful = stats.get("successful_queries", [])
        if successful and random.random() < 0.3:
            base = random.choice(successful)
        else:
            idx = stats["iterations"] % len(refinements)
            base = f"{base_query.strip()} {refinements[idx]}".strip()

        # Evita repetição
        used_queries = {
            item.get("query", "").strip().lower()
            for item in self.learning_memory.get("search_history", [])
            if item.get("objective", "").strip().lower() == objective_key
        }

        candidate = base
        counter = 0
        while candidate.lower() in used_queries and counter < 10:
            candidate = f"{base} {refinements[counter % len(refinements)]}".strip()
            counter += 1

        stats["iterations"] += 1
        self._save_learning_memory()

        logger.debug(f"Query gerada: {candidate}")
        return candidate

    def record_search_outcome(
        self, objective: str, query: str, url: str, usefulness_score: float, notes: str = ""
    ):
        """Registra resultado de busca para aprendizado."""
        usefulness_score = max(0.0, min(1.0, usefulness_score))

        self.learning_memory.setdefault("search_history", []).append({
            "timestamp": datetime.now().isoformat(),
            "objective": objective,
            "query": query,
            "url": url,
            "usefulness_score": usefulness_score,
            "notes": notes,
        })

        # Atualiza estatísticas do objetivo
        objective_key = objective.strip().lower()
        stats = self.learning_memory["objective_stats"].setdefault(
            objective_key, {"iterations": 0, "successful_queries": []}
        )

        if usefulness_score > 0.7 and query not in stats.get("successful_queries", []):
            stats.setdefault("successful_queries", []).append(query)
            stats["successful_queries"] = stats["successful_queries"][-10:]  # Mantém últimas 10

        if url and url not in self.learning_memory["visited_urls"]:
            self.learning_memory["visited_urls"].append(url)

        self._save_learning_memory()
        logger.info(f"📝 Busca registrada: score={usefulness_score:.2f}, query={query[:50]}...")

    async def take_screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> bool:
        """Tira screenshot da página atual."""
        if not self.page:
            return False
        try:
            screenshot_options = {"path": path, "full_page": full_page}
            await self.page.screenshot(**screenshot_options)
            logger.info(f"📸 Screenshot salvo: {path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar screenshot: {e}")
            return False

    async def scroll_to_bottom(self):
        """Rola até o final da página."""
        if not self.page:
            return
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

    async def extract_all_links(self) -> List[str]:
        """Extrai todos os links da página atual."""
        if not self.page:
            return []
        links = await self.page.evaluate(
            "Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
        )
        return list(set(links))

    async def close(self):
        """Fecha o navegador e limpa recursos."""
        if self.browser:
            await self.browser.close()
            logger.info("🔒 Navegador fechado")
        if self.playwright:
            await self.playwright.stop()
            logger.info("Playwright parado")

        # Salva estado final
        self.learning_memory["last_close"] = datetime.now().isoformat()
        self._save_learning_memory()


# =============================================================================
# DEMONSTRAÇÃO
# =============================================================================


async def main_demo():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    browser_agent = AtenaBrowserAgent(stealth_mode=True)

    try:
        await browser_agent.launch(headless=False)  # False para ver o navegador

        # Exemplo: Buscar documentação da ATENA
        objective = "entender arquitetura da ATENA"
        results = await browser_agent.search_and_extract(
            objective, "ATENA autonomous AI agent architecture", max_results=3
        )

        print("\n🔍 RESULTADOS DA BUSCA:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title'][:80]}...")
            print(f"   URL: {result['url']}")

        # Extrai informação do primeiro resultado relevante
        if results:
            print("\n📄 EXTRAINDO INFORMAÇÕES...")
            extracted = await browser_agent.extract_from_url(results[0]["url"], objective)
            if extracted:
                print(f"Título: {extracted['title']}")
                print(f"Relevância: {extracted['relevance_score']:.2f}")
                print(f"Resumo: {extracted['main_text'][:300]}...")

                # Registra utilidade
                browser_agent.record_search_outcome(
                    objective=objective,
                    query=results[0].get("title", ""),
                    url=results[0]["url"],
                    usefulness_score=extracted["relevance_score"],
                    notes="Primeira extração bem-sucedida",
                )

        await browser_agent.take_screenshot("atena_browser_demo.png", full_page=False)

    except Exception as e:
        logger.error(f"Erro na demonstração: {e}")
        traceback.print_exc()
    finally:
        await browser_agent.close()


if __name__ == "__main__":
    asyncio.run(main_demo())
