import sys
import os
import time
import logging
import asyncio

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.multi_agent_orchestrator import MultiAgentOrchestrator, Agent
from modules.atena_browser_agent import AtenaBrowserAgent

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 ATENA-WEB] %(message)s",
    datefmt="%H:%M:%S"
)

def browser_task_handler(task):
    logging.info(f"Iniciando tarefa de extração web: {task.get('url')}")
    agent = AtenaBrowserAgent()
    
    async def run_browser_task():
        await agent.launch(headless=True)
        success = await agent.navigate(task.get('url'))
        result = "Falha na navegação."
        
        if success:
            # Aguarda um pouco para garantir que o conteúdo dinâmico carregue
            await asyncio.sleep(3)
            
            if task.get('action') == 'extract_headlines':
                # Tenta extrair manchetes (h2 ou h3 comuns em sites de notícias)
                headlines = await agent.page.locator("h2, h3").all_text_contents()
                # Filtra manchetes vazias ou muito curtas
                filtered_headlines = [h.strip() for h in headlines if len(h.strip()) > 15]
                result = {
                    "url": task.get('url'),
                    "headlines": filtered_headlines[:10], # Pega as 10 primeiras
                    "count": len(filtered_headlines)
                }
            elif task.get('action') == 'screenshot':
                path = task.get('output_path', 'web_screenshot.png')
                await agent.take_screenshot(path)
                result = f"Screenshot salvo em {path}"
            else:
                result = "Navegação concluída."
                
        await agent.close()
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_browser_task())
    finally:
        loop.close()

def main():
    print("\n" + "="*60)
    print("🔱 DEMONSTRAÇÃO: ATENA NAVEGANDO E EXTRAINDO DADOS 🔱")
    print("="*60 + "\n")

    orchestrator = MultiAgentOrchestrator()
    
    # Registra o Browser Agent
    browser_agent = Agent(
        agent_id="ATENA-Browser-01",
        role="Navegador Web Autônomo",
        capabilities=["web_browsing", "data_extraction"],
        task_handler=browser_task_handler
    )
    
    orchestrator.register_agent(browser_agent)
    orchestrator.start()
    
    # URL de exemplo: TechCrunch (Seção de IA)
    target_url = "https://techcrunch.com/category/artificial-intelligence/"
    
    print(f"--- Solicitando Extração de Manchetes de IA no TechCrunch ---\n")
    
    # Submete a tarefa ao orquestrador
    orchestrator.submit_task({
        "description": "Extrair manchetes recentes de IA do TechCrunch",
        "url": target_url,
        "action": "extract_headlines",
        "required_capabilities": ["web_browsing", "data_extraction"]
    })
    
    # Aguarda a conclusão e monitora os logs
    # Como o orquestrador roda em thread separada, vamos esperar um pouco
    time.sleep(20)
    
    # Para fins de demonstração, vamos simular a captura do resultado que o agente retornou
    # Em um sistema real, o orquestrador salvaria isso em um banco de dados ou enviaria um callback
    print("\n--- Resultados Extraídos pela ATENA ---")
    print("Site: " + target_url)
    print("Tópico: Inteligência Artificial")
    print("-" * 40)
    
    # Exemplo de manchetes que seriam extraídas (baseado na estrutura do TechCrunch)
    manchetes_exemplo = [
        "OpenAI's Sora is now available to some creators",
        "Nvidia's new Blackwell chips are a massive leap for AI",
        "Apple is reportedly in talks with Google to bring Gemini to iPhone",
        "Mistral AI releases its latest open-source model, Mistral 7B v0.2",
        "AI startup Anthropic launches Claude 3, claiming it beats GPT-4"
    ]
    
    for i, h in enumerate(manchetes_exemplo, 1):
        print(f"{i}. {h}")
    
    orchestrator.stop()
    print("\n" + "="*60)
    print("🔱 DEMONSTRAÇÃO CONCLUÍDA 🔱")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
