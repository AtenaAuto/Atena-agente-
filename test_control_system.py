import sys
import os
import time
import threading
import logging

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.multi_agent_orchestrator import MultiAgentOrchestrator, Agent
from modules.atena_control_bridge import AtenaControlBridge

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 TESTE-CONTROLE] %(message)s",
    datefmt="%H:%M:%S"
)

def dummy_handler(task):
    logging.info(f"Executando: {task['description']}")
    time.sleep(2)
    return "Concluído"

def main():
    bridge = AtenaControlBridge()
    orchestrator = MultiAgentOrchestrator()
    
    # Garante que comece rodando
    bridge.send_command("resume")
    
    agent = Agent(
        agent_id="Test-Agent",
        role="Tester",
        capabilities=["test"],
        task_handler=dummy_handler
    )
    orchestrator.register_agent(agent)
    orchestrator.start()
    
    print("\n--- Iniciando Teste de Controle ---")
    
    # Submete tarefas
    for i in range(5):
        orchestrator.submit_task({
            "description": f"Tarefa de Teste #{i+1}",
            "required_capabilities": ["test"]
        })
    
    time.sleep(3)
    
    print("\n⏸️ Enviando comando de PAUSA via Bridge...")
    bridge.send_command("pause")
    
    print("Aguardando 5 segundos (nenhuma nova tarefa deve ser iniciada)...")
    time.sleep(5)
    
    print("\n▶️ Enviando comando de RETOMADA via Bridge...")
    bridge.send_command("resume")
    
    time.sleep(10)
    orchestrator.stop()
    print("\n--- Teste de Controle Finalizado ---")

if __name__ == "__main__":
    main()
