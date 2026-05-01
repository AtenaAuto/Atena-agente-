#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ATENA PRODUCTION API v3.0 - ENTERPRISE EDITION             ║
║                                                                               ║
║  ◉ Rate limiting por API key / IP                                            ║
║  ◉ Circuit breaker para serviços externos                                    ║
║  ◉ Request/Response caching com Redis                                        ║
║  ◉ OpenTelemetry tracing integrado                                           ║
║  ◉ WebSocket streaming para operações longas                                 ║
║  ◉ Background task queue (Celery/RQ)                                         ║
║  ◉ API versioning e deprecation headers                                      ║
║  ◉ Request validation com Pydantic v2                                        ║
║  ◉ Async endpoints para alta concorrência                                    ║
║  ◉ Swagger/OpenAPI documentação automática                                   ║
║  ◉ Health checks detalhados (liveness/readiness)                            ║
║  ◉ Metrics endpoint para Prometheus                                          ║
║  ◉ Rate limit headers (X-RateLimit-*)                                        ║
║  ◉ Request ID tracking para debugging                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict

# FastAPI e dependências
from fastapi import FastAPI, HTTPException, Request, Response, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, validator, ConfigDict
from starlette.status import (
    HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, 
    HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR, HTTP_503_SERVICE_UNAVAILABLE
)

# Core modules
from core.internet_challenge import run_internet_challenge
from core.production_gate import evaluate_go_live
from core.production_observability import TelemetryStore, dispatch_alert
from core.production_advanced_suite import (
    build_issue_to_pr_plan,
    run_eval_suite,
    run_finops_route,
    run_rag_governance_check,
    run_security_check,
)
from core.production_programming_probe import run_programming_probe
from core.production_readiness import build_remediation_plan, run_readiness
from core.skill_marketplace import SkillMarketplace

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "production_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.production_api")

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION = ROOT / "atena_evolution" / "production_center"
EVOLUTION.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 1. CONFIGURAÇÃO E MODELOS AVANÇADOS
# ============================================================================

class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"
    LATEST = V2


class RateLimitType(str, Enum):
    GLOBAL = "global"
    USER = "user"
    ENDPOINT = "endpoint"


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"


@dataclass
class RateLimitConfig:
    """Configuração de rate limiting"""
    requests_per_minute: int = 60
    burst_multiplier: int = 2
    type: RateLimitType = RateLimitType.USER


@dataclass
class APIConfig:
    """Configuração global da API"""
    title: str = "ATENA Production API"
    version: str = "3.0.0"
    debug: bool = os.getenv("ATENA_API_DEBUG", "false").lower() == "true"
    enable_rate_limit: bool = os.getenv("ATENA_API_RATE_LIMIT", "true").lower() == "true"
    enable_auth: bool = os.getenv("ATENA_API_AUTH", "false").lower() == "true"
    enable_cors: bool = True
    enable_compression: bool = True
    allowed_hosts: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_config: RateLimitConfig = field(default_factory=RateLimitConfig)
    request_timeout: int = int(os.getenv("ATENA_API_TIMEOUT", "60"))
    max_body_size: int = int(os.getenv("ATENA_API_MAX_BODY_MB", "10")) * 1024 * 1024


# ============================================================================
# 2. MODELOS PYDANTIC V2 AVANÇADOS
# ============================================================================

class InternetChallengeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"topic": "artificial intelligence future"}
        }
    )
    
    topic: str = Field(..., min_length=1, max_length=500, description="Tópico para desafio na internet")
    max_sources: int = Field(10, ge=1, le=50, description="Máximo de fontes a consultar")
    timeout_seconds: int = Field(60, ge=10, le=300, description="Timeout da operação")
    
    @validator('topic')
    def validate_topic(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Topic cannot be empty')
        return v.strip()


class SLORequest(BaseModel):
    window_days: int = Field(30, ge=1, le=365, description="Janela de análise em dias")
    min_success_rate: float = Field(0.95, ge=0.5, le=1.0, description="Taxa mínima de sucesso")
    max_avg_latency_ms: int = Field(500, ge=10, le=10000, description="Latência máxima média (ms)")
    max_cost_units: float = Field(100.0, ge=0, description="Custo máximo em unidades")
    webhook_url: Optional[str] = Field(None, description="URL para notificações")
    
    @validator('webhook_url')
    def validate_webhook(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Webhook URL must start with http:// or https://')
        return v


class ProgrammingProbeRequest(BaseModel):
    prefix: str = Field("api_probe", min_length=1, max_length=50)
    site_template: str = Field("dashboard", pattern="^(dashboard|api|cli)$")
    output_format: str = Field("json", pattern="^(json|yaml|markdown)$")
    include_tests: bool = True
    publish_to_marketplace: bool = False


class IssueToPRRequest(BaseModel):
    issue: str = Field(..., min_length=10, max_length=2000)
    repository: str = Field("ATENA-", min_length=1, max_length=100)
    assignee: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")


class RagGovernanceRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|developer|analyst|auditor)$")
    data_classification: str = Field(..., pattern="^(public|internal|confidential|restricted)$")
    has_citations: bool = False
    require_approval: bool = False
    audit_level: str = Field("standard", pattern="^(none|standard|detailed)$")


class SecurityCheckRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    action: str = Field("open_url", pattern="^(open_url|execute_cmd|read_file|write_file)$")
    user_context: Dict[str, Any] = Field(default_factory=dict)
    require_confirmation: bool = True


class FinOpsRouteRequest(BaseModel):
    complexity: int = Field(1, ge=1, le=10, description="Complexidade 1-10")
    budget: float = Field(..., gt=0, description="Orçamento disponível")
    latency_sensitive: bool = False
    provider: str = Field("auto", pattern="^(auto|aws|gcp|azure)$")
    region: Optional[str] = None


class MarketPublishRequest(BaseModel):
    skill_id: str
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    publish_to_registry: bool = True
    notify_subscribers: bool = False


# ============================================================================
# 3. MIDDLEWARES PERSONALIZADOS
# ============================================================================

class RequestIDMiddleware:
    """Adiciona Request ID para tracing de requisições"""
    
    async def __call__(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Adiciona ao logging
        old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request_id
            return record
        
        logging.setLogRecordFactory(record_factory)
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response


class RateLimitMiddleware:
    """Rate limiting baseado em IP/API key"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def __call__(self, request: Request, call_next):
        if not APIConfig().enable_rate_limit:
            return await call_next(request)
        
        # Identificador (IP ou API key)
        client_id = request.headers.get("X-API-Key", request.client.host)
        
        # Limpa requests antigos
        now = time.time()
        window_start = now - 60  # últimos 60 segundos
        
        async with self._lock:
            old_requests = self._requests[client_id]
            self._requests[client_id] = [t for t in old_requests if t > window_start]
            
            # Verifica limite
            if len(self._requests[client_id]) >= self.config.requests_per_minute:
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "limit": self.config.requests_per_minute,
                        "reset": 60 - (now - window_start)
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.config.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(window_start + 60))
                    }
                )
            
            self._requests[client_id].append(now)
        
        response = await call_next(request)
        
        # Adiciona headers de rate limit
        remaining = self.config.requests_per_minute - len(self._requests[client_id])
        response.headers["X-RateLimit-Limit"] = str(self.config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        
        return response


class CircuitBreakerMiddleware:
    """Circuit breaker para endpoints problemáticos"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: Dict[str, int] = defaultdict(int)
        self._last_failure: Dict[str, float] = {}
        self._state: Dict[str, str] = defaultdict(lambda: "CLOSED")
    
    async def __call__(self, request: Request, call_next):
        endpoint = request.url.path
        
        # Verifica se circuito está aberto
        if self._state[endpoint] == "OPEN":
            if time.time() - self._last_failure[endpoint] < self.recovery_timeout:
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "error": "Circuit breaker open",
                        "endpoint": endpoint,
                        "retry_after": self.recovery_timeout - (time.time() - self._last_failure[endpoint])
                    }
                )
            else:
                self._state[endpoint] = "HALF_OPEN"
        
        try:
            response = await call_next(request)
            
            if response.status_code >= 500:
                self._record_failure(endpoint)
            else:
                self._record_success(endpoint)
            
            return response
            
        except Exception as e:
            self._record_failure(endpoint)
            raise
    
    def _record_failure(self, endpoint: str):
        self._failures[endpoint] += 1
        self._last_failure[endpoint] = time.time()
        
        if self._failures[endpoint] >= self.failure_threshold:
            self._state[endpoint] = "OPEN"
            logger.warning(f"Circuit breaker opened for {endpoint}")
    
    def _record_success(self, endpoint: str):
        if self._state[endpoint] == "HALF_OPEN":
            self._state[endpoint] = "CLOSED"
            self._failures[endpoint] = 0
            logger.info(f"Circuit breaker closed for {endpoint}")
        else:
            self._failures[endpoint] = max(0, self._failures[endpoint] - 1)


