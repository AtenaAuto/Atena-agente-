#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dashboard local da ATENA com chat web estilo assistente moderno (Ultra Max v2)."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "atena_evolution" / "assistant_dashboard_state.json"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_llm_router import AtenaLLMRouter


HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ATENA Ultra Max v2</title>
  <style>
    :root { --bg:#050816; --card:#0f1731; --text:#e7ecff; --muted:#96a4d6; --accent:#8b5cf6; --accent2:#06b6d4; --ok:#22c55e; }
    * { box-sizing:border-box; font-family: Inter, system-ui, Arial, sans-serif; }
    body { margin:0; background:radial-gradient(900px 500px at 12% 0%, #17113f 0%, var(--bg) 48%); color:var(--text); }
    .wrap { max-width:1100px; margin:24px auto; padding:0 16px; display:grid; grid-template-columns:320px 1fr; gap:16px; }
    .card { background:linear-gradient(180deg, #111a37, var(--card)); border:1px solid #2a355f; border-radius:18px; padding:14px; box-shadow:0 20px 50px rgba(8,12,28,.35); }
    .title { font-weight:700; font-size:16px; margin-bottom:8px; letter-spacing:.2px; }
    .muted { color:var(--muted); font-size:13px; }
    .pill { display:inline-block; padding:4px 10px; border-radius:999px; background:#1f2a4f; color:#b8c8ff; font-size:12px; margin-right:6px; }
    .ok { background:rgba(34,197,94,.14); color:#9ef4bb; border:1px solid rgba(34,197,94,.35); }
    #chat { height:62vh; overflow:auto; padding:8px; border-radius:12px; background:#0a1126; border:1px solid #2a355f; }
    .msg { margin:8px 0; padding:10px 12px; border-radius:12px; white-space:pre-wrap; line-height:1.4; }
    .user { background:#243b5f; margin-left:20%; }
    .bot { background:#1f2937; margin-right:20%; border-left:3px solid var(--accent2); }
    .row { display:flex; gap:10px; margin-top:10px; }
    input { flex:1; border-radius:12px; border:1px solid #2a355f; background:#0a1126; color:var(--text); padding:12px; }
    button { border:0; border-radius:12px; padding:12px 14px; background:linear-gradient(90deg,var(--accent),var(--accent2)); color:white; font-weight:600; cursor:pointer; }
    .small { font-size:12px; margin-top:6px; color:#8ea0d8; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <div class="title">ATENA Ultra Max v2</div>
      <div class="pill" id="status-pill">carregando...</div><span class="pill ok" id="mode-pill">modo: local</span>
      <p class="muted" id="status-text">Aguardando estado...</p>
      <hr style="border-color:#2a355f; opacity:.5;">
      <p class="muted">Interface Ultra Max v2 com fallback automático para engine local.</p>
      <p class="muted">Se API externa falhar, o chat continua vivo no modo local sem interrupção.</p>
    </section>
    <section class="card">
      <div class="title">Chat</div>
      <div id="chat"></div>
      <div class="row">
        <input id="prompt" placeholder="Pergunte algo para a ATENA..." />
        <button id="send">Enviar</button>
      </div>
    </section>
  </div>
<script>
const chat = document.getElementById('chat');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('send');

function addMsg(kind, text){
  const div = document.createElement('div');
  div.className = 'msg ' + kind;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function send(){
  const prompt = promptEl.value.trim();
  if(!prompt) return;
  addMsg('user', prompt);
  promptEl.value = '';
  addMsg('bot', '⏳ Pensando...');
  const idx = chat.children.length - 1;
  try {
    const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({prompt})});
    const data = await res.json();
    chat.children[idx].textContent = data.answer || '(sem resposta)';
    document.getElementById('mode-pill').textContent = `modo: ${data.source || 'local'}`;
  } catch (e) {
    chat.children[idx].textContent = 'Erro no chat local: ' + e;
  }
}

async function refreshStatus(){
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const ok = data.last_success;
    document.getElementById('status-pill').textContent = `ciclos: ${data.cycles ?? 0}`;
    document.getElementById('status-text').textContent =
      `Último ciclo: ${data.last_finished_at ?? '-'} | sucesso: ${ok === null ? '-' : ok}`;
  } catch (_) {}
}

sendBtn.onclick = send;
promptEl.addEventListener('keydown', (e)=>{ if(e.key==='Enter') send(); });
addMsg('bot', 'ATENA Ultra Max v2 online. Posso operar com API externa e fallback local automático.');
refreshStatus();
setInterval(refreshStatus, 4000);
</script>
</body>
</html>
"""


class ExternalChatClient:
    """Cliente mínimo para API externa de chat com timeout curto."""

    def __init__(self) -> None:
        self.url = (os.getenv("ATENA_EXTERNAL_CHAT_URL") or "").strip()
        self.token = (os.getenv("ATENA_EXTERNAL_CHAT_TOKEN") or "").strip()
        self.timeout = float(os.getenv("ATENA_EXTERNAL_CHAT_TIMEOUT", "8"))

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def ask(self, prompt: str) -> str:
        body = json.dumps({"prompt": prompt}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"falha de rede na API externa: {exc}") from exc
        except HTTPError as exc:
            raise RuntimeError(f"API externa retornou HTTP {exc.code}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("API externa retornou JSON inválido") from exc
        answer = (payload.get("answer") or payload.get("response") or "").strip()
        if not answer:
            raise RuntimeError("API externa retornou resposta vazia")
        return answer


class Handler(BaseHTTPRequestHandler):
    router: AtenaLLMRouter | None = None
    external_client = ExternalChatClient()

    @classmethod
    def _router(cls) -> AtenaLLMRouter:
        if cls.router is None:
            cls.router = AtenaLLMRouter()
        return cls.router

    @classmethod
    def resolve_chat_answer(cls, prompt: str) -> tuple[str, str]:
        if cls.external_client.enabled:
            try:
                return cls.external_client.ask(prompt), "external"
            except RuntimeError:
                return cls._router().generate(prompt, context="Dashboard local chat da ATENA"), "local-fallback"
        return cls._router().generate(prompt, context="Dashboard local chat da ATENA"), "local"

    def _json(self, obj: Any, status: int = 200) -> None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path == "/":
            payload = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/status":
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                return self._json(data)
            return self._json({"cycles": 0, "last_success": None})
        return self._json({"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802
        if self.path != "/api/chat":
            return self._json({"error": "not found"}, status=404)
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        body = json.loads(raw)
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return self._json({"error": "prompt vazio"}, status=400)
        answer, source = self.resolve_chat_answer(prompt)
        return self._json({"answer": answer[:4000], "source": source})

    def log_message(self, format: str, *args):  # noqa: A003
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Local Dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"ATENA dashboard local em http://127.0.0.1:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
