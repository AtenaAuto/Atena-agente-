import time
import sys
import os

# Adiciona o diretório core ao path para importar os módulos
sys.path.append(os.path.join(os.getcwd(), 'modules'))
sys.path.append(os.path.join(os.getcwd(), 'core'))

try:
    from atena_ui_engine import AtenaUIEngine
except ImportError:
    print("Erro: atena_ui_engine não encontrado. Certifique-se de que o arquivo está no diretório correto.")
    sys.exit(1)

def run_demo():
    ui = AtenaUIEngine()
    ui.clear_screen()
    
    # 1. Header
    ui.print_header("🔱 ATENA NEURAL Ω", "Interface de Comando de Elite v4.2", color="#00D9FF")
    time.sleep(1)
    
    # 2. Logs de Inicialização
    ui.print_log("Inicializando núcleo de processamento...", level="info")
    time.sleep(0.5)
    ui.print_log("Carregando motor DeepSeek-R1-7B...", level="info")
    time.sleep(0.5)
    ui.print_log("Sincronizando com o Live Dashboard...", level="info")
    time.sleep(0.5)
    
    # 3. Status Panel
    status_data = {
        "Versão": "4.2.0-stable",
        "Motor LLM": "DeepSeek-R1 (Thinking Mode)",
        "Agentes": "Coder, Browser, Sec, Data",
        "Uptime": "00:42:15",
        "Status": "ONLINE 🟢"
    }
    ui.print_status_panel("SISTEMA OPERACIONAL", status_data)
    time.sleep(1)
    
    # 4. Tabela de Comandos
    cmds = [
        ("/chat <msg>", "Conversa consciente com a IA"),
        ("/evoluir", "Inicia ciclo de auto-evolução"),
        ("/auto", "Modo autônomo contínuo"),
        ("/status", "Exibe métricas em tempo real"),
        ("/sair", "Encerra a sessão de comando")
    ]
    ui.print_table("COMANDOS DISPONÍVEIS", ["Comando", "Descrição"], cmds)
    time.sleep(1)
    
    # 5. Barra de Progresso
    task_id = ui.start_progress("Executando análise de código...", total=100)
    for i in range(100):
        time.sleep(0.02)
        ui.update_progress(task_id, 1)
    ui.stop_progress()
    ui.print_log("Análise concluída. Nenhuma vulnerabilidade encontrada.", level="info")
    
    # 6. Exemplo de Código
    ui.print_log("Gerando sugestão de otimização...", level="info")
    code = """
# Otimização de busca binária gerada pela ATENA
def binary_search(arr, x):
    low = 0
    high = len(arr) - 1
    mid = 0
    while low <= high:
        mid = (high + low) // 2
        if arr[mid] < x:
            low = mid + 1
        elif arr[mid] > x:
            high = mid - 1
        else:
            return mid
    return -1
"""
    ui.print_code(code)
    
    # 7. Markdown
    ui.print_markdown("""
### 🧠 Insights da ATENA
> "A evolução não é um destino, mas um processo contínuo de refinamento de dados e lógica."

**Próxima Meta:** Integrar o módulo de *Teoria dos Jogos* ao processo de decisão do Orquestrador.
""")
    
    ui.print_log("Demonstração concluída com sucesso.", level="info")
    ui.print_header("FIM DA DEMONSTRAÇÃO", color="green")

if __name__ == "__main__":
    run_demo()