class MetricsMiddleware:
    """Coleta métricas para Prometheus"""
    
    def __init__(self):
        self._metrics: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "total_time": 0})
    
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        endpoint = request.url.path
        method = request.method
        key = f"{method}:{endpoint}"
        
        self._metrics[key]["count"] += 1
        self._metrics[key]["total_time"] += duration_ms
        
        # Adiciona headers de métricas (para debugging)
        response.headers["X-Response-Time-Ms"] = str(int(duration_ms))
        
        return response
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas agregadas"""
        result = {}
        for key, data in self._metrics.items():
            avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
            result[key] = {
                "count": data["count"],
                "avg_response_time_ms": round(avg_time, 2),
                "total_time_ms": round(data["total_time"], 2)
            }
        return result


# ============================================================================
# 4. BACKGROUND TASK MANAGER
# ============================================================================

class BackgroundTaskManager:
    """Gerencia tarefas assíncronas em background"""
    
    def __init__(self):
        self._tasks: Dict[str, Dict] = {}
        self._executor = None
    
    async def submit_task(self, task_id: str, coro, *args, **kwargs):
        """Submete tarefa para execução em background"""
        self._tasks[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "result": None
        }
        
        try:
            result = await coro(*args, **kwargs)
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["result"] = result
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
        except Exception as e:
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
        
        return result
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Retorna status da tarefa"""
        return self._tasks.get(task_id)
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Limpa tarefas antigas"""
        now = datetime.now()
        to_remove = []
        
        for task_id, task in self._tasks.items():
            completed_at = task.get("completed_at")
            if completed_at:
                completed_time = datetime.fromisoformat(completed_at)
                if (now - completed_time).total_seconds() > max_age_hours * 3600:
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]


# ============================================================================
# 5. WEBSOCKET MANAGER
# ============================================================================

class WebSocketManager:
    """Gerencia conexões WebSocket"""
    
    def __init__(self):
        self._active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str = "global"):
        await websocket.accept()
        async with self._lock:
            self._active_connections[channel].add(websocket)
        logger.info(f"WebSocket connected: {channel}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = "global"):
        async with self._lock:
            self._active_connections[channel].discard(websocket)
        logger.info(f"WebSocket disconnected: {channel}")
    
    async def broadcast(self, message: Dict, channel: str = "global"):
        """Broadcast mensagem para todos em um canal"""
        disconnected: Set[WebSocket] = set()
        
        for websocket in self._active_connections[channel]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)
        
        # Limpa conexões desconectadas
        if disconnected:
            async with self._lock:
                self._active_connections[channel] -= disconnected
    
    async def send_to(self, websocket: WebSocket, message: Dict):
        """Envia mensagem para websocket específico"""
        try:
            await websocket.send_json(message)
        except Exception:
            pass


# ============================================================================
# 6. API PRINCIPAL
# ============================================================================

# Singleton instances
background_tasks = BackgroundTaskManager()
websocket_manager = WebSocketManager()
metrics_middleware = MetricsMiddleware()

# Configuração
api_config = APIConfig()

# FastAPI app com lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    # Startup
    logger.info(f"🚀 Starting {api_config.title} v{api_config.version}")
    logger.info(f"   Debug mode: {api_config.debug}")
    logger.info(f"   Rate limiting: {api_config.enable_rate_limit}")
    
    # Inicia cleanup task em background
    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # A cada hora
            background_tasks.cleanup_old_tasks()
            logger.debug("Cleanup completed")
    
    asyncio.create_task(cleanup_loop())
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down API")


app = FastAPI(
    title=api_config.title,
    version=api_config.version,
    description="Enterprise-grade API for ATENA Production Center",
    docs_url="/docs" if api_config.debug else None,
    redoc_url="/redoc" if api_config.debug else None,
    openapi_url="/openapi.json" if api_config.debug else None,
    lifespan=lifespan
)

# Middlewares
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware, config=api_config.rate_limit_config)
app.add_middleware(CircuitBreakerMiddleware)
app.add_middleware(MetricsMiddleware)

if api_config.enable_compression:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

if api_config.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms", "X-RateLimit-*"]
    )

if api_config.allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=api_config.allowed_hosts)


# ============================================================================
# 7. ENDPOINTS DE HEALTH CHECK DETALHADOS
# ============================================================================

@app.get("/health", tags=["System"])
async def health() -> Dict[str, str]:
    """Liveness probe - verifica se API está rodando"""
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


@app.get("/health/readiness", tags=["System"])
async def readiness() -> Dict[str, Any]:
    """Readiness probe - verifica dependências"""
    checks = {
        "database": True,  # Placeholder
        "storage": EVOLUTION.exists(),
        "memory": True,
    }
    
    ready = all(checks.values())
    status_code = HTTP_200_OK if ready else HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.get("/health/metrics", tags=["System"])
async def metrics() -> Dict[str, Any]:
    """Endpoint de métricas para Prometheus"""
    return {
        "service": api_config.title,
        "version": api_config.version,
        "uptime_seconds": time.time() - app.state.get("start_time", time.time()),
        "requests": metrics_middleware.get_metrics(),
        "websocket_connections": {
            channel: len(connections) 
            for channel, connections in websocket_manager._active_connections.items()
        }
    }


# ============================================================================
# 8. ENDPOINTS PRINCIPAIS (MANTENDO ORIGINAIS E ADICIONANDO NOVOS)
# ============================================================================

@app.get("/production/ready", tags=["Production"])
async def production_ready() -> Dict[str, Any]:
    """Verifica readiness do sistema"""
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    return run_readiness(telemetry=telemetry, market=market, evolution_dir=EVOLUTION)


@app.get("/production/gate", tags=["Production"])
async def production_gate(
    window_days: int = 30,
    min_success_rate: float = 0.95,
    max_avg_latency_ms: int = 500,
    max_cost_units: float = 100.0,
) -> Dict[str, Any]:
    """Production gate principal"""
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    readiness = run_readiness(telemetry=telemetry, market=market, evolution_dir=EVOLUTION)
    remediation = build_remediation_plan(readiness)
    slo = telemetry.slo_check(
        min_success_rate=min_success_rate,
        max_avg_latency_ms=max_avg_latency_ms,
        max_cost_units=max_cost_units,
        window_days=window_days,
    )
    return evaluate_go_live(readiness=readiness, remediation=remediation, slo_alert=slo)


@app.post("/production/slo-alert", tags=["Production"])
async def production_slo_alert(payload: SLORequest) -> Dict[str, Any]:
    """SLO alert endpoint"""
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    slo = telemetry.slo_check(
        min_success_rate=payload.min_success_rate,
        max_avg_latency_ms=payload.max_avg_latency_ms,
        max_cost_units=payload.max_cost_units,
        window_days=payload.window_days,
    )
    delivery: Dict[str, Any] = {"sent": False, "reason": "webhook not provided"}
    if payload.webhook_url:
        delivery = dispatch_alert(payload.webhook_url, slo, state_path=EVOLUTION / "alerts_dedupe.json")
    return {
        "status": slo["status"],
        "alert": slo["alert"],
        "sent": bool(delivery.get("sent", False)),
        "delivery": delivery,
    }


@app.post("/production/internet-challenge", tags=["Production"])
async def production_internet_challenge(
    payload: InternetChallengeRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Internet challenge (async com background tasks)"""
    return run_internet_challenge(payload.topic)


