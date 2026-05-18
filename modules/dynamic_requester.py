"""
ATENA Ω - Módulo de Requisições Resilientes e Otimização de APIs.
Versão: v1.0.0
Autor: Danilo Gomes | Local: Angatuba, SP.
"""
from __future__ import annotations
import time
import random
import logging
import requests
from typing import Dict, Any, Optional

# Configuração de logs para auditoria no terminal do Hugging Face
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ATENA_BAKEOFF")

class ResilientRequester:
    def __init__(self, max_retries: int = 5, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        # Lista de User-Agents modernos para mimetizar tráfego real e evitar bloqueios por assinatura
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]

    def _get_rotated_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Gera cabeçalhos HTTP dinâmicos para simular requisições orgânicas."""
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def execute(self, url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, custom_headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        """
        Executa requisições HTTP utilizando Recuo Exponencial e Jitter.
        Garante o não esgotamento do hardware do container.
        """
        retries = 0
        delay = self.base_delay

        while retries < self.max_retries:
            headers = self._get_rotated_headers(custom_headers)
            try:
                logger.info(f"Disparando requisição ({method}) para {url} - Tentativa {retries + 1}/{self.max_retries}")
                
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=10.0 # Impede que a requisição fique travada indefinidamente gastando CPU
                )

                # Código 429 indica "Too Many Requests" (Rate Limit atingido)
                if response.status_code == 429:
                    logger.warning(f"Rate Limit detectado (HTTP 429). Iniciando protocolo de recuo.")
                    retries += 1
                    
                    # CÁLCULO CRÍTICO: Recuo Exponencial + Jitter (Variação Aleatória)
                    # Impede o efeito "Thundering Herd" e reduz drasticamente o uso de CPU
                    jitter = random.uniform(0.5, 1.5)
                    calculated_delay = (delay * (2 ** (retries - 1))) * jitter
                    
                    logger.info(f"Thread em repouso por {calculated_delay:.2f} segundos para liberação de barramento.")
                    time.sleep(calculated_delay)
                    continue

                # Se o status for bem-sucedido ou um erro que não seja de limite, retorna o objeto
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de rede na tentativa {retries + 1}: {str(e)}")
                retries += 1
                time.sleep(delay * retries)

        logger.critical(f"Falha total após {self.max_retries} tentativas. Abortando execução para proteger o Core.")
        return None

# Exemplo de Uso Operacional
if __name__ == "__main__":
    requester = ResilientRequester(max_retries=5, base_delay=1.5)
    
    # Teste simulado em uma rota de teste da própria ATENA ou API externa
    url_teste = "https://httpbin.org/status/429,200" # Simula alternância entre erro 429 e sucesso 200
    resultado = requester.execute(url=url_teste, method="GET")
    
    if resultado:
        print(f"Sucesso na execução do bypass. Código HTTP: {resultado.status_code}")
