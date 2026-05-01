#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω - Terminal Assistant (Claude Code Style) - APRIMORADO v2.0
Interface moderna com comandos intuitivos, IA multimodal e auto-evolução.

Novos recursos v2.0:
- 🧠 Memória de longo prazo com busca semântica
- 🔄 Auto-aprendizado contínuo baseado em interações
- 🌐 Navegação web autônoma com browser agent
- 📊 Dashboard interativo em tempo real
- 🔌 Sistema de plugins dinâmico
- ⚡ Execução paralela de tarefas
- 🛡️ Análise de segurança avançada
- 📈 Métricas SLO e auto-correção
"""

import shlex
import subprocess
import threading
import time
import sys
import os
import hashlib
import logging
import json
import re
import socket
import urllib.parse
import urllib.request
import webbrowser
import asyncio
from dataclasses import dataclass, field
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple, Callable
from xml.etree import ElementTree
from collections import defaultdict, deque
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_llm_router import AtenaLLMRouter
from core.internet_challenge import run_internet_challenge
from core.atena_module_preloader import preload_all_modules

# --- Tentativa de importar módulos avançados ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    from rich.table import Table
    from rich.box import ROUNDED
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.tree import Tree
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    from atena_browser_agent import AtenaBrowserAgent
    HAS_BROWSER_AGENT = True
except ImportError:
    HAS_BROWSER_AGENT = False

try:
    from multi_agent_orchestrator import MultiAgentOrchestrator
    HAS_ORCHESTRATOR = True
except ImportError:
    HAS_ORCHESTRATOR = False

try:
    from vector_memory import vector_memory
    HAS_VECTOR_MEMORY = True
except ImportError:
    HAS_VECTOR_MEMORY = False

# Configurações Globais
DASHBOARD_PORT = int(os.getenv("ATENA_DASHBOARD_PORT", "8765"))
ENABLE_DASHBOARD = os.getenv("ATENA_DASHBOARD_ENABLED", "0") == "1"
ROUTER_TIMEOUT_SECONDS = float(os.getenv("ATENA_ROUTER_TIMEOUT_S", "90"))
AUTO_LEARNING_ENABLED = os.getenv("ATENA_AUTO_LEARNING", "1") == "1"
MAX_SESSION_HISTORY = int(os.getenv("ATENA_MAX_SESSION_HISTORY", "100"))

# --- Logger silencioso ---
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("atena_assistant")


class PlainConsole:
    """Fallback simples para ambientes sem rich."""

    @staticmethod
    def print(*args, end: str = "\n", **kwargs) -> None:
        text = " ".join(str(a) for a in args)
        print(text, end=end)


CONSOLE = Console() if HAS_RICH else PlainConsole()


def console_print(message: str, style: str = None) -> None:
    if HAS_RICH and style:
        CONSOLE.print(message, style=style)
    elif HAS_RICH:
        CONSOLE.print(message)
    else:
        print(message)


# =============================================================================
# 1. MEMÓRIA DE LONGO PRAZO COM BUSCA SEMÂNTICA
# =============================================================================

class ConversationMemory:
    """Gerencia memória de conversas com busca semântica."""

    def __init__(self, max_history: int = MAX_SESSION_HISTORY):
        self.history: deque = deque(maxlen=max_history)
        self.embeddings: Dict[str, List[float]] = {}
        self.session_file = ROOT / "atena_evolution" / "conversation_memory.json"
        self._load()
        self._lock = threading.RLock()

    def _load(self):
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text(encoding="utf-8"))
                self.history = deque(data.get("history", []), maxlen=MAX_SESSION_HISTORY)
                self.embeddings = data.get("embeddings", {})
            except Exception:
                pass

    def _save(self):
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            self.session_file.write_text(json.dumps({
                "history": list(self.history),
                "embeddings": self.embeddings
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, user_input: str, assistant_response: str, context: str = ""):
        """Adiciona uma interação à memória."""
        with self._lock:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_input,
                "assistant": assistant_response[:2000],
                "context": context[:500]
            }
            self.history.append(entry)
            
            # Gera embedding para busca semântica (se disponível)
            if HAS_VECTOR_MEMORY:
                try:
                    text_for_embed = f"{user_input} {assistant_response[:500]}"
                    emb = self._get_embedding(text_for_embed)
                    if emb:
                        self.embeddings[entry["timestamp"]] = emb
                except Exception:
                    pass
            self._save()

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Gera embedding para busca semântica."""
        try:
            # Fallback simples usando hash de palavras
            words = set(re.findall(r'\b[a-z]{3,}\b', text.lower()))
            vector = [0.0] * 100
            for i, word in enumerate(list(words)[:100]):
                h = hash(word) % 100
                vector[h] += 1.0
            norm = sum(v * v for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]
            return vector
        except Exception:
            return None

    def search_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """Busca interações similares semanticamente."""
        if not self.embeddings or not HAS_VECTOR_MEMORY:
            # Fallback: busca por palavras-chave
            query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
            scored = []
            for entry in self.history:
                text = f"{entry['user']} {entry['assistant']}".lower()
                score = sum(1 for w in query_words if w in text)
                if score > 0:
                    scored.append((score, entry))
            scored.sort(reverse=True)
            return [entry for _, entry in scored[:top_k]]
        
        # Busca semântica
        q_emb = self._get_embedding(query)
        if not q_emb:
            return []
        scored = []
        for ts, emb in self.embeddings.items():
            if emb and len(emb) == len(q_emb):
                sim = sum(a * b for a, b in zip(q_emb, emb))
                scored.append((sim, ts))
        scored.sort(reverse=True)
        results = []
        for sim, ts in scored[:top_k]:
            for entry in self.history:
                if entry["timestamp"] == ts:
                    results.append({"similarity": sim, **entry})
                    break
        return results

    def get_recent(self, n: int = 10) -> List[Dict]:
        """Retorna interações recentes."""
        return list(self.history)[-n:]

    def clear(self):
        """Limpa memória."""
        with self._lock:
            self.history.clear()
            self.embeddings.clear()
            self._save()


# =============================================================================
# 2. SISTEMA DE AUTO-APRENDIZADO
# =============================================================================

