import json
import sys
from types import ModuleType

from core.atena_subagent_solver import solve_with_subagent


def _exec_generated_module(code: str, module_name: str = "generated_test_module") -> ModuleType:
    module = ModuleType(module_name)
    sys.modules[module_name] = module
    exec(code, module.__dict__, module.__dict__)
    return module


def test_subagent_solver_uses_failure_history(tmp_path):
    history = tmp_path / "telemetry.jsonl"
    history.write_text(
        "\n".join(
            [
                json.dumps({"mission": "pipeline-latency", "status": "fail"}),
                json.dumps({"mission": "pipeline-optimizer", "status": "error"}),
                json.dumps({"mission": "healthy-mission", "status": "ok"}),
            ]
        ),
        encoding="utf-8",
    )

    payload = solve_with_subagent(
        "reduzir latência de pipeline crítico",
        history_path=history,
    )

    assert payload["status"] == "ok"
    assert payload["learning"]["consulted_history"] is True
    assert payload["learning"]["failures_seen"] == 2
    assert payload["learning"]["matched_failures"] >= 1
    assert payload["learning"]["failure_hypotheses"]
    assert any("histórico de falhas" in step.lower() for step in payload["plan"])


def test_subagent_solver_without_history_still_returns_learning_block():
    payload = solve_with_subagent("melhorar confiabilidade do orquestrador")

    assert payload["status"] == "ok"
    assert payload["learning"]["consulted_history"] is False
    assert payload["learning"]["failures_seen"] == 0
    assert payload["learning"]["failure_hypotheses"] == []
    assert "diagnosis" in payload
    assert "fix_suggestion" in payload
    assert payload["complete_response"]


def test_subagent_solver_infers_language_from_examples():
    payload = solve_with_subagent("Use fn main() { let mut x = 1; } e impl para resolver")

    assert payload["status"] == "ok"
    assert payload["inferred_language"] == "rust"
    assert any("linguagem 'rust'" in step.lower() for step in payload["plan"])


def test_subagent_solver_returns_static_bug_diagnosis():
    payload = solve_with_subagent(
        "def media(nums): return sum(nums) / len(nums) if nums else 0; lista=[1,2,3]; print(media(lista[1:]))"
    )

    assert payload["status"] == "ok"
    assert payload["bug_found"] is False
    assert payload["confidence"] >= 0.5
    assert "numpy" in payload["diagnosis"].lower()


def test_subagent_solver_detects_dependency_cycle_and_reports_impossible_order():
    payload = solve_with_subagent(
        "A depende de nada; B depende de A; C depende de A; D depende de B e C; E depende de D; D também depende de E"
    )

    assert payload["status"] == "ok"
    assert payload["bug_found"] is True
    assert "ciclo" in payload["diagnosis"].lower()
    assert "d -> e -> d" in payload["diagnosis"].lower()
    assert payload["inferred_language"] is None


