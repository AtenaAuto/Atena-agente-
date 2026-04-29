import logging
import threading
import time
from typing import Dict, List, Any, Callable, Optional
from queue import Queue, Empty
from .atena_control_bridge import AtenaControlBridge

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, agent_id: str, role: str, capabilities: List[str], task_handler: Callable[[Dict[str, Any]], Any]):
        self.agent_id = agent_id
        self.role = role
        self.capabilities = capabilities
        self.task_handler = task_handler
        self.status = "idle"
        logger.info(f"Agente {self.agent_id} ({self.role}) criado com capacidades: {', '.join(self.capabilities)}")

    def assign_task(self, task: Dict[str, Any]) -> Any:
        self.status = "working"
        logger.info(f"Agente {self.agent_id} recebendo tarefa: {task.get('description', 'Sem descrição')}")
        try:
            result = self.task_handler(task)
            self.status = "idle"
            logger.info(f"Agente {self.agent_id} concluiu a tarefa.")
            return result
        except Exception as e:
            self.status = "idle"
            logger.error(f"Agente {self.agent_id} falhou na tarefa: {e}")
            raise

class MultiAgentOrchestrator:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.task_queue = Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self.max_retries = 3

    def register_agent(self, agent: Agent):
        if agent.agent_id in self.agents:
            logger.warning(f"Agente com ID {agent.agent_id} já registrado. Sobrescrevendo.")
        self.agents[agent.agent_id] = agent
        logger.info(f"Agente {agent.agent_id} registrado. Total de agentes: {len(self.agents)}")

    def _worker_loop(self):
        bridge = AtenaControlBridge()
        while not self._stop_event.is_set():
            # Verifica se o sistema está pausado via Bridge
            if bridge.is_paused():
                logger.info("Orquestrador em PAUSA. Aguardando sinal de retomada...")
                time.sleep(2)
                continue

            try:
                task = self.task_queue.get(timeout=1)
                logger.info(f"Orquestrador: Nova tarefa na fila: {task.get('description', 'Sem descrição')}")
                assigned = False
                task.setdefault("_retries", 0)
                for agent_id, agent in self.agents.items():
                    if agent.status == "idle" and all(cap in agent.capabilities for cap in task.get("required_capabilities", [])):
                        try:
                            agent.assign_task(task)
                            assigned = True
                            break
                        except Exception:
                            # Se o agente falhar, tentar outro ou re-enfileirar
                            logger.warning(f"Agente {agent_id} falhou na tarefa, tentando outro ou re-enfileirando.")
                            task["_retries"] += 1
                            if task["_retries"] <= self.max_retries:
                                self.task_queue.put(task)
                            else:
                                logger.error(
                                    "Tarefa descartada após %s tentativas: %s",
                                    self.max_retries,
                                    task.get("description", "Sem descrição")
                                )
                            break
                if not assigned:
                    task["_retries"] += 1
                    if task["_retries"] <= self.max_retries:
                        logger.warning(
                            "Nenhum agente disponível/capaz para tarefa: %s. Tentativa %s/%s.",
                            task.get('description', 'Sem descrição'),
                            task["_retries"],
                            self.max_retries
                        )
                        self.task_queue.put(task)
                    else:
                        logger.error(
                            "Tarefa sem agente compatível foi descartada após %s tentativas: %s",
                            self.max_retries,
                            task.get('description', 'Sem descrição')
                        )
                self.task_queue.task_done()
            except Empty:
                continue
            except Exception as exc:
                logger.exception("Erro inesperado no worker do orquestrador: %s", exc)

    def start(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            logger.info("Orquestrador de Multi-Agentes iniciado.")

    def stop(self):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5) # Espera um pouco para o worker terminar
            logger.info("Orquestrador de Multi-Agentes parado.")

    def submit_task(self, task: Dict[str, Any]):
        logger.info(f"Orquestrador: Tarefa submetida: {task.get('description', 'Sem descrição')}")
        self.task_queue.put(task)

# Exemplo de uso (para testes)
if __name__ == "__main__":
    import random
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    def code_generation_agent_handler(task: Dict[str, Any]) -> str:
        prompt = task["prompt"]
        # Simula a geração de código por uma LLM
        time.sleep(random.uniform(0.5, 2.0))
        return f"Script Python gerado para: {prompt}"

    def data_analysis_agent_handler(task: Dict[str, Any]) -> Dict[str, Any]:
        data = task["data"]
        # Simula análise de dados
        time.sleep(random.uniform(0.3, 1.5))
        return {"analysis_result": f"Análise de {len(data)} pontos de dados concluída."}

    orchestrator = MultiAgentOrchestrator()

    agent_coder = Agent("CoderAgent", "Developer", ["code_generation", "python"], code_generation_agent_handler)
    agent_analyst = Agent("AnalystAgent", "Data Scientist", ["data_analysis", "statistics"], data_analysis_agent_handler)

    orchestrator.register_agent(agent_coder)
    orchestrator.register_agent(agent_analyst)

    orchestrator.start()

    orchestrator.submit_task({"description": "Gerar script de monitoramento", "prompt": "monitoramento de rede", "required_capabilities": ["code_generation", "python"]})
    orchestrator.submit_task({"description": "Analisar logs de sistema", "data": [1,2,3,4,5], "required_capabilities": ["data_analysis"]})
    orchestrator.submit_task({"description": "Gerar script de relatório", "prompt": "relatório financeiro", "required_capabilities": ["code_generation", "python"]})
    orchestrator.submit_task({"description": "Tarefa sem agente capaz", "required_capabilities": ["unknown_capability"]})

    time.sleep(5) # Deixa as tarefas rodarem
    orchestrator.stop()
    print("\nOrquestrador parado. Verifique os logs acima para os resultados das tarefas.")
