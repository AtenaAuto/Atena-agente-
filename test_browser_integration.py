import sys
import os
import time
import logging

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.multi_agent_orchestrator import MultiAgentOrchestrator, Agent
from modules.atena_browser_agent import AtenaBrowserAgent
import asyncio

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 TESTE-BROWSER] %(message)s",
    datefmt="%H:%M:%S"
)

def browser_task_handler(task):
    logging.info(f"Iniciando tarefa de navegação: {task.get('url')}")
    agent = AtenaBrowserAgent()
    
    async def run_browser_task():
        await agent.launch(headless=True)
        success = await agent.navigate(task.get('url'))
        if success:
            if task.get('action') == 'screenshot':
                await agent.take_screenshot(task.get('output_path', 'screenshot.png'))
                result = f"Screenshot salvo em {task.get('output_path', 'screenshot.png')}"
            elif task.get('action') == 'extract_text':
                text = await agent.get_text_content()
                result = f"Texto extraído ({len(text)} caracteres): {text[:200]}..."
            else:
                result = "Navegação concluída com sucesso."
        else:
            result = "Falha na navegação."
        await agent.close()
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_browser_task())
    finally:
        loop.close()

def main():
    orchestrator = MultiAgentOrchestrator()
    
    browser_agent = Agent(
        agent_id="ATENA-Browser-01",
        role="Navegador Web Autônomo",
        capabilities=["web_browsing", "data_extraction", "screenshot"],
        task_handler=browser_task_handler
    )
    
    orchestrator.register_agent(browser_agent)
    orchestrator.start()
    
    print("\n--- Solicitando Navegação no GitHub da ATENA ---\n")
    orchestrator.submit_task({
        "description": "Acessar repositório ATENA e tirar screenshot",
        "url": "https://github.com/AtenaAuto/ATENA-",
        "action": "screenshot",
        "output_path": "atena_github_test.png",
        "required_capabilities": ["web_browsing", "screenshot"]
    })
    
    # Aguarda a conclusão (navegação pode demorar um pouco)
    time.sleep(15)
    
    orchestrator.stop()
    
    if os.path.exists("atena_github_test.png"):
        print("\n✅ SUCESSO: O BrowserAgent navegou e salvou o screenshot!")
    else:
        print("\n❌ FALHA: O screenshot não foi gerado.")

if __name__ == "__main__":
    main()
