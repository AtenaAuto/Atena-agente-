"""
ATENA Ω - Módulo de Requisições Resilientes e Otimização de APIs.
Versão: v1.1.0
Autor: Danilo Gomes | Local: Angatuba, SP.
"""
from __future__ import annotations
import time
import random
import logging
import requests
from typing import Dict, Any, Optional, Callable
from functools import wraps
from enum import Enum
from dataclasses import dataclass, field

# Configuração de logs para auditoria no terminal do Hugging Face
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ATENA_BAKEOFF")

class HTTPMethod(Enum):
    """Enumeração de métodos HTTP suportados."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker para proteção de APIs."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

class CircuitBreaker:
    """
    Implementa o padrão Circuit Breaker para evitar chamadas repetidas a APIs falhas.
    Estados: CLOSED (operando) -> OPEN (protegendo) -> HALF_OPEN (testando recuperação)
    """
    
    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.half_open_calls = 0
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executa função protegida pelo Circuit Breaker."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.config.recovery_timeout:
                logger.info("Tempo de recuperação expirado. Transicionando para HALF_OPEN")
                self.state = "HALF_OPEN"
                self.half_open_calls = 0
            else:
                raise Exception(f"Circuit Breaker está OPEN. Aguarde {self.config.recovery_timeout - (time.time() - self.last_failure_time):.1f}s")
        
        try:
            result = func(*args, **kwargs)
            
            if self.state == "HALF_OPEN":
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    logger.info("Sucesso no estado HALF_OPEN. Fechando Circuit Breaker.")
                    self._reset()
            
            return result
            
        except Exception as e:
            self._record_failure()
            raise e
    
    def _record_failure(self):
        """Registra falha e potencialmente abre o circuito."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold and self.state != "OPEN":
            logger.warning(f"Limite de {self.config.failure_threshold} falhas atingido. Abrindo Circuit Breaker.")
            self.state = "OPEN"
    
    def _reset(self):
        """Reseta o Circuit Breaker para estado CLOSED."""
        self.failure_count = 0
        self.state = "CLOSED"
        self.half_open_calls = 0

