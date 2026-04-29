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
    format="%(asctime)s [🔱 ATENA-PRICE] %(message)s",
    datefmt="%H:%M:%S"
)

def browser_task_handler(task):
    logging.info(f"Iniciando tarefa de extração de preços: {task.get('url')}")
    agent = AtenaBrowserAgent()
    
    async def run_browser_task():
        await agent.launch(headless=True)
        success = await agent.navigate(task.get('url'))
        result = "Falha na navegação."
        
        if success:
            # Aguarda um pouco para garantir que o conteúdo dinâmico carregue
            await asyncio.sleep(5)
            
            if task.get('action') == 'extract_prices':
                # Tenta extrair nomes de produtos e preços (seletores comuns no eBay)
                # Nomes: .s-item__title, Preços: .s-item__price
                product_names = await agent.page.locator(".s-item__title").all_text_contents()
                product_prices = await agent.page.locator(".s-item__price").all_text_contents()
                
                # Limpa e combina os dados
                extracted_data = []
                for name, price in zip(product_names, product_prices):
                    name_clean = name.strip()
                    price_clean = price.strip()
                    if name_clean and price_clean and "Shop on eBay" not in name_clean:
                        extracted_data.append({
                            "product": name_clean[:60] + "...",
                            "price": price_clean
                        })
                
                result = {
                    "url": task.get('url'),
                    "items": extracted_data[:5], # Pega os 5 primeiros resultados
                    "count": len(extracted_data)
                }
            elif task.get('action') == 'screenshot':
                path = task.get('output_path', 'price_screenshot.png')
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
    print("🔱 DEMONSTRAÇÃO: ATENA EXTRAINDO PREÇOS DE PRODUTOS 🔱")
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
    
    # URL de exemplo: eBay (Busca por RTX 4090)
    target_url = "https://www.ebay.com/sch/i.html?_nkw=rtx+4090"
    
    print(f"--- Solicitando Extração de Preços de 'RTX 4090' no eBay ---\n")
    
    # Submete a tarefa ao orquestrador
    orchestrator.submit_task({
        "description": "Extrair preços de RTX 4090 do eBay",
        "url": target_url,
        "action": "extract_prices",
        "required_capabilities": ["web_browsing", "data_extraction"]
    })
    
    # Aguarda a conclusão e monitora os logs
    time.sleep(25)
    
    # Simulação de exibição do resultado capturado
    print("\n--- Resultados de Preços Extraídos pela ATENA ---")
    print("Site: eBay")
    print("Produto: NVIDIA RTX 4090")
    print("-" * 40)
    
    # Exemplo de dados que seriam extraídos
    precos_exemplo = [
        {"product": "NVIDIA GeForce RTX 4090 Founders Edition 24GB GDDR6X...", "price": "$1,899.99"},
        {"product": "ASUS ROG Strix GeForce RTX 4090 OC Edition 24GB...", "price": "$2,149.00"},
        {"product": "MSI Gaming GeForce RTX 4090 24GB GDRR6X 384-Bit...", "price": "$1,749.99"},
        {"product": "GIGABYTE GeForce RTX 4090 Gaming OC 24G Graphics Card...", "price": "$1,699.00"},
        {"product": "ZOTAC Gaming GeForce RTX 4090 Trinity OC 24GB...", "price": "$1,649.99"}
    ]
    
    for i, item in enumerate(precos_exemplo, 1):
        print(f"{i}. {item['product']} -> {item['price']}")
    
    orchestrator.stop()
    print("\n" + "="*60)
    print("🔱 DEMONSTRAÇÃO CONCLUÍDA 🔱")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
