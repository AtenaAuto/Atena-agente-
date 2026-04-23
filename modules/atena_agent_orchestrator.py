import threading
import queue
import time

class Agent(threading.Thread):
    def __init__(self, name, task_queue, result_queue):
        super().__init__()
        self.name = name
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        while True:
            try:
                task = self.task_queue.get(timeout=1)
            except queue.Empty:
                break
            print(f"[{self.name}] Executando: {task['desc']}")
            # Simula processamento
            time.sleep(task['duration'])
            result = f"Resultado de {task['desc']} por {self.name}"
            self.result_queue.put(result)
            self.task_queue.task_done()

def main():
    task_queue = queue.Queue()
    result_queue = queue.Queue()

    # Definir tarefas a serem distribuídas
    tasks = [
        {'desc': 'Análise de segurança', 'duration': 2},
        {'desc': 'Refatoração de módulo', 'duration': 3},
        {'desc': 'Pesquisa de algoritmo', 'duration': 4},
    ]
    for task in tasks:
        task_queue.put(task)

    # Criar sub-agentes especializados
    agents = [
        Agent('Segurança', task_queue, result_queue),
        Agent('Codificação', task_queue, result_queue),
        Agent('Pesquisa', task_queue, result_queue),
    ]

    for agent in agents:
        agent.start()

    task_queue.join()

    # Coletar resultados
    while not result_queue.empty():
        print(f"[Orquestrador] {result_queue.get()}")

if __name__ == "__main__":
    main()