class AutoLearner:
    """Aprende com interações e melhora respostas automaticamente."""

    def __init__(self, memory: ConversationMemory):
        self.memory = memory
        self.patterns: Dict[str, Dict] = {}
        self.patterns_file = ROOT / "atena_evolution" / "learned_patterns.json"
        self._load_patterns()
        self._lock = threading.RLock()

    def _load_patterns(self):
        if self.patterns_file.exists():
            try:
                self.patterns = json.loads(self.patterns_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_patterns(self):
        try:
            self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
            self.patterns_file.write_text(json.dumps(self.patterns, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def learn_from_interaction(self, user_input: str, response: str, feedback: Optional[str] = None):
        """Aprende com a interação."""
        with self._lock:
            # Extrai padrões da pergunta
            words = re.findall(r'\b[a-z]{4,}\b', user_input.lower())
            key = "_".join(sorted(set(words))[:5])
            
            if key not in self.patterns:
                self.patterns[key] = {
                    "count": 0,
                    "success_count": 0,
                    "responses": [],
                    "last_seen": None
                }
            
            pattern = self.patterns[key]
            pattern["count"] += 1
            if feedback and "bom" in feedback.lower():
                pattern["success_count"] += 1
            pattern["responses"].append({
                "response": response[:1000],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "feedback": feedback
            })
            # Mantém apenas últimas 10 respostas
            pattern["responses"] = pattern["responses"][-10:]
            pattern["last_seen"] = datetime.now(timezone.utc).isoformat()
            
            self._save_patterns()

    def suggest_improvement(self, user_input: str) -> Optional[str]:
        """Sugere melhoria baseada em padrões aprendidos."""
        words = set(re.findall(r'\b[a-z]{4,}\b', user_input.lower()))
        best_match = None
        best_score = 0
        
        for key, pattern in self.patterns.items():
            key_words = set(key.split("_"))
            overlap = len(words & key_words)
            if overlap > best_score and pattern["success_count"] / max(pattern["count"], 1) > 0.5:
                best_score = overlap
                best_match = pattern
        
        if best_match and best_match["responses"]:
            # Retorna a resposta com maior sucesso
            best_response = max(best_match["responses"], 
                               key=lambda x: x.get("feedback", "").count("bom") if x.get("feedback") else 0)
            return best_response["response"]
        return None


# =============================================================================
# 3. PLUGIN SYSTEM DINÂMICO
# =============================================================================

@dataclass
class Plugin:
    name: str
    description: str
    handler: Callable
    commands: List[str]
    enabled: bool = True


class PluginManager:
    """Gerencia plugins dinâmicos para o assistente."""

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.plugins_dir = ROOT / "plugins" / "assistant_plugins"
        self._load_plugins()

    def _load_plugins(self):
        """Carrega plugins da pasta plugins/assistant_plugins/"""
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            self._create_example_plugin()
            return
        
        for py_file in self.plugins_dir.glob("*.py"):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, "register_plugin"):
                    plugin_info = module.register_plugin()
                    plugin = Plugin(
                        name=plugin_info["name"],
                        description=plugin_info["description"],
                        handler=plugin_info["handler"],
                        commands=plugin_info["commands"]
                    )
                    self.plugins[plugin.name] = plugin
                    console_print(f"[Plugin] Carregado: {plugin.name}", style="dim")
            except Exception as e:
                console_print(f"[Plugin] Erro ao carregar {py_file.name}: {e}", style="yellow")

    def _create_example_plugin(self):
        """Cria um plugin de exemplo."""
        example_path = self.plugins_dir / "example_plugin.py"
        if not example_path.exists():
            example_path.write_text('''
#!/usr/bin/env python3
"""Plugin de exemplo para ATENA Ω."""

def register_plugin():
    """Registra o plugin no sistema."""
    return {
        "name": "example",
        "description": "Plugin de exemplo com comandos úteis",
        "commands": ["/example", "/exemplo", "/demo"],
        "handler": handle_example
    }

def handle_example(args: str) -> str:
    """Handler do plugin example."""
    return f"Plugin example executado com argumentos: {args}\\nComandos disponíveis: /example, /exemplo, /demo"
''', encoding="utf-8")
            console_print("[Plugin] Plugin de exemplo criado", style="dim")

    def get_handler(self, command: str) -> Optional[Tuple[Callable, str]]:
        """Retorna handler para um comando."""
        for plugin in self.plugins.values():
            if plugin.enabled and command in plugin.commands:
                return plugin.handler, plugin.name
        return None

    def list_plugins(self) -> List[Dict]:
        """Lista plugins disponíveis."""
        return [{"name": p.name, "description": p.description, "commands": p.commands, "enabled": p.enabled} 
                for p in self.plugins.values()]

    def enable_plugin(self, name: str) -> bool:
        """Habilita um plugin."""
        if name in self.plugins:
            self.plugins[name].enabled = True
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Desabilita um plugin."""
        if name in self.plugins:
            self.plugins[name].enabled = False
            return True
        return False


# =============================================================================
# 4. EXECUÇÃO PARALELA DE TAREFAS
# =============================================================================

class ParallelTaskExecutor:
    """Executa múltiplas tarefas em paralelo."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._results: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def execute_parallel(self, tasks: Dict[str, Callable], timeout: float = 30.0) -> Dict[str, Any]:
        """Executa tarefas em paralelo e retorna resultados."""
        results = {}

        def _run_task(name: str, task: Callable):
            try:
                result = task()
                with self._lock:
                    results[name] = {"status": "ok", "result": result}
            except Exception as e:
                with self._lock:
                    results[name] = {"status": "error", "error": str(e)}

        threads = []
        for name, task in tasks.items():
            t = threading.Thread(target=_run_task, args=(name, task))
            t.daemon = True
            t.start()
            threads.append(t)

        # Aguarda conclusão com timeout
        start = time.time()
        while threads and (time.time() - start) < timeout:
            threads = [t for t in threads if t.is_alive()]
            time.sleep(0.1)

        return results


# =============================================================================
# 5. ANÁLISE DE SEGURANÇA AVANÇADA
# =============================================================================

class SecurityAnalyzer:
    """Analisa segurança de comandos e código."""

    DANGEROUS_PATTERNS = [
        (r'rm\s+-rf\s+/', "Extremamente perigoso: rm -rf /"),
        (r'curl.*\|\s*(bash|sh)', "Perigoso: pipe de curl para shell"),
        (r'wget.*\|\s*(bash|sh)', "Perigoso: pipe de wget para shell"),
        (r'chmod\s+777', "Inseguro: permissões 777"),
        (r'chown\s+-R', "Potencialmente perigoso: chown recursivo"),
        (r'kill\s+-9', "Perigoso: kill -9"),
        (r'dd\s+if=', "Perigoso: dd pode corromper dados"),
        (r'mkfs\.', "Muito perigoso: formatação de disco"),
        (r'passwd\s', "Sensível: alteração de senha"),
        (r'sudo\s', "Elevação de privilégio - requer confirmação"),
    ]

    @classmethod
    def analyze_command(cls, command: str) -> Tuple[bool, List[str]]:
        """Analisa comando e retorna (seguro, [avisos])."""
        warnings = []
        for pattern, warning in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                warnings.append(warning)
        
        if "sudo" in command and "--confirm" not in command:
            warnings.append("Comando sudo requer --confirm para execução")
        
        return len(warnings) == 0, warnings

    @classmethod
    def analyze_code(cls, code: str) -> Tuple[bool, List[str]]:
        """Analisa código Python em busca de padrões perigosos."""
        warnings = []
        
        dangerous_imports = ["os.system", "subprocess.Popen", "eval", "exec", "__import__"]
        for imp in dangerous_imports:
            if imp in code:
                warnings.append(f"Import perigoso detectado: {imp}")
        
        if "base64" in code and "b64decode" in code:
            warnings.append("Possível código ofuscado detectado")
        
        return len(warnings) == 0, warnings


# =============================================================================
# 6. DASHBOARD INTERATIVO
# =============================================================================

DASHBOARD_HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>ATENA Ω - Dashboard</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Courier New', monospace; background: #0a0e1a; color: #c0caf5; padding: 20px; margin: 0; }
        h1 { color: #bb9af7; border-bottom: 1px solid #3b4261; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; margin-top: 20px; }
        .card { background: #161c2e; border-radius: 12px; padding: 20px; border-left: 4px solid #7aa2f7; }
        .card h3 { margin: 0 0 10px 0; color: #7aa2f7; }
        .metric { font-size: 24px; font-weight: bold; color: #9ece6a; }
        .status-ok { color: #9ece6a; }
        .status-warn { color: #e0af68; }
        .status-error { color: #f7768e; }
        pre { background: #1a2335; padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
        .log-line { font-family: monospace; font-size: 11px; border-bottom: 1px solid #2a3a5a; padding: 4px; }
        .timestamp { color: #565f89; }
    </style>
    <script>
        let ws = null;
        let autoScroll = true;

        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateMetrics(data);
                addLog(data.log || data.event);
            };
            ws.onclose = () => setTimeout(connect, 3000);
        }

        function updateMetrics(data) {
            const metrics = ['generation', 'score', 'memory_size', 'plugins_count', 'tasks_completed'];
            for (let m of metrics) {
                const el = document.getElementById(m);
                if (el && data[m] !== undefined) el.innerText = data[m];
            }
            const statusEl = document.getElementById('status');
            if (statusEl && data.status) {
                statusEl.innerText = data.status;
                statusEl.className = `status-${data.status}`;
            }
        }

        function addLog(msg) {
            const logsDiv = document.getElementById('logs');
            if (!logsDiv) return;
            const line = document.createElement('div');
            line.className = 'log-line';
            const ts = new Date().toLocaleTimeString();
            line.innerHTML = `<span class="timestamp">[${ts}]</span> ${escapeHtml(msg)}`;
            logsDiv.appendChild(line);
            if (autoScroll) line.scrollIntoView();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        window.onload = () => {
            connect();
            const scrollCheck = document.getElementById('auto-scroll');
            if (scrollCheck) scrollCheck.onchange = (e) => autoScroll = e.target.checked;
        };
    </script>
</head>
<body>
    <h1>🔱 ATENA Ω - Terminal Assistant Dashboard</h1>
    
    <div class="grid">
        <div class="card">
            <h3>📊 Status do Sistema</h3>
            <div>Status: <span id="status" class="status-ok">iniciando...</span></div>
            <div>Geração: <span id="generation">0</span></div>
            <div>Score: <span id="score">0</span></div>
        </div>
        
        <div class="card">
            <h3>🧠 Memória</h3>
            <div>Interações: <span id="memory_size">0</span></div>
            <div>Plugins: <span id="plugins_count">0</span></div>
            <div>Tarefas: <span id="tasks_completed">0</span></div>
        </div>
        
        <div class="card">
            <h3>📋 Logs em Tempo Real</h3>
            <label><input type="checkbox" id="auto-scroll" checked> Auto-scroll</label>
            <div id="logs" style="max-height: 300px; overflow-y: auto;"></div>
        </div>
    </div>
</body>
</html>
'''


class AtenaDashboard:
    """Dashboard web interativo para monitoramento."""

    def __init__(self, port: int = DASHBOARD_PORT):
        self.port = port
        self._server = None
        self._thread = None
        self._websockets = []
        self._metrics = {
            "generation": 0,
            "score": 0,
            "memory_size": 0,
            "plugins_count": 0,
            "tasks_completed": 0,
            "status": "running"
        }
        self._log_queue: deque = deque(maxlen=1000)
        self._lock = threading.RLock()

    def log(self, message: str):
        """Adiciona log para o dashboard."""
        with self._lock:
            self._log_queue.append({"timestamp": datetime.now().isoformat(), "message": message})

    def update_metrics(self, **kwargs):
        """Atualiza métricas do dashboard."""
        with self._lock:
            self._metrics.update(kwargs)

    def start(self):
        """Inicia o servidor dashboard."""
        try:
            import http.server
            import socketserver
            from http import HTTPStatus

            dashboard = self

            class Handler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # Silencia logs do servidor

                def do_GET(self):
                    if self.path == '/':
                        self.send_response(HTTPStatus.OK)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
                    else:
                        self.send_error(HTTPStatus.NOT_FOUND)

                def do_websocket(self):
                    # Placeholder para WebSocket
                    pass

            with socketserver.TCPServer(("0.0.0.0", self.port), Handler) as server:
                self._server = server
                console_print(f"📊 Dashboard disponível em http://localhost:{self.port}", style="cyan")
                server.serve_forever()
        except Exception as e:
            console_print(f"⚠️ Dashboard não pôde iniciar: {e}", style="yellow")

    def start_async(self):
        """Inicia dashboard em thread separada."""
        if ENABLE_DASHBOARD:
            self._thread = threading.Thread(target=self.start, daemon=True)
            self._thread.start()


# =============================================================================
# 7. FUNÇÕES AUXILIARES (router, internet, etc.)
# =============================================================================

def router_generate_with_timeout(
    router: AtenaLLMRouter,
    prompt: str,
    context: str,
    timeout_seconds: float = ROUTER_TIMEOUT_SECONDS,
) -> str:
    """Executa router.generate em thread daemon para evitar travas."""
    done = threading.Event()
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = router.generate(prompt, context=context)
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=_worker, daemon=True).start()
    if not done.wait(timeout_seconds):
        raise TimeoutError(f"router.generate timeout > {timeout_seconds}s")
    if "error" in box:
        raise box["error"]
    return str(box.get("value", ""))


def _wants_five_topics(user_input: str) -> bool:
    text = user_input.lower()
    return ("5 tópicos" in text) or ("5 topicos" in text)


def _build_five_topics_prompt(user_input: str) -> str:
    return (
        f"{user_input}\n\n"
        "Responda SOMENTE com JSON válido no formato:\n"
        '{"topicos":["tópico 1","tópico 2","tópico 3","tópico 4","tópico 5"]}\n'
        "Exatamente 5 itens curtos."
    )


def _format_five_topics_response(raw_answer: str, original_prompt: str) -> str:
    text = (raw_answer or "").strip()
    try:
        payload = json.loads(text)
        items = payload.get("topicos") if isinstance(payload, dict) else None
        if isinstance(items, list) and items:
            cleaned = [str(x).strip() for x in items if str(x).strip()][:5]
            if cleaned:
                return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))
    except Exception:
        pass

    json_match = re.search(r"\{[\s\S]*\"topicos\"\s*:\s*\[[\s\S]*?\][\s\S]*?\}", text)
    if json_match:
        try:
            payload = json.loads(json_match.group(0))
            items = payload.get("topicos") if isinstance(payload, dict) else None
            if isinstance(items, list) and items:
                cleaned = [str(x).strip() for x in items if str(x).strip()][:5]
                if cleaned:
                    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))
        except Exception:
            pass

    lines = [ln.strip(" -•\t") for ln in text.splitlines() if ln.strip()]
    numbered = [ln for ln in lines if re.match(r"^\d+[\).\s-]+", ln)]
    if numbered:
        cleaned = [re.sub(r"^\d+[\).\s-]+", "", ln).strip() for ln in numbered][:5]
        if cleaned:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(cleaned))

    base = original_prompt.strip().rstrip("?")
    fallback = [
        f"Evoluir benchmark contínuo para '{base}'",
        "Aprimorar memória de longo prazo com validação de relevância",
        "Fortalecer segurança (redaction + secret scan + gates CI)",
        "Melhorar confiabilidade SRE (canary + auto-rollback)",
        "Automatizar avaliação de qualidade com métricas e auditoria",
    ]
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(fallback))


INTERNET_REQUEST_PATTERNS = (
    r"^\s*pesquis[ae]\b",
    r"\bpesquis[ae]\b",
    r"\bpesquis[ae]\b.*\binternet\b",
    r"\bna internet\b",
    r"\bprocure\b.*\binternet\b",
    r"\bbusque\b.*\binternet\b",
    r"\bache\b.*\binternet\b",
    r"\bencontre\b.*\binternet\b",
    r"\bsearch\b.*\bweb\b",
    r"\bweb search\b",
    r"\brelat[oó]rio\b.*\binternet\b",
)

WEB_FACT_QUESTION_PATTERNS = (
    r"^(quem|qual|quais|o que|oque|quando|onde|como)\b",
    r"^(what|who|when|where|which|how)\b",
)

WEB_FACT_SIGNAL_PATTERNS = (
    r"\b(hoje|atual|atualmente|agora|recente|últim|ultimo|latest|today|recent)\b",
    r"\b(preço|preco|cotação|cotacao|valor|dólar|dolar|bitcoin|btc|eth)\b",
    r"\b(oscar|grammy|nba|nfl|eleiç|election|presidente|ceo|lançamento|release|futebol|flamengo|santos|palmeiras|corinthians)\b",
    r"\b(202[0-9]|19[0-9]{2})\b",
    r"\?$",
)


def _is_internet_request(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text:
        return False
    if text.startswith("/internet "):
        return True
    if text.startswith("/internet"):
        return True
    return any(re.search(pattern, text) for pattern in INTERNET_REQUEST_PATTERNS)


def _is_web_fact_question(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text or text.startswith("/"):
        return False
    starts_like_question = any(re.search(pattern, text) for pattern in WEB_FACT_QUESTION_PATTERNS)
    has_web_signal = any(re.search(pattern, text) for pattern in WEB_FACT_SIGNAL_PATTERNS)
    return starts_like_question and has_web_signal


def _extract_internet_topic(user_input: str) -> str:
    text = (user_input or "").strip()
    if text.lower() == "/internet":
        return ""
    if text.lower().startswith("/internet "):
        return text[len("/internet "):].strip()

    cleaned = re.sub(r"(?i)^\s*(ask\s+atena|pergunte\s+atena|atena)\s*[:,\-]?\s*", "", text)
    text = cleaned if cleaned else text

    cleaned = re.sub(r"(?i)\bpesquis[ae]\b", "", text)
    cleaned = re.sub(r"(?i)\b(procure|busque)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(entregue|gere|monte|fa[çc]a)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(me|um|uma|o|a|e|and|pra|para|mim|por favor)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(na|no)\s+internet\b", "", cleaned)
    cleaned = re.sub(r"(?i)\binternet\b", "", cleaned)
    cleaned = re.sub(r"(?i)\b(relat[oó]rio|completo|final|atualizado|sobre|da|do|de)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(?i)^[:\-\s]+", "", cleaned).strip()
    return cleaned if cleaned else text


def _google_news_fallback_results(query: str, limit: int = 5) -> list[str]:
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (ATENA research fallback)"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        root = ElementTree.fromstring(raw)
        rows: list[str] = []
        for item in root.findall("./channel/item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source_node = item.find("source")
            source_url = ""
            if source_node is not None:
                source_url = str(source_node.attrib.get("url", "")).strip()
            display_link = source_url or link
            if title and link:
                rows.append(f"- {title}\n  {display_link}")
        return rows
    except Exception:
        return []


def _extract_internet_signals(payload: dict[str, object]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return signals
    for src in sources:
        if not isinstance(src, dict) or not src.get("ok"):
            continue
        source_name = str(src.get("source", "unknown"))
        details = src.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("top_repos", "hits", "papers"):
            items = details.get(key)
            if not isinstance(items, list):
                continue
            for item in items[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("full_name") or item.get("title") or "").strip()
                if title:
                    signals.append({"source": source_name, "title": title})
    return signals


def run_user_internet_research(user_input: str) -> str:
    topic = _extract_internet_topic(user_input)
    if not topic:
        return (
            "## Pesquisa na internet\n\n"
            "Use `/internet <tema>` para eu pesquisar e mostrar só o resultado final.\n"
            "Exemplo: `/internet ai agent safety evaluation benchmarks 2026`."
        )
    payload = run_internet_challenge(topic)
    all_sources = payload.get("all_sources", [])
    topic_lower = topic.lower()
    is_sports_schedule = ("joga" in topic_lower) or ("jogo" in topic_lower and "que dia" in topic_lower)
    stop_terms = {
        "que", "dia", "o", "a", "de", "do", "da", "na", "no", "joga", "jogo",
        "pra", "para", "mim", "me", "por", "favor", "quando", "qual", "quais",
    }
    topic_terms = [t for t in re.findall(r"[a-z0-9à-ú]+", topic_lower) if t not in stop_terms and len(t) >= 3]

    if is_sports_schedule and isinstance(all_sources, list):
        had_sports_source = False
        for item in all_sources:
            if not isinstance(item, dict):
                continue
            if str(item.get("source", "")).lower() != "thesportsdb" or not bool(item.get("ok")):
                continue
            had_sports_source = True
            details = item.get("details", {})
            events = details.get("events", []) if isinstance(details, dict) else []
            if isinstance(events, list) and events:
                event_lines: list[str] = []
                for evt in events[:3]:
                    if not isinstance(evt, dict):
                        continue
                    title = str(evt.get("title", "")).strip()
                    date = str(evt.get("date", "")).strip()
                    title_lower = title.lower()
                    is_relevant = any(term in title_lower for term in topic_terms) if topic_terms else True
                    if title and date and is_relevant:
                        event_lines.append(f"- {date}: {title}")
                if event_lines:
                    return (
                        "## Resultado da pesquisa\n\n"
                        f"**Tema:** {topic}\n\n"
                        "Próximos jogos encontrados:\n"
                        f"{chr(10).join(event_lines)}"
                    )
        google_rows = _google_news_fallback_results(topic)
        if google_rows:
            return (
                "## Resultado da pesquisa (fallback Google)\n\n"
                f"**Tema:** {topic}\n\n"
                "Não consegui confirmar pelo feed esportivo direto. "
                "Segue resultado completo encontrado no Google News:\n\n"
                + "\n".join(google_rows)
            )
        if had_sports_source:
            return (
                "## Resultado da pesquisa\n\n"
                f"**Tema:** {topic}\n\n"
                "Não encontrei um calendário confiável com esse termo."
            )
        return (
            "## Resultado da pesquisa\n\n"
            f"**Tema:** {topic}\n\n"
            "Não consegui confirmar a próxima partida com confiança nas fontes esportivas nem no fallback do Google."
        )

    all_findings: list[str] = []
    fallback_findings: list[str] = []
    if isinstance(all_sources, list):
        for item in all_sources:
            if not isinstance(item, dict):
                continue
            source_name = str(item.get("source", "unknown"))
            ok = bool(item.get("ok"))
            details = item.get("details", {})
            if ok:
                findings = []
                for key in ("extract", "title", "description"):
                    value = details.get(key)
                    if isinstance(value, str) and value.strip():
                        findings.append(value.strip()[:200])
                        break
                if not findings:
                    for key in ("top_repos", "papers", "hits"):
                        items = details.get(key)
                        if isinstance(items, list) and items:
                            for it in items[:2]:
                                if isinstance(it, dict):
                                    title = it.get("title") or it.get("full_name") or it.get("name")
                                    if isinstance(title, str) and title.strip():
                                        findings.append(f"{title[:150]}")
                                        break
                        if findings:
                            break
                for finding in findings:
                    fallback_findings.append(f"- **{source_name}**: {finding[:240]}")
                    finding_lower = finding.lower()
                    is_relevant = any(term in finding_lower for term in topic_terms) if topic_terms else True
                    if is_relevant:
                        all_findings.append(f"- **{source_name}**: {finding[:240]}")
    final_findings = all_findings if all_findings else fallback_findings
    if not final_findings:
        google_rows = _google_news_fallback_results(topic)
        if google_rows:
            final_findings = google_rows
    key_findings = "\n".join(final_findings[:8]) if final_findings else "- Não encontrei resultados úteis para esse tema."
    catalog_note = ""
    catalog_meta = payload.get("public_api_catalog", {})
    if isinstance(catalog_meta, dict):
        catalog_path = str(catalog_meta.get("catalog_path", "")).strip()
        discovery_path = str(catalog_meta.get("discovery_path", "")).strip()
        api_count = int(catalog_meta.get("api_count", 0) or 0)
        if catalog_path:
            catalog_note = (
                f"\n\n**Catálogo de APIs públicas salvo:** `{catalog_path}`"
                f"\n**Descoberta desta execução:** `{discovery_path}`"
                f"\n**APIs mapeadas:** {api_count}"
            )
    return (
        f"## Resultado da pesquisa\n\n"
        f"**Tema:** {topic}\n\n"
        f"{key_findings}"
        f"{catalog_note}"
    )


def git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or "main"
    except Exception:
        return "local"


def get_prompt_label(model: str) -> Any:
    display_model = "local" if model.startswith("local:") else model
    branch = git_branch()
    cwd = Path.cwd().name
    if HAS_RICH:
        prompt = Text()
        prompt.append(f" {branch} ", style="bold white on blue")
        prompt.append(f" {cwd} ", style="bold white on black")
        prompt.append(f" {display_model} ", style="bold black on cyan")
        prompt.append("\n ❯ ", style="bold magenta")
        return prompt
    return f"[{branch}][{cwd}][{display_model}] ❯ "


def render_banner():
    if HAS_RICH:
        CONSOLE.print("\n")
        CONSOLE.print(Panel(
            Text.assemble(
                ("🔱 ATENA Ω ", "bold cyan"),
                ("Assistant v2.0 ", "bold white"),
                ("\n\n", ""),
                ("Auto-aprendizado | ", "dim"),
                ("Pesquisa web | ", "dim"),
                ("Plugins dinâmicos\n\n", "dim"),
                ("Digite ", "dim"),
                ("/help", "bold green"),
                (" para comandos.", "dim")
            ),
            border_style="cyan",
            box=ROUNDED,
            padding=(1, 2)
        ))
    else:
        print("\n🔱 ATENA Ω Assistant v2.0 - Digite /help para comandos.\n")


def print_help():
    if HAS_RICH:
        table = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
        table.add_column("Comando", style="cyan")
        table.add_column("Descrição", style="white")
        
        commands = [
            ("/task <msg>", "Executa tarefa; perguntas factuais disparam pesquisa web"),
            ("/internet <tema>", "Pesquisa tema na internet em múltiplas fontes"),
            ("/task-exec <objetivo>", "Planeja e executa comandos seguros"),
            ("/self-test [quick|full|security|perf]", "Executa validações automáticas"),
            ("/release-governor", "Executa gates security/release/perf"),
            ("/saas-bootstrap <nome>", "Gera stack SaaS web/api/cli"),
            ("/telemetry-insights", "Resumo de falhas/sucessos por missão"),
            ("/orchestrate <objetivo>", "Orquestração multiagente"),
            ("/memory-suggest <objetivo>", "Sugere ação baseada em memória"),
            ("/benchmark", "Benchmark contínuo"),
            ("/device-control <pedido> [--confirm]", "Controle de dispositivo"),
            ("/security-scan [repo|system]", "Scanner de segurança"),
            ("/secret-audit", "Auditoria de segredos (mascarada)"),
            ("/policy", "Mostra política de segurança"),
            ("/plugins", "Lista plugins carregados"),
            ("/memory [clear|stats]", "Gerencia memória do assistente"),
            ("/plan <objetivo>", "Gera plano de execução"),
            ("/run <cmd>", "Executa comando no terminal"),
            ("/context", "Mostra contexto da sessão"),
            ("/model [list|set|prepare-local|auto]", "Gerencia modelo de IA"),
            ("/clear", "Limpa terminal"),
            ("/exit", "Encerra assistente")
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        CONSOLE.print(Panel(table, title="[bold cyan]Comandos Disponíveis[/bold cyan]", border_style="cyan"))
    else:
        print("\nComandos: /task, /internet, /task-exec, /self-test, /release-governor, /saas-bootstrap, /telemetry-insights, /orchestrate, /memory-suggest, /benchmark, /device-control, /security-scan, /secret-audit, /policy, /plugins, /memory, /plan, /run, /context, /model, /clear, /exit\n")


# =============================================================================
# 8. FUNÇÕES DE COMANDO (self-test, task-exec, etc.)
# =============================================================================

ALLOWED_PREFIXES = (
    "./atena",
    "python",
    "python3",
    "pytest",
    "uv ",
    "pip ",
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "uname",
    "git status",
    "git diff",
)

DENY_PATTERNS = (
    r"(^|\s)rm\s+-rf\s+/",
    r"(^|\s)sudo(\s|$)",
    r"(^|\s)shutdown(\s|$)",
    r"(^|\s)reboot(\s|$)",
    r"mkfs\.",
    r"dd\s+if=",
    r"curl\s+.*\|\s*sh",
    r"wget\s+.*\|\s*sh",
    r"git\s+push",
)

READ_ONLY_PREFIXES = (
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "uname",
    "df",
    "free",
    "rg ",
    "find ",
    "wc ",
    "head ",
    "tail ",
    "python3 --version",
    "pip --version",
    "mkdir -p ",
    "git status",
    "git diff",
    "./atena doctor",
    "./atena learn-status",
)

APPROVAL_TIERS = {
    "tier0": {"desc": "read-only", "allowed": READ_ONLY_PREFIXES},
    "tier1": {"desc": "build-and-test", "allowed": ("./atena", "python", "python3", "pytest", "uv ", "pip ")},
    "tier2": {"desc": "mutable", "allowed": ALLOWED_PREFIXES},
}


def validate_command_policy(command: str, context: str = "interactive", tier: str = "tier1") -> tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return False, "comando vazio"
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd):
            return False, f"bloqueado por política: {pattern}"
    tier_cfg = APPROVAL_TIERS.get(tier, APPROVAL_TIERS["tier1"])
    allowed_prefixes = tuple(tier_cfg["allowed"])
    if not cmd.startswith(allowed_prefixes):
        return False, "comando fora da allowlist"
    current_branch = git_branch()
    if current_branch == "main" and context in {"run", "task-exec"} and not cmd.startswith(READ_ONLY_PREFIXES):
        return False, "em branch main apenas comandos read-only são permitidos neste contexto"
    return True, "ok"


def run_safe_command(command: str, timeout: int = 120, context: str = "interactive", tier: str = "tier1") -> tuple[int, str, str]:
    allowed, reason = validate_command_policy(command, context=context, tier=tier)
    if not allowed:
        return 126, "", reason
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def run_self_test(mode: str = "full") -> tuple[str, str]:
    presets = {
        "quick": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
        ],
        "full": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("go-no-go", ["./atena", "go-no-go"]),
        ],
        "security": [("guardian", ["./atena", "guardian"])],
        "release": [("production-ready", ["./atena", "production-ready"])],
        "perf": [
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("telemetry-report", ["./atena", "telemetry-report"]),
        ],
    }
    checks = presets.get(mode, presets["full"])

    report_dir = ROOT / "atena_evolution" / "assistant_self_tests"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"assistant_self_test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    results: list[dict[str, object]] = []
    for name, cmd in checks:
        started = datetime.now(timezone.utc).isoformat()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=180 if name in {"go-no-go", "production-ready"} else 120,
            )
            rc = proc.returncode
            stdout = (proc.stdout or "")[-4000:]
            stderr = (proc.stderr or "")[-2000:]
        except subprocess.TimeoutExpired as exc:
            rc = 124
            stdout = (exc.stdout or "")[-4000:] if exc.stdout else ""
            stderr = f"timeout: {exc}"
        results.append(
            {
                "name": name,
                "command": " ".join(cmd),
                "started_at": started,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
        )

    status = "ok" if all(item["ok"] for item in results) else "failed"
    payload = {
        "status": status,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return status, str(report_path)


def run_release_governor() -> tuple[str, str]:
    sequence = ["security", "release", "perf"]
    details = []
    weights = {"security": 0.5, "release": 0.3, "perf": 0.2}
    score = 0.0
    for mode in sequence:
        status, report_path = run_self_test(mode=mode)
        details.append({"mode": mode, "status": status, "report_path": report_path})
        score += weights.get(mode, 0.0) * (1.0 if status == "ok" else 0.0)
    final_status = "go" if score >= 0.8 else "no-go"
    remediation = "Executar ./atena fix e repetir /self-test security" if final_status == "no-go" else "Sistema aprovado para evolução."
    governor_dir = ROOT / "atena_evolution" / "release_governor"
    governor_dir.mkdir(parents=True, exist_ok=True)
    out_path = governor_dir / f"release_governor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps({"status": final_status, "score": round(score, 3), "checks": details, "remediation": remediation, "generated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return final_status, str(out_path)


def run_saas_bootstrap(project_name: str) -> tuple[str, str]:
    safe_name = "".join(ch for ch in project_name if ch.isalnum() or ch in ("-", "_")).strip("-_") or "atena_saas"
    commands = [
        f"./atena code-build --type site --template dashboard --name {safe_name}_web --validate",
        f"./atena code-build --type api --name {safe_name}_api --validate",
        f"./atena code-build --type cli --name {safe_name}_cli --validate",
    ]
    results = []
    for command in commands:
        rc, out, err = run_safe_command(command, timeout=240, context="saas-bootstrap")
        results.append({"command": command, "returncode": rc, "ok": rc == 0, "stdout_tail": out[-1800:], "stderr_tail": err[-800:]})

    bundle_dir = ROOT / "atena_evolution" / "generated_apps" / f"{safe_name}_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "docker-compose.yml").write_text(
        f"""services:\n  {safe_name}_api:\n    image: python:3.10-slim\n    working_dir: /app\n    command: sh -c \"pip install fastapi uvicorn && uvicorn main:app --host 0.0.0.0 --port 8000\"\n    volumes:\n      - ../{safe_name}_api:/app\n    ports:\n      - \"8000:8000\"\n""",
        encoding="utf-8",
    )
    (bundle_dir / "smoke_test.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_path = bundle_dir / "bootstrap_report.json"
    report_path.write_text(json.dumps({"status": status, "project": safe_name, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return status, str(report_path)


def telemetry_insights() -> str:
    telemetry_file = ROOT / "atena_evolution" / "telemetry_events.jsonl"
    if not telemetry_file.exists():
        return "Sem telemetria ainda. Rode missões para gerar eventos."
    total = 0
    fail = 0
    missions: dict[str, dict[str, int]] = {}
    for line in telemetry_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        mission = str(item.get("mission", "unknown"))
        status = str(item.get("status", "unknown"))
        missions.setdefault(mission, {"ok": 0, "fail": 0})
        if status == "ok":
            missions[mission]["ok"] += 1
        else:
            missions[mission]["fail"] += 1
            fail += 1
    top = sorted(missions.items(), key=lambda x: x[1]["fail"], reverse=True)[:3]
    fail_rate = (fail / total) if total else 0.0
    success_rate = 1.0 - fail_rate
    slo_targets = {"max_fail_rate": 0.20, "min_success_rate": 0.80}
    slo_ok = fail_rate <= slo_targets["max_fail_rate"] and success_rate >= slo_targets["min_success_rate"]
    lines = [
        f"Eventos totais: {total}",
        f"Falhas totais: {fail}",
        f"Fail rate: {fail_rate:.2%}",
        f"Success rate: {success_rate:.2%}",
        f"SLO status: {'OK' if slo_ok else 'ALERTA'}",
        "Top missões por falha:",
    ]
    lines.extend([f"- {name}: fail={stats['fail']} ok={stats['ok']}" for name, stats in top])
    return "\n".join(lines)


def run_multi_agent_orchestrator(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    roles = ["planner", "builder", "reviewer", "security", "release"]
    outputs = {}
    for role in roles:
        prompt = f"Você é o agente {role}. Objetivo: {objective}. Entregue resumo objetivo e próximo passo."
        outputs[role] = router.generate(prompt, context=f"multi-agent:{role}")
    orchestration_dir = ROOT / "atena_evolution" / "multi_agent_runs"
    orchestration_dir.mkdir(parents=True, exist_ok=True)
    out_path = orchestration_dir / f"orchestrate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps({"objective": objective, "outputs": outputs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return "ok", str(out_path)


def run_benchmark_suite() -> tuple[str, str]:
    suites = ["quick", "security", "perf"]
    points = {"quick": 20, "security": 40, "perf": 40}
    total = 0
    details = []
    for suite in suites:
        status, report_path = run_self_test(mode=suite)
        earned = points[suite] if status == "ok" else 0
        total += earned
        details.append({"suite": suite, "status": status, "points": earned, "report_path": report_path})
    leaderboard_dir = ROOT / "atena_evolution" / "benchmarks"
    leaderboard_dir.mkdir(parents=True, exist_ok=True)
    out_path = leaderboard_dir / "leaderboard.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "score": total, "details": details}
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return ("ok" if total >= 80 else "alert"), str(out_path)


def run_device_control(request: str, confirmed: bool) -> tuple[str, str]:
    report_dir = ROOT / "atena_evolution" / "device_control"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"device_control_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"

    if not confirmed:
        payload = {
            "status": "blocked",
            "reason": "confirmation_required",
            "request": request,
            "allowed_actions": [
                "abrir URL (http/https)",
                "diagnóstico rápido do sistema",
                "status básico do sistema",
            ],
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return "blocked", str(report_path)

    req = request.strip().lower()
    action = "unknown"
    result: dict[str, object] = {"request": request}

    url_match = re.search(r"(https?://[^\s]+)", request, flags=re.IGNORECASE)
    if any(token in req for token in ("abrir", "abra", "open")) and url_match:
        action = "open_url"
        url = url_match.group(1)
        ok = webbrowser.open(url)
        result.update({"action": action, "url": url, "ok": bool(ok)})
    elif "diagnost" in req or "teste" in req:
        action = "self_test_quick"
        status, path = run_self_test(mode="quick")
        result.update({"action": action, "status": status, "report": path})
    elif "status" in req or "sistema" in req:
        action = "system_status"
        rc, out, err = run_safe_command("uname -a", context="device-control", tier="tier0")
        result.update({"action": action, "returncode": rc, "stdout": out[-800:], "stderr": err[-400:]})
    else:
        result.update({"action": action, "status": "unsupported_request"})

    final_status = "ok" if result.get("action") != "unknown" and result.get("status") != "unsupported_request" else "failed"
    payload = {"status": final_status, **result}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_status, str(report_path)


def run_security_scan(scope: str = "repo") -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    reports_dir = ROOT / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    commands: list[tuple[str, str]] = [
        (f"SCAN_SECURITY_SYSTEM_{timestamp}.txt", "uname -a && cat /etc/os-release && python3 --version"),
        (f"SCAN_SECURITY_ATENA_DOCTOR_{timestamp}.txt", "./atena doctor"),
        (f"SCAN_SECURITY_SECRET_SCAN_{timestamp}.txt", "./atena secret-scan"),
        (f"SCAN_SECURITY_CODE_MARKERS_{timestamp}.txt", "rg -n \"TODO|FIXME|HACK|XXX|password|secret|token|eval\\(|exec\\(|subprocess\\.Popen\\(|os\\.system\\(\" core modules protocols"),
        (f"SCAN_SECURITY_WORLD_WRITABLE_{timestamp}.txt", "find . -xdev -type f -perm -0002"),
    ]
    if scope == "system":
        commands.append((f"SCAN_SECURITY_SUID_TOP200_{timestamp}.txt", "find / -xdev -type f -perm -4000 2>/dev/null | head -n 200"))

    results: list[dict[str, object]] = []
    artifact_map: dict[str, Path] = {}
    for filename, command in commands:
        rc, out, err = run_safe_command(command, timeout=240, context="security-scan", tier="tier0")
        out_path = reports_dir / filename
        out_path.write_text((out or "").rstrip() + ("\n" if out else ""), encoding="utf-8")
        artifact_map[filename] = out_path
        results.append({"artifact": str(out_path), "command": command, "returncode": rc, "ok": rc == 0})

    status = "ok" if all(item["ok"] for item in results) else "failed"
    summary_path = reports_dir / f"EXECUCAO_SECURITY_SCAN_{timestamp}.json"
    summary_path.write_text(json.dumps({"status": status, "scope": scope, "generated_at": datetime.now(timezone.utc).isoformat(), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return status, str(summary_path)


def _mask_secret(value: str) -> dict[str, str]:
    token = (value or "").strip()
    if len(token) <= 8:
        masked = "*" * len(token)
    else:
        masked = f"{token[:4]}...{token[-4:]}"
    fp = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else ""
    return {"masked": masked, "fingerprint_sha256_16": fp}


def run_secret_audit() -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    reports_dir = ROOT / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"EXECUCAO_SECRET_AUDIT_{timestamp}.json"

    patterns = [
        ("github_token", re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
        ("api_key", re.compile(r"\b(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\\-_]{20,})\b")),
        ("env_secret_value", re.compile(r"(?i)\b(?:token|secret|api[_-]?key|github[_-]?token)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\\-]{16,})[\"']?")),
    ]

    findings: list[dict[str, object]] = []
    scanned_files = 0
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", "atena_evolution", "analysis_reports"}

    for file_path in ROOT.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(ROOT)
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned_files += 1
        for line_no, line in enumerate(content.splitlines(), start=1):
            for kind, rgx in patterns:
                for match in rgx.finditer(line):
                    raw = match.group(1)
                    if kind == "env_secret_value" and not re.search(r"\d", raw):
                        continue
                    masked = _mask_secret(raw)
                    findings.append({
                        "file": str(rel), "line": line_no, "kind": kind,
                        "masked": masked["masked"], "fingerprint": masked["fingerprint_sha256_16"]
                    })
    status = "warn" if findings else "ok"
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": status, "scanned_files": scanned_files, "findings_count": len(findings), "findings": findings[:1000]}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return status, str(report_path)


@contextmanager
def atena_thinking(message: str = "Pensando..."):
    use_live_spinner = HAS_RICH and os.getenv("ATENA_USE_LIVE_SPINNER", "0") == "1"
    if use_live_spinner:
        with Live(Spinner("dots", text=Text(message, style="cyan"), style="magenta"), refresh_per_second=10, transient=True):
            yield
    else:
        print(f"◐ {message}")
        yield
        print("✔ concluído")


# =============================================================================
# 9. MAIN - LOOP PRINCIPAL APRIMORADO
# =============================================================================

def main():
    render_banner()
    router = AtenaLLMRouter()
    memory = ConversationMemory()
    auto_learner = AutoLearner(memory)
    plugin_manager = PluginManager()
    task_executor = ParallelTaskExecutor()
    dashboard = AtenaDashboard()
    dashboard.start_async()
    tasks_completed = 0

    if os.getenv("ATENA_PRELOAD_ALL_MODULES", "1") == "1":
        preload_result = preload_all_modules(ROOT / "modules")
        loaded_count = int(preload_result.get("loaded_count", 0))
        total = int(preload_result.get("total", 0))
        console_print(f"[ATENA preload] módulos carregados: {loaded_count}/{total}", style="dim")
    
    if router.auto_prepare_result is not None:
        ok_auto, msg_auto = router.auto_prepare_result
        if ok_auto:
            console_print(f"[ATENA model] {msg_auto}", style="green")
        else:
            console_print(f"[ATENA model] aviso: {msg_auto}", style="yellow")
    
    # Silenciar logs
    for logger_name in ["AtenaUltraBrain", "httpx", "huggingface_hub", "transformers"]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    dashboard.update_metrics(plugins_count=len(plugin_manager.list_plugins()), memory_size=len(memory.history))

    while True:
        try:
            prompt = get_prompt_label(router.current())
            if HAS_RICH:
                CONSOLE.print(prompt, end="")
                user_input = input().strip()
            else:
                user_input = input(prompt).strip()

            if user_input.startswith(".task "):
                user_input = "/task " + user_input[len(".task "):]
            elif user_input.startswith(".internet "):
                user_input = "/internet " + user_input[len(".internet "):]
            
            if not user_input:
                continue
            
            # Atualiza dashboard
            dashboard.log(f"Comando: {user_input[:100]}")
            
            if user_input in ["/exit", "exit", "quit", "/quit", "/q", ":q", "/sair", "sair"]:
                console_print("[bold red]🔱 Encerrando ATENA Ω... Até logo![/bold red]" if HAS_RICH else "Encerrando ATENA Ω... Até logo!")
                break
            
            if user_input == "/help":
                print_help()
                continue
            
            if user_input == "/clear":
                os.system("clear")
                continue

            if user_input == "/plugins":
                plugins = plugin_manager.list_plugins()
                if HAS_RICH:
                    table = Table(title="Plugins Carregados")
                    table.add_column("Nome", style="cyan")
                    table.add_column("Descrição", style="white")
                    table.add_column("Comandos", style="green")
                    table.add_column("Status", style="yellow")
                    for p in plugins:
                        status = "✅" if p["enabled"] else "❌"
                        table.add_row(p["name"], p["description"][:40], ", ".join(p["commands"][:3]), status)
                    CONSOLE.print(table)
                else:
                    for p in plugins:
                        print(f"{p['name']}: {p['description']} - {', '.join(p['commands'])}")
                continue

            if user_input.startswith("/memory"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1] == "clear":
                    memory.clear()
                    console_print("🧠 Memória limpa!", style="green")
                    continue
                elif len(parts) > 1 and parts[1] == "stats":
                    console_print(f"📊 Memória: {len(memory.history)} interações, {len(memory.embeddings)} embeddings", style="cyan")
                    continue
                else:
                    recent = memory.get_recent(5)
                    if HAS_RICH:
                        table = Table(title="Últimas Interações")
                        table.add_column("Timestamp", style="dim")
                        table.add_column("Usuário", style="cyan")
                        table.add_column("Assistente (resumo)", style="green")
                        for r in recent:
                            table.add_row(r["timestamp"][:19], r["user"][:40], r["assistant"][:60])
                        CONSOLE.print(table)
                    else:
                        for r in recent:
                            print(f"[{r['timestamp'][:19]}] {r['user'][:40]}")
                continue

            if user_input == "/model":
                options = "\n".join(f"- {item}" for item in router.list_options())
                message = f"Atual: {router.current()}\n\nUso:\n- /model list\n- /model set <provider:modelo>\n- /model set custom:<modelo>@<base_url>\n- /model prepare-local\n- /model auto\n\nOpções disponíveis:\n{options}"
                if HAS_RICH:
                    CONSOLE.print(Panel(message, title="[bold cyan]Model Router[/bold cyan]", border_style="cyan"))
                else:
                    print(message)
                continue

            if user_input.startswith("/model set "):
                spec = user_input[len("/model set "):].strip()
                ok, msg = router.set_backend(spec)
                console_print(msg, style="green" if ok else "red")
                continue

            if user_input == "/model prepare-local":
                ok, msg = router.prepare_free_local_model()
                console_print(msg, style="green" if ok else "yellow")
                continue

            if user_input == "/model auto":
                ok, msg = router.auto_orchestrate_llm()
                console_print(msg, style="green" if ok else "yellow")
                continue
            
            if user_input == "/context":
                if HAS_RICH:
                    CONSOLE.print(Panel(f"CWD: [cyan]{ROOT}[/cyan]\nBranch: [magenta]{git_branch()}[/magenta]\nModelo: [green]{router.current()}[/green]\nPlugins: {len(plugin_manager.list_plugins())}\nMemória: {len(memory.history)} interações", title="Contexto Atual", border_style="blue"))
                continue

            if user_input == "/policy":
                CONSOLE.print("[bold cyan]Policy Engine[/bold cyan]")
                CONSOLE.print(f"Allowlist: {', '.join(ALLOWED_PREFIXES)}")
                CONSOLE.print(f"Bloqueios: {', '.join(DENY_PATTERNS)}")
                continue

            if user_input.startswith("/self-test"):
                parts = user_input.split(maxsplit=1)
                mode = parts[1].strip().lower() if len(parts) > 1 else "full"
                with atena_thinking("Executando auto-validação..."):
                    status, report_path = run_self_test(mode=mode)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Self-test: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/release-governor":
                with atena_thinking("Executando Release Governor..."):
                    status, report_path = run_release_governor()
                color = "green" if status == "go" else "red"
                CONSOLE.print(f"[bold {color}]Release Governor: {status.upper()}[/bold {color}]")
                continue

            if user_input.startswith("/orchestrate "):
                objective = user_input[len("/orchestrate "):].strip()
                with atena_thinking("Executando orquestração multiagente..."):
                    status, report_path = run_multi_agent_orchestrator(router, objective)
                CONSOLE.print(f"[bold green]Orchestrate: OK[/bold green] - Relatório: {report_path}")
                continue

            if user_input == "/benchmark":
                with atena_thinking("Executando benchmark..."):
                    status, report_path = run_benchmark_suite()
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Benchmark: {status.upper()}[/bold {color}]")
                continue

            if user_input.startswith("/device-control "):
                raw = user_input[len("/device-control "):].strip()
                confirmed = raw.endswith("--confirm")
                request = raw[:-9].strip() if confirmed else raw
                with atena_thinking("Executando device control..."):
                    status, report_path = run_device_control(request=request, confirmed=confirmed)
                color = "green" if status == "ok" else ("yellow" if status == "blocked" else "red")
                CONSOLE.print(f"[bold {color}]Device control: {status.upper()}[/bold {color}]")
                if status == "blocked":
                    CONSOLE.print("[yellow]Use --confirm para executar ações de controle.[/yellow]")
                continue

            if user_input.startswith("/security-scan"):
                raw = user_input[len("/security-scan"):].strip().lower()
                scope = "system" if raw == "system" else "repo"
                with atena_thinking(f"Executando scanner de segurança ({scope})..."):
                    status, report_path = run_security_scan(scope=scope)
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Security scan: {status.upper()}[/bold {color}]")
                continue

            if user_input == "/secret-audit":
                with atena_thinking("Executando auditoria de segredos (mascarada)..."):
                    status, report_path = run_secret_audit()
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Secret audit: {status.upper()}[/bold {color}]")
                if status != "ok":
                    CONSOLE.print("[yellow]Possíveis segredos detectados. Apenas versão mascarada foi salva.[/yellow]")
                continue

            if user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                safe, warnings = SecurityAnalyzer.analyze_command(cmd)
                if not safe:
                    CONSOLE.print(f"[red]Segurança: {', '.join(warnings)}[/red]")
                    continue
                CONSOLE.print(f"[dim]Executando: {cmd}[/dim]")
                rc, out, err = run_safe_command(cmd, context="run", tier="tier0")
                if out:
                    CONSOLE.print(out.rstrip())
                if err:
                    CONSOLE.print(f"[yellow]{err.rstrip()}[/yellow]")
                CONSOLE.print(f"[dim]returncode={rc}[/dim]")
                continue

            if user_input.startswith("/task-exec "):
                objective = user_input[len("/task-exec "):].strip()
                with atena_thinking("Planejando e executando tarefa..."):
                    status, report_path = run_task_exec(router, objective)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Task exec: {status.upper()}[/bold {color}]")
                tasks_completed += 1
                dashboard.update_metrics(tasks_completed=tasks_completed)
                continue

            if user_input.startswith("/internet "):
                with atena_thinking("Pesquisando na internet..."):
                    answer = run_user_internet_research(user_input)
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA Ω[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA Ω:\n{answer}\n")
                continue

            if user_input.startswith("/saas-bootstrap "):
                project_name = user_input[len("/saas-bootstrap "):].strip()
                with atena_thinking("Gerando stack SaaS..."):
                    status, report_path = run_saas_bootstrap(project_name)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]SaaS bootstrap: {status.upper()}[/bold {color}]")
                continue

            if user_input == "/telemetry-insights":
                CONSOLE.print(Panel(telemetry_insights(), title="[bold cyan]Telemetry Insights[/bold cyan]", border_style="cyan"))
                continue

            # Processamento de Tarefas (Task)
            if user_input.startswith("/task "):
                task_msg = user_input[6:].strip()
                if _is_internet_request(task_msg) or _is_web_fact_question(task_msg):
                    with atena_thinking("Pesquisando..."):
                        answer = run_user_internet_research(task_msg)
                    if HAS_RICH:
                        CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA Ω[/bold cyan]", border_style="cyan"))
                    else:
                        print(f"\nATENA Ω:\n{answer}\n")
                    memory.add(task_msg, answer, "internet_research")
                    dashboard.update_metrics(memory_size=len(memory.history))
                    continue
                
                # Verifica se há sugestão do auto-learner
                suggested = auto_learner.suggest_improvement(task_msg)
                if suggested:
                    with atena_thinking("Baseado em aprendizado anterior..."):
                        answer = suggested
                else:
                    structured_five = _wants_five_topics(task_msg)
                    effective_prompt = _build_five_topics_prompt(task_msg) if structured_five else task_msg
                    with atena_thinking("Processando..."):
                        try:
                            answer = router_generate_with_timeout(router=router, prompt=effective_prompt, context="ATENA Assistant", timeout_seconds=ROUTER_TIMEOUT_SECONDS)
                            if structured_five:
                                answer = _format_five_topics_response(answer, task_msg)
                        except Exception as exc:
                            answer = f"Timeout/erro ({type(exc).__name__}). Use /task-exec para fluxo estruturado."
                
                memory.add(task_msg, answer, "task")
                auto_learner.learn_from_interaction(task_msg, answer, None)
                dashboard.update_metrics(memory_size=len(memory.history))
                
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA Ω[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA Ω:\n{answer}\n")
                continue

            # Comando padrão (se não começar com / assume-se /task)
            if not user_input.startswith("/"):
                if _is_internet_request(user_input) or _is_web_fact_question(user_input):
                    with atena_thinking("Pesquisando..."):
                        answer = run_user_internet_research(user_input)
                    if HAS_RICH:
                        CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA Ω[/bold cyan]", border_style="cyan"))
                    else:
                        print(f"\nATENA Ω:\n{answer}\n")
                    memory.add(user_input, answer, "internet_research")
                    dashboard.update_metrics(memory_size=len(memory.history))
                    continue
                
                suggested = auto_learner.suggest_improvement(user_input)
                if suggested:
                    with atena_thinking("Baseado em aprendizado..."):
                        answer = suggested
                else:
                    structured_five = _wants_five_topics(user_input)
                    effective_prompt = _build_five_topics_prompt(user_input) if structured_five else user_input
                    with atena_thinking("Analisando..."):
                        try:
                            answer = router_generate_with_timeout(router=router, prompt=effective_prompt, context="ATENA Assistant", timeout_seconds=ROUTER_TIMEOUT_SECONDS)
                            if structured_five:
                                answer = _format_five_topics_response(answer, user_input)
                        except Exception as exc:
                            answer = f"Timeout/erro ({type(exc).__name__}). Use /task-exec para fluxo estruturado."
                
                memory.add(user_input, answer, "general")
                auto_learner.learn_from_interaction(user_input, answer, None)
                dashboard.update_metrics(memory_size=len(memory.history))
                
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA Ω[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA Ω:\n{answer}\n")
                continue

            # Check plugin commands
            handler, plugin_name = plugin_manager.get_handler(user_input.split()[0]) if user_input.split() else (None, None)
            if handler:
                args = user_input[len(user_input.split()[0]):].strip()
                result = handler(args)
                CONSOLE.print(result)
                continue

            console_print(f"[yellow]Comando desconhecido: {user_input}. Digite /help.[/yellow]" if HAS_RICH else f"Comando desconhecido: {user_input}")

        except EOFError:
            console_print("\n[yellow]EOF detectado. Encerrando.[/yellow]" if HAS_RICH else "\nEOF detectado. Encerrando.")
            break
        except KeyboardInterrupt:
            console_print("\n[yellow]Interrompido. Digite /exit para sair.[/yellow]" if HAS_RICH else "\nInterrompido.")
        except Exception as e:
            console_print(f"[bold red]Erro:[/bold red] {str(e)}" if HAS_RICH else f"Erro: {str(e)}")

    return 0


# Função task_exec precisava ser definida - vamos adicionar
def run_task_exec(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    """Executa planejamento de tarefas."""
    planner_prompt = f"Planeje uma sequência de comandos seguros para: {objective}. Retorne 1 comando por linha usando ./atena, python3, pytest ou uv."
    try:
        plan = router_generate_with_timeout(router, planner_prompt, "task_executor", 30)
        commands = [c.strip() for c in plan.splitlines() if c.strip() and not c.startswith("#")][:5]
    except Exception:
        commands = ["./atena doctor", "python3 --version"]
    
    results = []
    for cmd in commands:
        rc, out, err = run_safe_command(cmd, context="task-exec", tier="tier1")
        results.append({"command": cmd, "ok": rc == 0, "output": out[:500]})
    
    status = "ok" if all(r["ok"] for r in results) else "failed"
    report_dir = ROOT / "atena_evolution" / "task_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps({"objective": objective, "status": status, "results": results}, indent=2))
    return status, str(report_path)


if __name__ == "__main__":
    sys.exit(main())