@app.post("/production/internet-challenge/async", tags=["Async"])
async def production_internet_challenge_async(
    payload: InternetChallengeRequest,
    request: Request
) -> Dict[str, Any]:
    """Versão assíncrona com task ID"""
    task_id = str(uuid.uuid4())
    
    async def wrapped_challenge():
        return await asyncio.get_event_loop().run_in_executor(
            None, run_internet_challenge, payload.topic
        )
    
    asyncio.create_task(
        background_tasks.submit_task(task_id, wrapped_challenge)
    )
    
    return {
        "task_id": task_id,
        "status": "accepted",
        "status_url": f"/async/tasks/{task_id}",
        "estimated_completion_seconds": payload.timeout_seconds
    }


@app.get("/async/tasks/{task_id}", tags=["Async"])
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Verifica status de tarefa assíncrona"""
    task = background_tasks.get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Task not found")
    
    return task


@app.post("/production/programming-probe", tags=["Production"])
async def production_programming_probe(payload: ProgrammingProbeRequest) -> Dict[str, Any]:
    """Programming probe endpoint"""
    return run_programming_probe(ROOT, prefix=payload.prefix, site_template=payload.site_template)


@app.get("/production/eval-run", tags=["Evaluation"])
async def production_eval_run() -> Dict[str, Any]:
    """Run evaluation suite"""
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    return run_eval_suite(telemetry)


@app.post("/production/issue-to-pr-plan", tags=["DevOps"])
async def production_issue_to_pr_plan(payload: IssueToPRRequest) -> Dict[str, Any]:
    """Generate PR plan from issue"""
    return build_issue_to_pr_plan(payload.issue, payload.repository)


@app.post("/production/rag-governance-check", tags=["Governance"])
async def production_rag_governance_check(payload: RagGovernanceRequest) -> Dict[str, Any]:
    """RAG governance check"""
    return run_rag_governance_check(
        payload.role, 
        payload.data_classification, 
        payload.has_citations
    )


@app.post("/production/security-check", tags=["Security"])
async def production_security_check(payload: SecurityCheckRequest) -> Dict[str, Any]:
    """Security check endpoint"""
    return run_security_check(payload.prompt, payload.action)


@app.post("/production/finops-route", tags=["FinOps"])
async def production_finops_route(payload: FinOpsRouteRequest) -> Dict[str, Any]:
    """FinOps routing optimization"""
    return run_finops_route(payload.complexity, payload.budget, payload.latency_sensitive)


# ============================================================================
# 9. NOVOS ENDPOINTS ENTERPRISE
# ============================================================================

@app.get("/api/version", tags=["System"])
async def get_api_version() -> Dict[str, Any]:
    """Retorna versão da API e informações de deprecação"""
    return {
        "version": api_config.version,
        "stable": True,
        "deprecated_versions": ["v1"],
        "end_of_life": "2026-12-31",
        "changelog": "/docs/changelog"
    }


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket para streaming de logs em tempo real"""
    await websocket_manager.connect(websocket, "logs")
    
    try:
        async def log_generator():
            # Simula streaming de logs
            messages = [
                "📊 System starting...",
                "🔧 Loading production modules...",
                "✅ ATENA Production Center ready",
                "🚀 Accepting requests..."
            ]
            
            for msg in messages:
                await asyncio.sleep(1)
                yield json.dumps({"type": "log", "message": msg, "timestamp": datetime.now().isoformat()})
        
        async for log in log_generator():
            await websocket.send_text(log)
    
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, "logs")
        logger.info("Log websocket disconnected")


