import logging
import asyncio
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class AtenaBrowserAgent:
    def __init__(self):
        self.browser: Optional[Any] = None
        self.page: Optional[Any] = None
        self.context: Optional[Any] = None # BrowserContext
        self.playwright: Optional[Any] = None
        self.memory_path = Path("atena_evolution/states/browser_learning_memory.json")
        self.learning_memory = self._load_learning_memory()

    def _load_learning_memory(self) -> Dict[str, Any]:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Falha ao carregar memória de browser: {e}")
        return {
            "visited_urls": [],
            "search_history": [],
            "objective_stats": {}
        }

    def _save_learning_memory(self):
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_path.write_text(
            json.dumps(self.learning_memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def next_objective_query(self, objective: str, base_query: str) -> str:
        """
        Gera a próxima query de forma determinística (sem random),
        com refinamento progressivo por objetivo e evitando repetição.
        """
        objective_key = objective.strip().lower()
        stats = self.learning_memory["objective_stats"].setdefault(
            objective_key, {"iterations": 0}
        )
        refinements = [
            "site:github.com",
            "2026 latest",
            "official docs",
            "benchmarks",
            "comparison",
            "best practices",
        ]
        idx = stats["iterations"] % len(refinements)
        candidate = f"{base_query.strip()} {refinements[idx]}".strip()

        used_queries = {
            item.get("query", "").strip().lower()
            for item in self.learning_memory.get("search_history", [])
            if item.get("objective", "").strip().lower() == objective_key
        }
        if candidate.lower() in used_queries:
            for extra in refinements:
                alt = f"{candidate} {extra}".strip()
                if alt.lower() not in used_queries:
                    candidate = alt
                    break
        stats["iterations"] += 1
        self._save_learning_memory()
        return candidate

    def record_search_outcome(
        self,
        objective: str,
        query: str,
        url: str,
        usefulness_score: float,
        notes: str = "",
    ):
        """Registra resultado para aprendizado contínuo orientado a objetivo."""
        usefulness_score = max(0.0, min(1.0, usefulness_score))
        self.learning_memory.setdefault("search_history", []).append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "objective": objective,
                "query": query,
                "url": url,
                "usefulness_score": usefulness_score,
                "notes": notes,
            }
        )
        if url and url not in self.learning_memory["visited_urls"]:
            self.learning_memory["visited_urls"].append(url)
        self._save_learning_memory()

    async def launch(self, headless: bool = True):
        """Inicia o navegador Chromium."""
        logger.info(f"Lançando navegador (headless={headless})...")
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(ignore_https_errors=True)
        self.page = await self.context.new_page()
        logger.info("Navegador iniciado com sucesso.")

    async def navigate(self, url: str, allow_repeat: bool = False) -> bool:
        """Navega para uma URL específica."""
        if not self.page:
            logger.error("Navegador não iniciado. Chame launch() primeiro.")
            return False
        if not allow_repeat and url in self.learning_memory.get("visited_urls", []):
            logger.info(f"URL já visitada anteriormente; pulando repetição: {url}")
            return False
        try:
            logger.info(f"Navegando para: {url}")
            await self.page.goto(url, wait_until="domcontentloaded")
            if url not in self.learning_memory["visited_urls"]:
                self.learning_memory["visited_urls"].append(url)
                self._save_learning_memory()
            logger.info(f"Navegação para {url} concluída.")
            return True
        except Exception as e:
            logger.error(f"Erro ao navegar para {url}: {e}")
            return False

    async def get_page_content(self) -> str:
        """Retorna o conteúdo HTML da página atual."""
        if not self.page:
            return ""
        return await self.page.content()

    async def get_text_content(self) -> str:
        """Retorna todo o texto visível da página atual."""
        if not self.page:
            return ""
        return await self.page.locator("body").text_content()

    async def take_screenshot(self, path: str = "screenshot.png") -> bool:
        """Tira um screenshot da página atual."""
        if not self.page:
            return False
        try:
            await self.page.screenshot(path=path)
            logger.info(f"Screenshot salvo em: {path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar screenshot em {path}: {e}")
            return False

    async def click_element(self, selector: str) -> bool:
        """Clica em um elemento usando um seletor CSS."""
        if not self.page:
            return False
        try:
            logger.info(f"Clicando no elemento: {selector}")
            await self.page.click(selector)
            logger.info(f"Elemento {selector} clicado.")
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em {selector}: {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """Digita texto em um campo usando um seletor CSS."""
        if not self.page:
            return False
        try:
            logger.info(f"Digitando \'{text}\' no elemento: {selector}")
            await self.page.fill(selector, text)
            logger.info(f"Texto digitado em {selector}.")
            return True
        except Exception as e:
            logger.error(f"Erro ao digitar em {selector}: {e}")
            return False

    async def close(self):
        """Fecha o navegador."""
        if self.browser:
            await self.browser.close()
            logger.info("Navegador fechado.")
        if self.playwright:
            await self.playwright.stop()
            logger.info("Playwright parado.")

# Exemplo de uso (para testes)
async def main_demo():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    browser_agent = AtenaBrowserAgent()
    try:
        await browser_agent.launch(headless=True)
        await browser_agent.navigate("https://github.com/AtenaAuto/ATENA-")
        await browser_agent.take_screenshot("github_atena.png")
        
        print("\n--- Conteúdo da Página (trecho) ---")
        text_content = await browser_agent.get_text_content()
        print(text_content[:500]) # Imprime os primeiros 500 caracteres

        # Exemplo de busca (se houver um campo de busca visível)
        # await browser_agent.type_text("input[name=\'q\']", "AtenaAI")
        # await browser_agent.page.press("input[name=\'q\']", "Enter")
        # await browser_agent.page.wait_for_load_state("networkidle")
        # await browser_agent.take_screenshot("github_search_results.png")

    except Exception as e:
        logger.error(f"Erro na demonstração do Browser Agent: {e}")
    finally:
        await browser_agent.close()

if __name__ == "__main__":
    asyncio.run(main_demo())
