"""ATENA Ω Vercel dashboard and chat API.

This module is intentionally self-contained because Vercel can use a root
``api.py`` file as the Python serverless entrypoint. It exposes a polished
operator dashboard plus JSON endpoints for health, capabilities, and chat.
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
APP_VERSION = "10.1.0"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
__path__ = [str(Path(__file__).with_name("api"))]

SYSTEM_PROMPT = """
Você é a ATENA Ω, uma assistente técnica para o operador do dashboard.
Responda em português do Brasil, com clareza, objetividade e foco prático.
Explique capacidades reais deste repositório quando perguntarem: terminal
assistant, missões autônomas, gates de qualidade, validação de segurança,
monitoramento, evolução de código, pesquisa web/GitHub, APIs FastAPI e deploy
Vercel. Quando não tiver uma chave de modelo configurada, ofereça um modo local
honesto e útil, sem fingir acesso externo.
""".strip()

CAPABILITIES = [
    {
        "title": "Chat operacional",
        "description": "Conversa por API com Gemini quando GEMINI_API_KEY está configurada.",
        "icon": "💬",
    },
    {
        "title": "Assistente de terminal",
        "description": "Modo interativo para operar tarefas locais via launcher ./atena assistant.",
        "icon": "⌨️",
    },
    {
        "title": "Missões autônomas",
        "description": "Protocolos para pesquisa, código, segurança, produção e orquestração.",
        "icon": "🚀",
    },
    {
        "title": "Gates de qualidade",
        "description": "Doctor, self-test, release-gate, lint e suíte pytest para validação contínua.",
        "icon": "🛡️",
    },
    {
        "title": "Evolução e memória",
        "description": "Módulos de scorecard, auditoria, rollback, cache e aprendizagem operacional.",
        "icon": "🧬",
    },
    {
        "title": "Observabilidade",
        "description": "Endpoints /healthz, /api/status e cards em tempo real para deploy serverless.",
        "icon": "📊",
    },
]

SUGGESTIONS = [
    "O que você consegue fazer neste repositório?",
    "Como eu publico este dashboard na Vercel?",
    "Liste os comandos principais da ATENA.",
    "Crie um plano para evoluir a ATENA com segurança.",
]

app = FastAPI(title=f"{APP_NAME} Dashboard", version=APP_VERSION)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL)
else:
    gemini_model = None


class ChatRequest(BaseModel):
    """Incoming chat payload from the dashboard."""

    message: str = Field(..., min_length=1, max_length=6000)


class ChatResponse(BaseModel):
    """Chat response returned to the browser."""

    response: str
    mode: str
    trace_id: str
    created_at: str


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


STARTED_AT = utc_now()


def local_fallback_response(message: str) -> str:
    """Return a useful local response when no model API key is configured."""

    lower_message = message.lower()
    if "vercel" in lower_message or "deploy" in lower_message:
        return (
            "Para publicar na Vercel: conecte o repositório, configure a variável "
            "GEMINI_API_KEY no painel do projeto, mantenha o build Python apontando "
            "para api.py via vercel.json e acesse / após o deploy. O chat funciona "
            "sem chave em modo local, mas respostas inteligentes exigem Gemini."
        )
    if "comando" in lower_message or "capaz" in lower_message or "fazer" in lower_message:
        return (
            "Eu posso operar como dashboard/chat, expor health checks, orientar o uso "
            "do launcher ./atena, listar capacidades, apoiar missões autônomas, validar "
            "qualidade com testes e gates, e servir como interface bonita para deploy "
            "serverless na Vercel. Para IA generativa completa, configure GEMINI_API_KEY."
        )
    return (
        "Modo local ativo: recebi sua mensagem e estou pronta para orientar sobre a "
        "ATENA, comandos, deploy, testes e arquitetura. Configure GEMINI_API_KEY para "
        "ativar respostas neurais completas via Gemini."
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Echo request IDs for traceability in tests and Vercel logs."""

    response = await call_next(request)
    request_id = request.headers.get("x-request-id")
    if request_id:
        response.headers["x-request-id"] = request_id
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Health endpoint for Vercel and external monitors."""

    return {"status": "ok"}


@app.get("/status")
def legacy_status() -> dict[str, object]:
    """Legacy status endpoint kept for existing tests and monitors."""

    return {
        "service": "atena",
        "status": "ok",
        "release": APP_VERSION,
        "environment": os.getenv("VERCEL_ENV", "local"),
        "started_at": STARTED_AT,
    }


@app.get("/api/status")
def status() -> dict[str, object]:
    """Return runtime status for the dashboard cards."""

    return {
        "service": "atena-dashboard",
        "status": "online",
        "version": APP_VERSION,
        "model": GEMINI_MODEL if gemini_model else "local-fallback",
        "llm_configured": bool(gemini_model),
        "capabilities_count": len(CAPABILITIES),
        "timestamp": utc_now(),
    }


@app.get("/api/capabilities")
def capabilities() -> dict[str, object]:
    """Return ATENA capabilities displayed by the UI."""

    return {"capabilities": CAPABILITIES, "suggestions": SUGGESTIONS}


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(data: ChatRequest) -> ChatResponse:
    """Chat with ATENA through Gemini or the deterministic local fallback."""

    trace_id = str(uuid4())
    if not gemini_model:
        return ChatResponse(
            response=local_fallback_response(data.message),
            mode="local-fallback",
            trace_id=trace_id,
            created_at=utc_now(),
        )

    response = gemini_model.generate_content(f"{SYSTEM_PROMPT}\n\nUsuário: {data.message}")
    text = getattr(response, "text", "").strip() or "Não consegui gerar uma resposta agora."
    return ChatResponse(
        response=text,
        mode=GEMINI_MODEL,
        trace_id=trace_id,
        created_at=utc_now(),
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Serve the ATENA operator dashboard."""

    cards = "".join(
        f"""
        <article class="capability-card">
          <div class="capability-icon">{item['icon']}</div>
          <h3>{item['title']}</h3>
          <p>{item['description']}</p>
        </article>
        """
        for item in CAPABILITIES
    )
    suggestion_buttons = "".join(
        f'<button class="chip" type="button" data-prompt="{suggestion}">{suggestion}</button>'
        for suggestion in SUGGESTIONS
    )

    return f"""
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ATENA Dashboard — Neural Cockpit</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050816;
      --panel: rgba(10, 18, 38, 0.76);
      --panel-strong: rgba(13, 24, 52, 0.94);
      --cyan: #22d3ee;
      --blue: #60a5fa;
      --violet: #a78bfa;
      --pink: #fb7185;
      --green: #34d399;
      --text: #e5f6ff;
      --muted: #93a4b8;
      --border: rgba(125, 211, 252, 0.22);
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 12% 18%, rgba(34, 211, 238, 0.22), transparent 28%),
        radial-gradient(circle at 88% 8%, rgba(167, 139, 250, 0.24), transparent 28%),
        radial-gradient(circle at 72% 92%, rgba(251, 113, 133, 0.16), transparent 28%),
        linear-gradient(135deg, #020617 0%, var(--bg) 50%, #0f172a 100%);
      color: var(--text);
      overflow-x: hidden;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: radial-gradient(circle at center, black 0%, transparent 78%);
    }}
    .shell {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0; }}
    .hero {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 22px;
      align-items: stretch;
      margin-bottom: 22px;
    }}
    .panel {{
      position: relative;
      overflow: hidden;
      border: 1px solid var(--border);
      background: linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(8, 13, 30, 0.72));
      border-radius: 30px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .intro {{ padding: 34px; min-height: 390px; }}
    .intro::after {{
      content: "";
      position: absolute;
      width: 360px;
      height: 360px;
      right: -120px;
      top: -110px;
      border-radius: 999px;
      background: conic-gradient(from 120deg, rgba(34,211,238,.5), rgba(167,139,250,.25), transparent, rgba(34,211,238,.5));
      filter: blur(6px);
      opacity: .68;
    }}
    .badge {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 8px 12px;
      border: 1px solid rgba(52, 211, 153, .35);
      border-radius: 999px;
      background: rgba(16, 185, 129, .1);
      color: #b7ffe6;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: .03em;
      text-transform: uppercase;
    }}
    h1 {{
      position: relative;
      z-index: 1;
      margin: 22px 0 14px;
      font-size: clamp(42px, 7vw, 84px);
      line-height: .9;
      letter-spacing: -0.07em;
    }}
    .gradient-text {{
      background: linear-gradient(90deg, #fff, var(--cyan), var(--violet));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}
    .lead {{ position: relative; z-index: 1; color: #c6d8ea; font-size: 18px; line-height: 1.7; max-width: 680px; }}
    .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 26px; position: relative; z-index: 1; }}
    .stat {{ padding: 16px; border-radius: 18px; background: rgba(2, 6, 23, .46); border: 1px solid rgba(148, 163, 184, .18); }}
    .stat strong {{ display:block; font-size: 26px; color: white; }}
    .stat span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .chat {{ display: flex; flex-direction: column; min-height: 620px; }}
    .chat-header {{ padding: 22px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; gap: 18px; }}
    .chat-title strong {{ display: block; font-size: 18px; }}
    .chat-title span {{ color: var(--muted); font-size: 13px; }}
    .pulse {{ width: 12px; height: 12px; border-radius: 999px; background: var(--green); box-shadow: 0 0 0 8px rgba(52,211,153,.12), 0 0 28px rgba(52,211,153,.7); }}
    .messages {{ flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; max-height: 430px; }}
    .msg {{ display: grid; gap: 6px; max-width: 90%; }}
    .msg.user {{ align-self: flex-end; text-align: right; }}
    .msg .label {{ color: var(--muted); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; }}
    .bubble {{ padding: 14px 16px; border-radius: 18px; line-height: 1.55; white-space: pre-wrap; }}
    .atena .bubble {{ background: rgba(14, 165, 233, .12); border: 1px solid rgba(34, 211, 238, .22); }}
    .user .bubble {{ background: linear-gradient(135deg, rgba(99,102,241,.95), rgba(14,165,233,.85)); color: white; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 0 20px 14px; }}
    .chip {{ cursor: pointer; border: 1px solid rgba(125,211,252,.24); background: rgba(15,23,42,.72); color: #dbeafe; border-radius: 999px; padding: 8px 10px; font-size: 12px; }}
    .composer {{ padding: 18px; border-top: 1px solid var(--border); display: grid; grid-template-columns: 1fr auto; gap: 12px; }}
    textarea {{
      width: 100%; min-height: 54px; max-height: 140px; resize: vertical; border: 1px solid rgba(125,211,252,.24); border-radius: 18px;
      background: rgba(2,6,23,.55); color: var(--text); padding: 15px 16px; outline: none; font: inherit;
    }}
    textarea:focus {{ border-color: var(--cyan); box-shadow: 0 0 0 4px rgba(34,211,238,.09); }}
    .send {{ border: 0; cursor: pointer; border-radius: 18px; padding: 0 22px; min-width: 112px; font-weight: 800; color: #02111d; background: linear-gradient(135deg, var(--cyan), var(--blue)); box-shadow: 0 16px 30px rgba(34,211,238,.2); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
    .capability-card {{ padding: 20px; border-radius: 24px; background: var(--panel); border: 1px solid rgba(125,211,252,.16); box-shadow: 0 14px 40px rgba(0,0,0,.22); }}
    .capability-icon {{ width: 48px; height: 48px; display: grid; place-items: center; border-radius: 16px; background: rgba(34, 211, 238, .12); font-size: 24px; margin-bottom: 14px; }}
    .capability-card h3 {{ margin: 0 0 8px; font-size: 17px; }}
    .capability-card p {{ margin: 0; color: var(--muted); line-height: 1.6; font-size: 14px; }}
    footer {{ color: var(--muted); text-align: center; padding: 24px 0 4px; font-size: 13px; }}
    @media (max-width: 920px) {{ .hero, .grid {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: 1fr; }} .chat {{ min-height: 590px; }} }}
    @media (max-width: 560px) {{ .shell {{ width: min(100% - 20px, 1180px); }} .intro {{ padding: 24px; }} .composer {{ grid-template-columns: 1fr; }} .send {{ min-height: 48px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="panel intro">
        <div class="badge"><span class="pulse"></span> Dashboard online • Vercel ready</div>
        <h1><span class="gradient-text">ATENA Ω</span><br/>Neural Cockpit</h1><span style="position:absolute;left:-9999px">ATENA Dashboard</span>
        <p class="lead">Um dashboard bonito para conversar com a ATENA, monitorar status, ver capacidades e publicar como API Python serverless na Vercel.</p>
        <div class="stats">
          <div class="stat"><strong id="statusText">ON</strong><span>Status</span></div>
          <div class="stat"><strong>{len(CAPABILITIES)}</strong><span>Capacidades</span></div>
          <div class="stat"><strong id="modelText">...</strong><span>Modelo</span></div>
        </div>
      </div>
      <section class="panel chat" aria-label="Chat da ATENA">
        <div class="chat-header">
          <div class="chat-title"><strong>Converse com a ATENA</strong><span id="modeText">Carregando núcleo...</span></div>
          <span class="pulse" aria-hidden="true"></span>
        </div>
        <div class="messages" id="messages">
          <div class="msg atena"><span class="label">ATENA</span><div class="bubble">Olá, Danilo. Painel carregado. Me pergunte o que consigo fazer, peça um plano ou teste o chat.</div></div>
        </div>
        <div class="chips">{suggestion_buttons}</div>
        <form class="composer" id="chatForm">
          <textarea id="messageInput" placeholder="Digite sua mensagem para a ATENA..." required></textarea>
          <button class="send" type="submit">Enviar</button>
        </form>
      </section>
    </section>
    <section class="grid" aria-label="Capacidades da ATENA">{cards}</section>
    <footer>ATENA Ω Dashboard v{APP_VERSION} • /api/chat • /api/status • /healthz</footer>
  </main>
  <script>
    const messages = document.querySelector('#messages');
    const form = document.querySelector('#chatForm');
    const input = document.querySelector('#messageInput');
    const modeText = document.querySelector('#modeText');
    const modelText = document.querySelector('#modelText');
    const statusText = document.querySelector('#statusText');

    function appendMessage(sender, text, kind) {{
      const wrapper = document.createElement('div');
      wrapper.className = `msg ${{kind}}`;
      const label = document.createElement('span');
      label.className = 'label';
      label.textContent = sender;
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      wrapper.append(label, bubble);
      messages.appendChild(wrapper);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }}

    async function refreshStatus() {{
      const response = await fetch('/api/status');
      const data = await response.json();
      statusText.textContent = data.status === 'online' ? 'ON' : 'OFF';
      modelText.textContent = data.llm_configured ? 'Gemini' : 'Local';
      modeText.textContent = data.llm_configured ? `Modo neural: ${{data.model}}` : 'Modo local: configure GEMINI_API_KEY para Gemini';
    }}

    async function sendMessage(text) {{
      appendMessage('Você', text, 'user');
      const loading = appendMessage('ATENA', 'Processando...', 'atena');
      const response = await fetch('/api/chat', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ message: text }})
      }});
      const data = await response.json();
      loading.textContent = data.response || 'Sem resposta.';
      modeText.textContent = `Última resposta: ${{data.mode}}`;
    }}

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      try {{
        await sendMessage(text);
      }} catch (error) {{
        appendMessage('Sistema', 'Falha ao conectar com /api/chat. Verifique o deploy ou logs da Vercel.', 'atena');
      }}
    }});

    document.querySelectorAll('.chip').forEach((button) => {{
      button.addEventListener('click', () => {{
        input.value = button.dataset.prompt;
        input.focus();
      }});
    }});

    refreshStatus().catch(() => {{
      statusText.textContent = 'WARN';
      modeText.textContent = 'Não foi possível ler /api/status';
      modelText.textContent = 'N/D';
    }});
  </script>
</body>
</html>
"""
