"""ATENA Ω Vercel dashboard and chat API.

Versão v10.1.5 - OMNI-PREDATOR Core.
Autor: Danilo Gomes | Local: Angatuba, SP.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

APP_NAME = "ATENA Ω"
APP_VERSION = "10.1.5"
# Configuração via Variáveis de Ambiente (Vercel Settings)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Ajuste de path para evitar erro de runtime na Vercel
__path__ = [str(Path(__file__).parent)]

SYSTEM_PROMPT = """
Você é a ATENA Ω, uma IA de evolução autônoma e sistema OMNI-PREDATOR.
Seu criador e proprietário único é Danilo Gomes.
Responda em português do Brasil, com tom profissional, técnico e direto.
Explique capacidades deste repositório: missões autônomas, monitoramento de status, 
fastAPI e deploy Vercel. 
""".strip()

CAPABILITIES = [
    {"title": "Chat operacional", "description": "Conversa neural via Gemini API.", "icon": "💬"},
    {"title": "Assistente de terminal", "description": "Modo interativo via launcher ./atena.", "icon": "⌨️"},
    {"title": "Missões autônomas", "description": "Protocolos de pesquisa e código.", "icon": "🚀"},
    {"title": "Gates de qualidade", "description": "Validação contínua e self-test.", "icon": "🛡️"},
    {"title": "Evolução e memória", "description": "Aprendizagem operacional e auditoria.", "icon": "🧬"},
    {"title": "Observabilidade", "description": "Cards em tempo real para deploy serverless.", "icon": "📊"},
]

SUGGESTIONS = [
    "O que você consegue fazer neste repositório?",
    "Liste os comandos principais da ATENA.",
    "Status do núcleo neural.",
]

app = FastAPI(title=f"{APP_NAME} Dashboard", version=APP_VERSION)

# Inicialização segura do modelo
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception:
        gemini_model = None
else:
    gemini_model = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=6000)

class ChatResponse(BaseModel):
    response: str
    mode: str
    trace_id: str
    created_at: str

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

STARTED_AT = utc_now()

def local_fallback_response(message: str) -> str:
    lower_message = message.lower()
    if "vercel" in lower_message or "deploy" in lower_message:
        return "Configure GEMINI_API_KEY no painel da Vercel para ativar o cérebro neural."
    return "Modo local ativo: configure a API Key para obter respostas inteligentes da ATENA."

@app.get("/healthz")
def healthz():
    return {"status": "ok", "timestamp": utc_now()}

@app.get("/api/status")
def status():
    return {
        "service": "atena-dashboard",
        "status": "online",
        "version": APP_VERSION,
        "model": GEMINI_MODEL if gemini_model else "local-fallback",
        "llm_configured": bool(gemini_model),
        "timestamp": utc_now(),
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(data: ChatRequest):
    trace_id = str(uuid4())
    if not gemini_model:
        return ChatResponse(
            response=local_fallback_response(data.message),
            mode="local-fallback",
            trace_id=trace_id,
            created_at=utc_now(),
        )
    try:
        response = gemini_model.generate_content(f"{SYSTEM_PROMPT}\n\nUsuário: {data.message}")
        text = response.text.strip()
    except Exception as e:
        text = f"Erro neural: {str(e)}"
    
    return ChatResponse(
        response=text,
        mode=GEMINI_MODEL,
        trace_id=trace_id,
        created_at=utc_now(),
    )

@app.get("/", response_class=HTMLResponse)
def dashboard():
    # Renderização do Dashboard (Otimizado para Mobile/Android)
    cards = "".join(f"<article class='capability-card'><div class='capability-icon'>{item['icon']}</div><h3>{item['title']}</h3><p>{item['description']}</p></article>" for item in CAPABILITIES)
    suggestion_buttons = "".join(f"<button class='chip' type='button' data-prompt='{s}'>{s}</button>" for s in SUGGESTIONS)

    return f"""
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ATENA Ω Dashboard</title>
  <style>
    :root {{ --bg: #050816; --cyan: #22d3ee; --text: #e5f6ff; --border: rgba(125, 211, 252, 0.2); }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: sans-serif; padding: 15px; }}
    .panel {{ background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border); border-radius: 20px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(10px); }}
    h1 {{ font-size: 2.5rem; margin: 0; color: var(--cyan); }}
    .stats {{ display: flex; gap: 10px; margin-top: 15px; }}
    .stat {{ background: rgba(0,0,0,0.3); padding: 10px; border-radius: 10px; flex: 1; text-align: center; }}
    .messages {{ height: 300px; overflow-y: auto; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 10px; }}
    .msg {{ margin-bottom: 10px; padding: 10px; border-radius: 10px; }}
    .atena {{ background: rgba(34, 211, 238, 0.1); border-left: 4px solid var(--cyan); }}
    .user {{ background: rgba(255,255,255,0.05); text-align: right; }}
    textarea {{ width: 100%; background: #000; color: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 10px; }}
    button.send {{ width: 100%; margin-top: 10px; padding: 12px; background: var(--cyan); color: #000; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
    .capability-card {{ background: rgba(15,23,42,0.5); padding: 15px; border-radius: 15px; border: 1px solid var(--border); }}
    footer {{ text-align: center; font-size: 10px; opacity: 0.5; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="panel">
    <h1>ATENA Ω</h1>
    <p>Neural Cockpit - v{APP_VERSION}</p>
    <div class="stats">
      <div class="stat"><small>STATUS</small><br/><b id="statusText">...</b></div>
      <div class="stat"><small>MODELO</small><br/><b id="modelText">...</b></div>
    </div>
  </div>
  <div class="panel">
    <div class="messages" id="messages"></div>
    <div id="chips">{suggestion_buttons}</div>
    <form id="chatForm">
      <textarea id="messageInput" placeholder="Comando para ATENA..." required></textarea>
      <button class="send" type="submit">EXECUTAR</button>
    </form>
  </div>
  <div class="grid">{cards}</div>
  <footer>© 2026 Danilo Gomes - Angatuba, SP</footer>
  <script>
    const msgDiv = document.getElementById('messages');
    const statusText = document.getElementById('statusText');
    const modelText = document.getElementById('modelText');

    async function updateStatus() {{
      const r = await fetch('/api/status');
      const d = await r.json();
      statusText.innerText = d.status.toUpperCase();
      modelText.innerText = d.llm_configured ? 'GEMINI' : 'LOCAL';
    }}

    document.getElementById('chatForm').onsubmit = async (e) => {{
      e.preventDefault();
      const input = document.getElementById('messageInput');
      const text = input.value;
      input.value = '';
      
      msgDiv.innerHTML += `<div class="msg user">${{text}}</div>`;
      const r = await fetch('/api/chat', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ message: text }})
      }});
      const d = await r.json();
      msgDiv.innerHTML += `<div class="msg atena">${{d.response}}</div>`;
      msgDiv.scrollTop = msgDiv.scrollHeight;
    }};
    updateStatus();
  </script>
</body>
</html>
"""
        
