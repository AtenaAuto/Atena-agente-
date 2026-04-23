#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — MISSÃO DE NAVEGAÇÃO: PESQUISA WIKIPÉDIA
    Demonstração da capacidade de navegação da ATENA.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Configuração de caminhos
sys.path.append(str(Path(__file__).parent.parent / "modules"))
sys.path.append(str(Path(__file__).parent.parent / "core"))

from atena_browser_agent import AtenaBrowserAgent

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 ATENA-NAV] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("AtenaNav")

async def run_wikipedia_mission(search_query="Inteligência artificial"):
    logger.info(f"🚀 Iniciando missão de pesquisa: '{search_query}' no Wikipédia")
    
    agent = AtenaBrowserAgent()
    output_path = "/home/ubuntu/ATENA/atena_wikipedia_view.png"
    
    try:
        # Lançamos o navegador (usando headless=True para o sandbox, mas capturando screenshot)
        await agent.launch(headless=True)
        
        # 1. Ir para a página inicial da Wikipédia em português
        url = "https://pt.wikipedia.org/"
        success = await agent.navigate(url)
        
        if not success:
            logger.error("Falha ao acessar a Wikipédia.")
            return

        # 2. Pesquisar o termo
        logger.info(f"Digitando pesquisa: {search_query}")
        # O seletor do campo de busca da Wikipédia costuma ser 'input[name="search"]'
        await agent.type_text('input[name="search"]', search_query)
        await agent.page.press('input[name="search"]', "Enter")
        
        # Aguarda carregar os resultados
        await asyncio.sleep(5)
        
        # 3. Capturar a "tela" da ATENA
        logger.info("Capturando a visão da ATENA...")
        await agent.take_screenshot(output_path)
        
        # 4. Extrair um resumo do que ela está vendo
        text = await agent.get_text_content()
        logger.info(f"ATENA concluiu a leitura. Resumo da visão: {text[:300]}...")
        
        print(f"\n✅ MISSÃO CONCLUÍDA: A ATENA navegou com sucesso.")
        print(f"📸 A 'tela' da ATENA foi salva em: {output_path}")
        
    except Exception as e:
        logger.error(f"Erro durante a missão: {e}")
    finally:
        await agent.close()

if __name__ == "__main__":
    query = "Inteligência artificial"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    asyncio.run(run_wikipedia_mission(query))
