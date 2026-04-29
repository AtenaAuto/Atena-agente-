#!/usr/bin/env python3
"""
Neural API - API FastAPI para a ATENA Ω
Fornece endpoints para monitorar e controlar a evolução em tempo real.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from datetime import datetime
import sqlite3

app = FastAPI(title="ATENA Ω Neural API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Endpoint raiz da API."""
    return {
        "name": "ATENA Ω Neural API",
        "version": "1.0.0",
        "status": "online",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
def get_status():
    """Retorna o status atual da ATENA."""
    state_file = Path("atena_evolution/atena_state.json")
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
        return {
            "status": "running",
            "generation": state.get("generation", 0),
            "best_score": state.get("best_score", 0),
            "timestamp": datetime.now().isoformat()
        }
    return {"status": "idle", "timestamp": datetime.now().isoformat()}

@app.get("/metrics")
def get_metrics(limit: int = 50):
    """Retorna as métricas de evolução."""
    try:
        conn = sqlite3.connect("atena_evolution/knowledge/knowledge.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM evolution_metrics ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        metrics = [dict(row) for row in rows]
        return {"metrics": metrics, "count": len(metrics)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/curiosity")
def get_curiosity_topics():
    """Retorna os tópicos de curiosidade e seus scores."""
    try:
        conn = sqlite3.connect("atena_evolution/knowledge/knowledge.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM curiosity_topics ORDER BY interest_score DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        
        topics = [dict(row) for row in rows]
        return {"topics": topics, "count": len(topics)}
    except Exception as e:
        return {"topics": [], "error": str(e)}

@app.get("/council/decisions")
def get_council_decisions(limit: int = 20):
    """Retorna as decisões recentes do conselho."""
    # Stub: em produção, isso viria de um log estruturado
    return {
        "decisions": [
            {
                "generation": 350,
                "mutation": "Import: from collections import Counter",
                "architect_vote": 1.0,
                "security_vote": 1.0,
                "performance_vote": 0.8,
                "consensus": 0.93,
                "timestamp": datetime.now().isoformat()
            }
        ]
    }

@app.get("/memory/stats")
def get_memory_stats():
    """Retorna estatísticas da memória vetorial."""
    try:
        metadata_file = Path("atena_evolution/knowledge/metadata.json")
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            return {
                "total_experiences": len(metadata),
                "avg_score": sum(m.get("score", 0) for m in metadata) / len(metadata) if metadata else 0,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