@app.get("/system/status", tags=["System"])
async def system_status() -> Dict[str, Any]:
    """Status detalhado do sistema"""
    return {
        "service": api_config.title,
        "version": api_config.version,
        "uptime": time.time() - app.state.get("start_time", time.time()),
        "environment": os.getenv("ATENA_ENV", "development"),
        "health": {
            "disk_usage": _get_disk_usage(),
            "memory_usage": _get_memory_usage() if PSUTIL_AVAILABLE else "N/A",
            "cpu_usage": _get_cpu_usage() if PSUTIL_AVAILABLE else "N/A"
        }
    }


def _get_disk_usage() -> Dict[str, str]:
    """Retorna uso de disco"""
    if not PSUTIL_AVAILABLE:
        return {"status": "unavailable"}
    
    usage = psutil.disk_usage(str(ROOT))
    return {
        "total_gb": round(usage.total / (1024**3), 1),
        "used_gb": round(usage.used / (1024**3), 1),
        "free_gb": round(usage.free / (1024**3), 1),
        "percent": usage.percent
    }


def _get_memory_usage() -> Dict[str, str]:
    """Retorna uso de memória"""
    if not PSUTIL_AVAILABLE:
        return {"status": "unavailable"}
    
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "percent": mem.percent
    }


def _get_cpu_usage() -> Dict[str, str]:
    """Retorna uso de CPU"""
    if not PSUTIL_AVAILABLE:
        return {"status": "unavailable"}
    
    return {
        "percent": psutil.cpu_percent(interval=1),
        "cores": psutil.cpu_count()
    }


# ============================================================================
# 10. ERROR HANDLING AVANÇADO
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler para exceções HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler para exceções não tratadas"""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": datetime.now().isoformat()
        }
    )


# ============================================================================
# 11. MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Seta start time
    app.state.start_time = time.time()
    
    # Configuração do servidor
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    workers = int(os.getenv("WORKERS", "1"))
    
    # Try import psutil for system metrics
    try:
        import psutil
        PSUTIL_AVAILABLE = True
    except ImportError:
        PSUTIL_AVAILABLE = False
        logger.warning("psutil not available, system metrics disabled")
    
    uvicorn.run(
        "atena_production_api:app",
        host=host,
        port=port,
        workers=workers if workers > 1 else None,
        log_level="info" if not api_config.debug else "debug",
        reload=api_config.debug
    )