def test_subagent_solver_returns_code_solution_for_balanced_brackets_prompt():
    payload = solve_with_subagent(
        "Escreva uma função Python que valida parênteses, colchetes e chaves balanceados"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "def balanced_brackets" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_lru_prompt():
    payload = solve_with_subagent(
        "Implemente em Python uma LRU Cache do zero, sem usar functools.lru_cache nem OrderedDict. Só com dict e lógica manual. Deve suportar get(key) e put(key, value)."
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class LRUCache" in payload["code_solution"]
    assert "def get(" in payload["code_solution"]
    assert "def put(" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_portuguese_lru_prompt():
    payload = solve_with_subagent(
        "Implemente uma cache que descarta o item menos usado recentemente. Capacidade máxima configurável. Operações: buscar(chave) e inserir(chave, valor). Sem biblioteca."
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class LRUCache" in payload["code_solution"]
    assert "def buscar(" in payload["code_solution"]
    assert "def inserir(" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_socket_http_server_prompt():
    payload = solve_with_subagent(
        "Sem usar nenhuma biblioteca, implemente um servidor HTTP do zero em Python puro com socket na porta 8080; GET /hello -> Hello World; GET /soma?a=3&b=5 -> 8; demais rotas 404"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "import socket" in payload["code_solution"]
    assert "def run_server" in payload["code_solution"]
    assert 'if path == "/hello"' in payload["code_solution"]
    assert 'if path == "/soma"' in payload["code_solution"]
    assert "\\r\\n" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_deadlock_detector_prompt():
    payload = solve_with_subagent(
        "Você tem um grafo direcionado com N nós. Implemente detector de deadlock com processos e recursos, retornando processos em deadlock e ciclo exato."
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "def detect_deadlock" in payload["code_solution"]
    assert "def _find_cycle" in payload["code_solution"]
    assert "resource_owner" in payload["code_solution"]
    assert "Solução completa:" in payload["complete_response"]


def test_subagent_solver_returns_code_solution_for_sort_prompt():
    payload = solve_with_subagent("Peça para evoluir uma função sort para ordenar listas")
    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "def sort_list" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_find_pattern_prompt():
    payload = solve_with_subagent("Evoluir função find_pattern para buscar substring")
    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "def find_pattern" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_rle_prompt():
    payload = solve_with_subagent("Resolver compressão de dados com Run-Length Encoding (RLE)")
    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "def rle_encode" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_atenalang_prompt():
    payload = solve_with_subagent(
        "Implemente um interpretador de uma linguagem minimalista chamada AtenaLang com lexer, parser e interpreter"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class Lexer" in payload["code_solution"]
    assert "class Parser" in payload["code_solution"]
    assert "class Interpreter" in payload["code_solution"]
    assert "def run_atenalang" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_minirdb_prompt():
    payload = solve_with_subagent(
        "Implemente um banco de dados relacional minimalista em Python puro com parser SQL SELECT/INSERT/UPDATE/DELETE/CREATE TABLE/JOIN, storage engine binário, B-Tree index, transaction engine com WAL e query optimizer"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class SQLParser" in payload["code_solution"]
    assert "class BTreeIndex" in payload["code_solution"]
    assert "class MiniRelationalDB" in payload["code_solution"]
    assert "CREATE TABLE users" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_mini_os_prompt():
    payload = solve_with_subagent(
        "Implemente um sistema operacional minimalista em Python com scheduler round-robin preemptivo, memory manager com páginas e LRU, filesystem com inodes e journaling, IPC e shell"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class Scheduler" in payload["code_solution"]
    assert "class MemoryManager" in payload["code_solution"]
    assert "class FileSystem" in payload["code_solution"]
    assert "class IPC" in payload["code_solution"]
    assert "class MiniShell" in payload["code_solution"]
    assert "def demo()" in payload["code_solution"]


def test_generated_mini_os_scheduler_is_round_robin_for_equal_priority():
    payload = solve_with_subagent(
        "Implemente um sistema operacional minimalista em Python com scheduler round-robin preemptivo, memory manager com páginas e LRU, filesystem com inodes e journaling, IPC e shell"
    )
    module = _exec_generated_module(payload["code_solution"], module_name="generated_minios_rr")

    kernel = module.Kernel()
    trace = []

    def make_proc(name: str):
        state = {"n": 0}

        def _fn(k, pid):
            trace.append(name)
            state["n"] += 1
            if state["n"] >= 2:
                k.kill(pid)

        return _fn

    kernel.spawn("p1", make_proc("p1"), priority=5)
    kernel.spawn("p2", make_proc("p2"), priority=5)
    kernel.scheduler.run(kernel, max_ticks=6)

    assert trace[:4] == ["p1", "p1", "p2", "p2"]


def test_generated_mini_os_shell_supports_append_redirect():
    payload = solve_with_subagent(
        "Implemente um sistema operacional minimalista em Python com scheduler round-robin preemptivo, memory manager com páginas e LRU, filesystem com inodes e journaling, IPC e shell"
    )
    module = _exec_generated_module(payload["code_solution"], module_name="generated_minios_append")

    kernel = module.Kernel()
    shell = module.MiniShell(kernel)
    shell.run("mkdir /tmp")
    shell.run("echo abc > /tmp/f.txt")
    shell.run("echo zz >> /tmp/f.txt")

    assert shell.run("cat /tmp/f.txt") == "abczz"


def test_subagent_solver_returns_code_solution_for_http2_tls_websocket_server_prompt():
    payload = solve_with_subagent(
        "Servidor web concorrente com HTTP/2 e TLS, certificados autoassinados, WebSockets e servir arquivos do filesystem"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "asyncio.start_server" in payload["code_solution"]
    assert "set_alpn_protocols" in payload["code_solution"]
    assert "_http2_goaway" in payload["code_solution"]
    assert "Sec-WebSocket-Accept" in payload["code_solution"]
    assert "serve_with_supervisor" in payload["code_solution"]
    assert "if target == \"/health\"" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_atenaquery_prompt():
    payload = solve_with_subagent(
        "Crie uma linguagem AtenaQuery para grafos com lexer, parser, planner e executor com pattern matching, caminhos *1..3 e filtro WHERE"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class AtenaQueryLexer" in payload["code_solution"]
    assert "class AtenaQueryParser" in payload["code_solution"]
    assert "class AtenaQueryPlanner" in payload["code_solution"]
    assert "class AtenaQueryExecutor" in payload["code_solution"]
    assert "def build_demo_graph" in payload["code_solution"]
    assert "def demo()" in payload["code_solution"]


def test_subagent_solver_returns_code_solution_for_open_world_meta_agent_prompt():
    payload = solve_with_subagent(
        "Crie um meta-agente que aprende a aprender em mundo aberto com curiosidade intrínseca, modelagem de mundo, MCTS, transferência entre ambientes e recompensas esparsas"
    )

    assert payload["status"] == "ok"
    assert payload["code_solution"] is not None
    assert "class MetaAgent" in payload["code_solution"]
    assert "class WorldModel" in payload["code_solution"]
    assert "class MCTSPlanner" in payload["code_solution"]
    assert "class MiniPongEnv" in payload["code_solution"]
    assert "class MiniGo5x5CaptureEnv" in payload["code_solution"]
    assert "class BlockStackEnv" in payload["code_solution"]
    assert "class NovelMazeEnv" in payload["code_solution"]
    assert "def run_open_world_benchmark" in payload["code_solution"]
    assert "meta_agent_validation" in payload
    validation = payload["meta_agent_validation"]
    assert validation["executed"] is True
    assert "report" in validation
    assert validation["meets_10k_constraint"] is True
    assert "generalized_to_unseen_env" in validation


def test_subagent_solver_returns_capability_portfolio_for_9_domain_prompt():
    payload = solve_with_subagent(
        "Atena agora que tem windows: 1. Desenvolvimento de Software Autônomo 2. Infraestrutura como Código "
        "3. Segurança Ofensiva e Defensiva 4. Educação e Pesquisa 5. Automação de Tarefas Complexas "
        "6. Entretenimento e Jogos 7. Simulação e Modelagem 8. Saúde e Biologia 9. Internet das Coisas"
    )

    assert payload["status"] == "ok"
    assert payload["complete_response"]
    assert "Portfólio de Capacidades (9 trilhas)" in payload["complete_response"]
    assert "Trilha 1" in payload["complete_response"]
    assert "Trilha 9" in payload["complete_response"]
