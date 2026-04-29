import sys
import os
import time
import logging

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.multi_agent_orchestrator import MultiAgentOrchestrator, Agent

# Configuração de logging para ver a delegação em tempo real
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [🔱 ORQUESTRADOR] %(message)s",
    datefmt="%H:%M:%S"
)

def main():
    print("\n" + "="*60)
    print("🔱 DEMONSTRAÇÃO: ORQUESTRADOR MULTI-AGENTE ATENA 🔱")
    print("="*60 + "\n")

    # 1. Inicializa o Orquestrador
    orchestrator = MultiAgentOrchestrator()

    # 2. Define as funções de processamento dos agentes (Handlers)
    def coder_handler(task):
        print(f"   [Coder] 💻 Gerando código para: {task['description']}...")
        time.sleep(1.5)
        return f"Código Python para {task['description']} gerado com sucesso."

    def security_handler(task):
        print(f"   [Security] 🛡️ Auditando segurança de: {task['target']}...")
        time.sleep(1.0)
        return f"Auditoria de {task['target']} concluída: 0 vulnerabilidades críticas."

    def data_handler(task):
        print(f"   [Data] 📊 Analisando dataset: {task['dataset_name']}...")
        time.sleep(2.0)
        return f"Análise de {task['dataset_name']} finalizada com insights estatísticos."

    # 3. Cria e registra os agentes especializados
    agente_programador = Agent(
        agent_id="ATENA-Coder-01",
        role="Desenvolvedor",
        capabilities=["python", "code_gen"],
        task_handler=coder_handler
    )

    agente_seguranca = Agent(
        agent_id="ATENA-Sec-01",
        role="Auditor de Segurança",
        capabilities=["security_audit", "vulnerability_scan"],
        task_handler=security_handler
    )

    agente_analista = Agent(
        agent_id="ATENA-Data-01",
        role="Cientista de Dados",
        capabilities=["data_analysis", "statistics"],
        task_handler=data_handler
    )

    orchestrator.register_agent(agente_programador)
    orchestrator.register_agent(agente_seguranca)
    orchestrator.register_agent(agente_analista)

    # 4. Inicia o orquestrador (abre a thread de processamento)
    orchestrator.start()
    time.sleep(1)

    # 5. Submete tarefas com diferentes requisitos de capacidade
    print("\n--- Submetendo Tarefas ao Orquestrador ---\n")

    # Tarefa 1: Requer Python e Code Gen (Vai para o Coder)
    orchestrator.submit_task({
        "description": "Script de Automação de Backup",
        "required_capabilities": ["python", "code_gen"]
    })

    # Tarefa 2: Requer Auditoria de Segurança (Vai para o Sec)
    orchestrator.submit_task({
        "description": "Verificação de Firewall",
        "target": "Rede Interna v4",
        "required_capabilities": ["security_audit"]
    })

    # Tarefa 3: Requer Análise de Dados (Vai para o Data)
    orchestrator.submit_task({
        "description": "Relatório de Evolução Mensal",
        "dataset_name": "atena_evolution_logs",
        "required_capabilities": ["data_analysis"]
    })

    # Tarefa 4: Requer capacidade que nenhum agente tem (Ficará na fila)
    orchestrator.submit_task({
        "description": "Tradução para Latim Arcaico",
        "required_capabilities": ["translation_latin"]
    })

    # 6. Aguarda o processamento paralelo
    print("\n--- Aguardando Delegação e Execução Paralela ---\n")
    time.sleep(6)

    # 7. Finaliza
    orchestrator.stop()
    print("\n" + "="*60)
    print("🔱 DEMONSTRAÇÃO CONCLUÍDA 🔱")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
