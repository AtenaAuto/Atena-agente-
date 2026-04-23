import sys
import os
import asyncio
import logging

# Adiciona o caminho dos módulos
sys.path.append(os.path.join(os.getcwd(), 'modules'))
from atena_browser_agent import AtenaBrowserAgent

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 ATENA-GOOGLE] %(message)s",
    datefmt="%H:%M:%S"
)

async def search_google(query: str, screenshot_path: str = "google_search_result.png"):
    agent = AtenaBrowserAgent()
    logging.info(f"Iniciando pesquisa no Google: '{query}'")
    
    try:
        await agent.launch(headless=True)
        # Navega para o Google
        await agent.navigate("https://www.google.com")
        
        # Aguarda o campo de busca (seletor comum: name='q')
        logging.info("Localizando campo de busca e digitando...")
        await agent.page.wait_for_selector("textarea[name='q'], input[name='q']")
        
        # Digita a pesquisa e pressiona Enter
        await agent.page.fill("textarea[name='q'], input[name='q']", query)
        await agent.page.press("textarea[name='q'], input[name='q']", "Enter")
        
        # Aguarda os resultados carregarem
        logging.info("Aguardando resultados...")
        await agent.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2) # Pequena pausa para renderização
        
        # Tira um screenshot do resultado
        await agent.take_screenshot(screenshot_path)
        logging.info(f"Pesquisa concluída. Screenshot salvo em {screenshot_path}")
        
        # Extrai os títulos dos primeiros resultados
        results = await agent.page.locator("h3").all_text_contents()
        filtered_results = [r for r in results if len(r) > 5][:5]
        
        await agent.close()
        return {
            "success": True,
            "query": query,
            "results": filtered_results,
            "screenshot": screenshot_path
        }
    except Exception as e:
        logging.error(f"Erro durante a pesquisa: {e}")
        if agent.browser:
            await agent.close()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Inteligência Artificial ATENA"
        
    asyncio.run(search_google(query))
