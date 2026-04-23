#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dashboard local da ATENA com chat web estilo assistente moderno."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
  <title>ATENA Local Dashboard</title>
  <style>
    :root { --bg:#0b1020; --card:#131a2e; --text:#e7ecff; --muted:#96a4d6; --accent:#8b5cf6; --accent2:#06b6d4; }
    * { box-sizing:border-box; font-family: Inter, system-ui, Arial, sans-serif; }
    body { margin:0; background:radial-gradient(1000px 500px at 10% 0%, #1e1b4b 0%, var(--bg) 50%); color:var(--text); }
    .wrap { max-width:1000px; margin:24px auto; padding:0 16px; display:grid; grid-template-columns:280px 1fr; gap:16px; }
    .card { background:linear-gradient(180deg, #161f39, var(--card)); border:1px solid #2a355f; border-radius:16px; padding:14px; }
    .title { font-weight:700; font-size:16px; margin-bottom:8px; }
    .muted { color:var(--muted); font-size:13px; }
    .pill { display:inline-block; padding:4px 10px; border-radius:999px; background:#1f2a4f; color:#b8c8ff; font-size:12px; }
    #chat { height:62vh; overflow:auto; padding:8px; border-radius:12px; background:#0e152b; border:1px solid #2a355f; }
    .msg { margin:8px 0; padding:10px 12px; border-radius:12px; white-space:pre-wrap; line-height:1.4; }
    .user { background:#243b5f; margin-left:20%; }
    .bot { background:#1f2937; margin-right:20%; border-left:3px solid var(--accent2); }
    .row { display:flex; gap:10px; margin-top:10px; }
    input { flex:1; border-radius:12px; border:1px solid #2a355f; background:#0e152b; color:var(--text); padding:12px; }
    button { border:0; border-radius:12px; padding:12px 14px; background:linear-gradient(90deg,var(--accent),var(--accent2)); color:white; font-weight:600; cursor:pointer; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <div class="title">ATENA Dashboard</div>
      <div class="pill" id="status-pill">carregando...</div>
      <p class="muted" id="status-text">Aguardando estado...</p>
      <hr style="border-color:#2a355f; opacity:.5;">
      <p class="muted">Chat local para conversar com a ATENA no estilo assistente moderno.</p>
      <p class="muted">Atualiza automaticamente o status dos ciclos de evolução.</p>
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
addMsg('bot', 'Olá! Sou a ATENA local. Como posso ajudar hoje?');
refreshStatus();
setInterval(refreshStatus, 4000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    router = AtenaLLMRouter()

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
        answer = self.router.generate(prompt, context="Dashboard local chat da ATENA")
        return self._json({"answer": answer[:4000]})

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