class ResilientRequester:
    def __init__(self, max_retries: int = 5, base_delay: float = 2.0, enable_circuit_breaker: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        
        # Cache simples para respostas GET (evita requisições repetidas)
        self.cache: Dict[str, tuple[float, requests.Response]] = {}
        self.cache_ttl: float = 300.0  # 5 minutos
        
        # Lista de User-Agents modernos para mimetizar tráfego real e evitar bloqueios
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
        
        # Estatísticas para monitoramento
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retries_performed": 0,
            "cache_hits": 0
        }

    def _get_rotated_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Gera cabeçalhos HTTP dinâmicos para simular requisições orgânicas."""
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",  # Suporte a compressão
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Cache-Control": "no-cache" if random.random() > 0.7 else "max-age=0",  # Variação de cache
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _get_cache_key(self, url: str, method: str, payload: Optional[Dict] = None) -> str:
        """Gera chave única para cache baseada nos parâmetros da requisição."""
        import json
        key = f"{method}:{url}"
        if payload:
            key += f":{json.dumps(payload, sort_keys=True)}"
        return key

    def _get_from_cache(self, key: str) -> Optional[requests.Response]:
        """Recupera resposta do cache se ainda válida."""
        if key in self.cache:
            timestamp, response = self.cache[key]
            if time.time() - timestamp < self.cache_ttl:
                self.stats["cache_hits"] += 1
                logger.debug(f"Cache HIT para {key}")
                return response
            else:
                del self.cache[key]
        return None

    def _execute_request(self, url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, 
                        custom_headers: Optional[Dict[str, str]] = None, use_cache: bool = True) -> Optional[requests.Response]:
        """Executa requisição HTTP com mecanismos de resiliência."""
        
        cache_key = self._get_cache_key(url, method, payload)
        
        # Verifica cache apenas para GET
        if use_cache and method == "GET":
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                return cached_response
        
        retries = 0
        delay = self.base_delay

        while retries < self.max_retries:
            headers = self._get_rotated_headers(custom_headers)
            
            # Adiciona header de rate limit residual para evitar bloqueios
            if retries > 0:
                headers["X-Retry-Count"] = str(retries)
            
            try:
                logger.info(f"Disparando requisição ({method}) para {url} - Tentativa {retries + 1}/{self.max_retries}")
                
                # Detecta se é necessário usar proxy rotativo
                session = requests.Session()
                response = session.request(
                    method=method,
                    url=url,
                    json=payload if method in ["POST", "PUT", "PATCH"] else None,
                    params=payload if method == "GET" else None,
                    headers=headers,
                    timeout=10.0,
                    allow_redirects=True  # Segue redirects automaticamente
                )

                # Tratamento específico para diferentes códigos de status
                if response.status_code == 429:
                    logger.warning(f"Rate Limit detectado (HTTP 429). Iniciando protocolo de recuo.")
                    retries += 1
                    self.stats["retries_performed"] += 1
                    
                    # Verifica header de retry-after se disponível
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                            logger.info(f"Servidor solicitou aguardar {delay}s via Retry-After header")
                        except ValueError:
                            pass
                    
                    # Cálculo com Recuo Exponencial + Jitter
                    jitter = random.uniform(0.5, 1.5)
                    calculated_delay = (delay * (2 ** (retries - 1))) * jitter
                    
                    logger.info(f"Thread em repouso por {calculated_delay:.2f} segundos")
                    time.sleep(calculated_delay)
                    continue
                
                elif response.status_code == 503:
                    logger.warning(f"Serviço indisponível (HTTP 503). Aguardando recuperação...")
                    retries += 1
                    time.sleep(delay * (2 ** retries))
                    continue
                
                elif 500 <= response.status_code < 600:
                    logger.error(f"Erro de servidor (HTTP {response.status_code})")
                    retries += 1
                    time.sleep(delay * retries)
                    continue

                # Sucesso - verifica se resposta é válida
                response.raise_for_status()
                
                # Cache apenas para GET bem-sucedidas
                if use_cache and method == "GET":
                    self.cache[cache_key] = (time.time(), response)
                
                self.stats["successful_requests"] += 1
                return response

            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout na tentativa {retries + 1}: {str(e)}")
                retries += 1
                self.stats["retries_performed"] += 1
                time.sleep(delay * retries)
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Erro de conexão na tentativa {retries + 1}: {str(e)}")
                retries += 1
                self.stats["retries_performed"] += 1
                time.sleep(delay * retries)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de rede na tentativa {retries + 1}: {str(e)}")
                retries += 1
                self.stats["retries_performed"] += 1
                time.sleep(delay * retries)

        self.stats["failed_requests"] += 1
        logger.critical(f"Falha total após {self.max_retries} tentativas para {url}")
        return None

    def execute(self, url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, 
                custom_headers: Optional[Dict[str, str]] = None, use_cache: bool = True) -> Optional[requests.Response]:
        """
        Executa requisições HTTP com proteção de Circuit Breaker, Cache e Recuo Exponencial.
        
        Args:
            url: URL alvo
            method: Método HTTP (GET, POST, PUT, DELETE, PATCH)
            payload: Dados para enviar (json para POST/PUT/PATCH, params para GET)
            custom_headers: Headers adicionais
            use_cache: Habilita cache para requisições GET
            
        Returns:
            Response object ou None em caso de falha total
        """
        self.stats["total_requests"] += 1
        
        # Validação do método HTTP
        try:
            HTTPMethod(method.upper())
        except ValueError:
            logger.error(f"Método HTTP inválido: {method}")
            return None
        
        # Proteção via Circuit Breaker
        if self.enable_circuit_breaker and self.circuit_breaker:
            try:
                return self.circuit_breaker.call(
                    self._execute_request, url, method.upper(), payload, custom_headers, use_cache
                )
            except Exception as e:
                logger.error(f"Circuit Breaker impediu execução: {str(e)}")
                return None
        else:
            return self._execute_request(url, method.upper(), payload, custom_headers, use_cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de execução."""
        success_rate = (self.stats["successful_requests"] / self.stats["total_requests"] * 100) if self.stats["total_requests"] > 0 else 0
        
        return {
            **self.stats,
            "success_rate_percent": round(success_rate, 2),
            "circuit_breaker_state": self.circuit_breaker.state if self.circuit_breaker else "DISABLED",
            "cache_size": len(self.cache)
        }
    
    def clear_cache(self):
        """Limpa o cache de respostas."""
        self.cache.clear()
        logger.info("Cache limpo com sucesso")

# Decorador para fácil integração
def resilient_request(max_retries: int = 3, base_delay: float = 1.0):
    """Decorador que adiciona resiliência a funções que fazem requisições."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            requester = ResilientRequester(max_retries=max_retries, base_delay=base_delay)
            # Assume que a função decorada retorna (url, method, payload, headers)
            result = func(*args, **kwargs)
            if isinstance(result, tuple) and len(result) >= 2:
                return requester.execute(*result)
            return requester.execute(result)
        return wrapper
    return decorator

# Exemplo de Uso Operacional
if __name__ == "__main__":
    requester = ResilientRequester(max_retries=5, base_delay=1.5)
    
    # Teste com endpoints reais
    endpoints = [
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/429",  # Rate limit simulado
        "https://httpbin.org/delay/3",     # Resposta lenta
        "https://api.github.com/zen"       # API real
    ]
    
    for url in endpoints:
        print(f"\n--- Testando {url} ---")
        resultado = requester.execute(url=url, method="GET")
        
        if resultado:
            print(f"✅ Sucesso! Código HTTP: {resultado.status_code}")
            if url == "https://api.github.com/zen":
                print(f"📖 Zen do GitHub: {resultado.text}")
        else:
            print(f"❌ Falha após todas as tentativas")
        
        time.sleep(2)  # Delay entre testes
    
    # Exibe estatísticas finais
    print("\n=== ESTATÍSTICAS GLOBAIS ===")
    stats = requester.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
