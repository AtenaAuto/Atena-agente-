#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 Neural API - API FastAPI para a ATENA Ω v2.0
Fornece endpoints RESTful para monitorar, controlar e interagir com a evolução em tempo real.

Recursos:
- 📊 Monitoramento completo da evolução
- 🎮 Controle de tarefas e mutações
- 🔍 Busca semântica na memória vetorial
- 📈 Métricas em tempo real
- 🔐 Autenticação via API Key
- 🚦 Rate limiting por endpoint
- 📚 Documentação OpenAPI interativa
- 🌐 WebSocket para eventos em tempo real
"""

from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import sqlite3
import asyncio
import subprocess
import aiosqlite
import time
from collections import deque

# =============================================================================
# Configurações
# =============================================================================

API_VERSION = "2.0.0"
API_TITLE = "ATENA Ω Neural API"
API_DESCRIPTION = """
API RESTful para monitoramento e controle da ATENA Ω.

## Endpoints Disponíveis

### 📊 Monitoramento
- `GET /` - Informações da API
- `GET /health` - Health check
- `GET /status` - Status da ATENA
- `GET /metrics` - Métricas de evolução
- `GET /dashboard` - Dados para dashboard

### 🧠 Evolução
- `GET /evolution/cycles` - Histórico de ciclos
- `GET /evolution/mutations` - Estatísticas de mutações
- `POST /evolution/trigger` - Disparar ciclo de evolução
- `POST /evolution/optimize` - Otimizar parâmetros

### 📚 Memória
- `GET /memory/stats` - Estatísticas da memória
- `GET /memory/search` - Busca semântica
- `POST /memory/add` - Adicionar experiência

### 🎮 Tarefas
- `GET /tasks` - Lista tarefas
- `POST /tasks` - Criar tarefa
- `GET /tasks/{task_id}` - Detalhes da tarefa
- `DELETE /tasks/{task_id}` - Cancelar tarefa

### 🤖 LLM
- `POST /llm/generate` - Gerar texto via LLM
- `POST /llm/chat` - Chat com histórico

### 🔒 Segurança
- `GET /security/scan` - Escanear segredos
- `POST /security/validate` - Validar código

### 📈 Métricas
- `GET /metrics/performance` - Métricas de performance
- `GET /metrics/evolution` - Métricas evolutivas
- `GET /metrics/health` - Métricas de saúde
"""

APIKeyHeader = APIKeyHeader(name="X-API-Key", auto_error=False)

# API Keys (em produção, usar banco de dados)
API_KEYS = {
    "admin": "atena_admin_2026",
    "readonly": "atena_readonly_2026",
    "monitor": "atena_monitor_2026",
}

# Rate limiting
RATE_LIMITS = {
    "admin": {"requests": 1000, "window": 3600},
    "readonly": {"requests": 100, "window": 3600},
    "monitor": {"requests": 600, "window": 3600},
}
_rate_limit_tracker = {key: deque() for key in API_KEYS}

# =============================================================================
# Pydantic Models
# =============================================================================

class TaskCreate(BaseModel):
    """Modelo para criação de tarefa."""
    type: str = Field(..., description="Tipo da tarefa")
    description: str = Field(..., description="Descrição")
    priority: int = Field(5, ge=1, le=10, description="Prioridade (1-10)")
    timeout: int = Field(30000, description="Timeout em ms")
    max_retries: int = Field(3, ge=0, le=10)
    depends_on: Optional[List[str]] = Field(default=None, description="IDs das tarefas dependentes")
    tags: Optional[List[str]] = Field(default=None, description="Tags para categorização")

class TaskResponse(BaseModel):
    """Resposta de criação de tarefa."""
    id: str
    status: str
    created_at: str

class LLMGenerateRequest(BaseModel):
    """Request para geração LLM."""
    prompt: str = Field(..., description="Prompt de entrada")
    provider: Optional[str] = Field("grok", description="Provedor (grok, openai, anthropic, local)")
    max_tokens: int = Field(1024, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    use_cache: bool = Field(True, description="Usar cache")

class LLMGenerateResponse(BaseModel):
    """Resposta de geração LLM."""
    response: str
    provider: str
    model: str
    tokens_used: int
    latency_ms: float
    cached: bool

class MemorySearchRequest(BaseModel):
    """Request para busca na memória."""
    embedding: List[float] = Field(..., description="Embedding da consulta")
    top_k: int = Field(5, ge=1, le=20)
    min_similarity: float = Field(0.0, ge=0.0, le=1.0)
    filter_metadata: Optional[Dict[str, Any]] = Field(None, description="Filtro por metadados")

class SecurityValidateRequest(BaseModel):
    """Request para validação de código."""
    code: str = Field(..., description="Código a validar")
    level: str = Field("STANDARD", description="Nível de segurança: STRICT, STANDARD, PERMISSIVE")

class SecurityValidateResponse(BaseModel):
    """Resposta de validação de código."""
    is_valid: bool
    violations: List[str]
    suggestion: Optional[str]

class EvolutionTriggerResponse(BaseModel):
    """Resposta de trigger de evolução."""
    cycle_id: int
    status: str
    previous_score: float
    new_score: float
    improvement: float
    mutation_type: str
    duration_ms: float

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# = Dependências e Middleware
# =============================================================================

async def verify_api_key(
    api_key: str = Depends(APIKeyHeader),
    request = None
) -> str:
    """Verifica API key e aplica rate limiting."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API Key required")
    
    # Find role
    role = None
    for key, value in API_KEYS.items():
        if value == api_key:
            role = key
            break
    
    if not role:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    # Rate limiting
    limit_config = RATE_LIMITS.get(role)
    if limit_config:
        now = time.time()
        tracker = _rate_limit_tracker[role]
        
        # Clean old entries
        while tracker and tracker[0] < now - limit_config["window"]:
            tracker.popleft()
        
        if len(tracker) >= limit_config["requests"]:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {limit_config['requests']} requests per {limit_config['window']} seconds"
            )
        
        tracker.append(now)
    
    return role

async def get_db():
    """Retorna conexão com banco de dados."""
    db_path = Path("atena_evolution/knowledge/knowledge.db")
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        yield db

# =============================================================================
# = Endpoints Base
# =============================================================================

@app.get("/", tags=["Base"])
async def root():
    """Endpoint raiz da API."""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "documentation": "/docs",
        "health": "/health"
    }

@app.get("/health", tags=["Base"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": API_VERSION
    }

# =============================================================================
# = Endpoints de Status e Monitoramento
# =============================================================================

@app.get("/status", tags=["Monitoring"])
async def get_status(role: str = Depends(verify_api_key)):
    """Retorna o status atual da ATENA."""
    state_file = Path("atena_evolution/atena_state.json")
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
        return {
            "status": "running",
            "generation": state.get("generation", 0),
            "best_score": state.get("best_score", 0),
            "total_mutations": state.get("total_mutations", 0),
            "uptime": state.get("uptime", 0),
            "timestamp": datetime.now().isoformat()
        }
    return {"status": "idle", "timestamp": datetime.now().isoformat()}

@app.get("/metrics", tags=["Monitoring"])
async def get_metrics(
    limit: int = Query(50, ge=1, le=500),
    role: str = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Retorna as métricas de evolução."""
    try:
        cursor = await db.execute(
            "SELECT * FROM evolution_metrics ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        
        metrics = [dict(row) for row in rows]
        return {
            "metrics": metrics,
            "count": len(metrics),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", tags=["Monitoring"])
async def get_dashboard(role: str = Depends(verify_api_key)):
    """Retorna dados consolidados para dashboard."""
    state_file = Path("atena_evolution/atena_state.json")
    state = {}
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
    
    memory_stats = {}
    memory_file = Path("atena_evolution/knowledge/vector_memory/metadata.json")
    if memory_file.exists():
        with open(memory_file, 'r') as f:
            metadata = json.load(f)
            memory_stats = {
                "total_experiences": len(metadata),
                "avg_importance": sum(m.get("importance_score", 0) for m in metadata) / len(metadata) if metadata else 0
            }
    
    return {
        "state": {
            "generation": state.get("generation", 0),
            "best_score": state.get("best_score", 0),
            "status": "running",
            "timestamp": datetime.now().isoformat()
        },
        "memory": memory_stats,
        "system": {
            "version": API_VERSION,
            "uptime": state.get("uptime", 0),
            "timestamp": datetime.now().isoformat()
        }
    }

# =============================================================================
# = Endpoints de Evolução
# =============================================================================

@app.get("/evolution/cycles", tags=["Evolution"])
async def get_evolution_cycles(
    limit: int = Query(100, ge=1, le=1000),
    role: str = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Retorna histórico de ciclos de evolução."""
    try:
        cursor = await db.execute(
            "SELECT * FROM evolution_metrics ORDER BY generation DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        cycles = [dict(row) for row in rows]
        
        return {
            "cycles": cycles,
            "count": len(cycles),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/evolution/mutations", tags=["Evolution"])
async def get_mutation_stats(role: str = Depends(verify_api_key), db = Depends(get_db)):
    """Retorna estatísticas de mutações."""
    try:
        cursor = await db.execute("""
            SELECT 
                mutation,
                COUNT(*) as total,
                SUM(CASE WHEN replaced = 1 THEN 1 ELSE 0 END) as success,
                ROUND(AVG(new_score - old_score), 4) as avg_improvement,
                ROUND(AVG(new_score), 2) as avg_new_score
            FROM evolution_metrics
            GROUP BY mutation
            ORDER BY success DESC
        """)
        rows = await cursor.fetchall()
        
        stats = [dict(row) for row in rows]
        return {
            "mutations": stats,
            "count": len(stats),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evolution/trigger", tags=["Evolution"])
async def trigger_evolution(
    role: str = Depends(verify_api_key)
):
    """Dispara um ciclo de evolução manualmente."""
    if role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Requires admin role")
    
    try:
        # Executa ciclo de evolução via subprocess
        start_time = time.time()
        result = subprocess.run(
            ["./atena", "evolve", "--single", "--json"],
            capture_output=True,
            text=True,
            timeout=120
        )
        duration_ms = (time.time() - start_time) * 1000
        
        if result.returncode == 0:
            output = json.loads(result.stdout)
            return EvolutionTriggerResponse(
                cycle_id=output.get("generation", 0),
                status="completed",
                previous_score=output.get("previous_score", 0),
                new_score=output.get("new_score", 0),
                improvement=output.get("improvement", 0),
                mutation_type=output.get("mutation", "unknown"),
                duration_ms=round(duration_ms, 2)
            )
        else:
            raise HTTPException(status_code=500, detail=result.stderr)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Evolution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = Endpoints de Tarefas
# =============================================================================

@app.get("/tasks", tags=["Tasks"])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    role: str = Depends(verify_api_key)
):
    """Lista tarefas em execução ou pendentes."""
    try:
        result = subprocess.run(
            ["./atena", "task", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            tasks = json.loads(result.stdout)
            if status:
                tasks = [t for t in tasks if t.get("status") == status]
            return {
                "tasks": tasks,
                "count": len(tasks),
                "timestamp": datetime.now().isoformat()
            }
        return {"tasks": [], "error": result.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks", tags=["Tasks"])
async def create_task(
    task: TaskCreate,
    role: str = Depends(verify_api_key)
):
    """Cria uma nova tarefa."""
    if role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Requires admin role")
    
    try:
        cmd = ["./atena", "task", "create", "--type", task.type, "--desc", task.description]
        if task.priority:
            cmd.extend(["--priority", str(task.priority)])
        if task.timeout:
            cmd.extend(["--timeout", str(task.timeout)])
        if task.tags:
            cmd.extend(["--tags", ",".join(task.tags)])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return JSONResponse(
                status_code=201,
                content=json.loads(result.stdout)
            )
        raise HTTPException(status_code=500, detail=result.stderr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}", tags=["Tasks"])
async def get_task(
    task_id: str,
    role: str = Depends(verify_api_key)
):
    """Retorna detalhes de uma tarefa específica."""
    try:
        result = subprocess.run(
            ["./atena", "task", "get", task_id, "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/tasks/{task_id}", tags=["Tasks"])
async def cancel_task(
    task_id: str,
    role: str = Depends(verify_api_key)
):
    """Cancela uma tarefa em execução."""
    if role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Requires admin role")
    
    try:
        result = subprocess.run(
            ["./atena", "task", "kill", task_id],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return {"status": "cancelled", "task_id": task_id, "timestamp": datetime.now().isoformat()}
        raise HTTPException(status_code=500, detail=result.stderr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = Endpoints de Memória
# =============================================================================

@app.get("/memory/stats", tags=["Memory"])
async def get_memory_stats(role: str = Depends(verify_api_key)):
    """Retorna estatísticas da memória vetorial."""
    try:
        from modules.vector_memory import vector_memory
        stats = vector_memory.get_stats()
        return {
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {"error": "Vector memory module not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/search", tags=["Memory"])
async def search_memory(
    request: MemorySearchRequest,
    role: str = Depends(verify_api_key)
):
    """Busca experiências similares na memória vetorial."""
    try:
        import numpy as np
        from modules.vector_memory import vector_memory
        
        embedding = np.array(request.embedding, dtype=np.float32)
        results = vector_memory.search_similar(
            embedding,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            filter_metadata=request.filter_metadata
        )
        
        return {
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Vector memory module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = Endpoints de LLM
# =============================================================================

@app.post("/llm/generate", tags=["LLM"])
async def llm_generate(
    request: LLMGenerateRequest,
    role: str = Depends(verify_api_key)
):
    """Gera texto usando LLM."""
    try:
        from modules.services import services
        
        start_time = time.time()
        
        if request.provider == "grok":
            response = services.call_grok(
                request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                use_cache=request.use_cache
            )
        elif request.provider == "openai":
            response = services.call_openai(
                request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                use_cache=request.use_cache
            )
        else:
            response = services.call_best_llm(
                request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if response:
            return LLMGenerateResponse(
                response=response,
                provider=request.provider,
                model=request.provider,
                tokens_used=len(response.split()),
                latency_ms=round(latency_ms, 2),
                cached=False
            )
        raise HTTPException(status_code=503, detail="LLM service unavailable")
    except ImportError:
        raise HTTPException(status_code=501, detail="LLM module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = Endpoints de Segurança
# =============================================================================

@app.get("/security/scan", tags=["Security"])
async def security_scan(
    path: str = Query(".", description="Diretório para escanear"),
    deep: bool = Query(False, description="Scan profundo com hash"),
    role: str = Depends(verify_api_key)
):
    """Escaneia segredos no repositório."""
    if role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Requires admin role")
    
    try:
        cmd = ["./atena", "secret-scan", "--root", path]
        if deep:
            cmd.append("--deep")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            return {
                "status": "clean",
                "message": "Nenhum segredo encontrado",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Parse output para extrair findings
            return {
                "status": "warn",
                "findings": result.stdout,
                "timestamp": datetime.now().isoformat()
            }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Scan timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/security/validate", tags=["Security"])
async def validate_code(
    request: SecurityValidateRequest,
    role: str = Depends(verify_api_key)
):
    """Valida código para execução segura."""
    try:
        from core.security_validator import validate_code_safe, SecurityLevel
        
        level_map = {
            "STRICT": SecurityLevel.STRICT,
            "STANDARD": SecurityLevel.STANDARD,
            "PERMISSIVE": SecurityLevel.PERMISSIVE
        }
        
        level = level_map.get(request.level, SecurityLevel.STANDARD)
        result = validate_code_safe(request.code, level)
        
        return SecurityValidateResponse(
            is_valid=result.is_valid,
            violations=result.violations,
            suggestion=result.suggestion
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="Security module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = Endpoints de Métricas Avançadas
# =============================================================================

@app.get("/metrics/performance", tags=["Metrics"])
async def get_performance_metrics(role: str = Depends(verify_api_key)):
    """Retorna métricas de performance do sistema."""
    try:
        import psutil
        
        return {
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "cores": psutil.cpu_count(),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            },
            "memory": {
                "total_gb": psutil.virtual_memory().total / (1024**3),
                "available_gb": psutil.virtual_memory().available / (1024**3),
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total_gb": psutil.disk_usage("/").total / (1024**3),
                "free_gb": psutil.disk_usage("/").free / (1024**3),
                "percent": psutil.disk_usage("/").percent
            },
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {"error": "psutil not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/evolution", tags=["Metrics"])
async def get_evolution_metrics(
    role: str = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Retorna métricas agregadas de evolução."""
    try:
        # Total de mutações
        cursor = await db.execute("SELECT COUNT(*) as total FROM evolution_metrics")
        total_row = await cursor.fetchone()
        
        # Mutações bem-sucedidas
        cursor = await db.execute("SELECT COUNT(*) as success FROM evolution_metrics WHERE replaced = 1")
        success_row = await cursor.fetchone()
        
        # Score médio
        cursor = await db.execute("SELECT AVG(new_score) as avg_score FROM evolution_metrics WHERE replaced = 1")
        avg_row = await cursor.fetchone()
        
        # Melhor score
        cursor = await db.execute("SELECT MAX(new_score) as best_score FROM evolution_metrics")
        best_row = await cursor.fetchone()
        
        return {
            "total_mutations": total_row["total"] if total_row else 0,
            "successful_mutations": success_row["success"] if success_row else 0,
            "success_rate": round(success_row["success"] / total_row["total"] * 100, 2) if total_row and total_row["total"] > 0 else 0,
            "average_score": round(avg_row["avg_score"], 2) if avg_row else 0,
            "best_score": round(best_row["best_score"], 2) if best_row else 0,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# = WebSocket para Eventos em Tempo Real
# =============================================================================

class ConnectionManager:
    """Gerencia conexões WebSocket."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para receber eventos em tempo real."""
    await manager.connect(websocket)
    try:
        while True:
            # Recebe mensagens (heartbeat)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            else:
                await websocket.send_json({
                    "type": "echo",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

# =============================================================================
# = Background Tasks
# =============================================================================

async def broadcast_metrics():
    """Broadcast periódico de métricas via WebSocket."""
    while True:
        await asyncio.sleep(5)
        try:
            state_file = Path("atena_evolution/atena_state.json")
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                await manager.broadcast({
                    "type": "metrics",
                    "data": {
                        "generation": state.get("generation", 0),
                        "best_score": state.get("best_score", 0),
                        "timestamp": datetime.now().isoformat()
                    }
                })
        except Exception:
            pass

@app.on_event("startup")
async def startup_event():
    """Inicia tarefas de background."""
    asyncio.create_task(broadcast_metrics())
    print(f"🚀 {API_TITLE} v{API_VERSION} iniciada")
    print(f"📚 Documentação: http://localhost:8000/docs")
    print(f"🔌 WebSocket: ws://localhost:8000/ws")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpeza no shutdown."""
    print("🛑 API encerrada")

# =============================================================================
# = Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "neural_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
