import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich.syntax import Syntax
from rich.markdown import Markdown

class AtenaUIEngine:
    def __init__(self):
        self.console = Console()
        self.layout = Layout(name="root")
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        )
        self.live_display = None

    def print_header(self, title: str, subtitle: str = "", color: str = "#00D9FF"):
        self.console.print(
            Panel(
                Align.center(
                    Text(title, style=f"bold {color} on black") + 
                    (Text(f"\n{subtitle}", style="dim white on black") if subtitle else ""),
                    vertical="middle"
                ),
                border_style=f"bold {color}",
                padding=(1, 2),
                width=self.console.width
            )
        )

    def print_status_panel(self, title: str, status_data: dict, color: str = "#00D9FF"):
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold white")
        table.add_column(style="#00FF00")

        for key, value in status_data.items():
            table.add_row(key, str(value))

        self.console.print(
            Panel(
                table,
                title=f"[bold {color}]{title}[/bold {color}]",
                border_style=f"dim {color}",
                expand=True
            )
        )

    def print_log(self, message: str, level: str = "info"):
        if level == "info":
            self.console.print(f"[blue]INFO[/blue] {message}")
        elif level == "warning":
            self.console.print(f"[yellow]WARN[/yellow] {message}")
        elif level == "error":
            self.console.print(f"[red]ERRO[/red] {message}")
        elif level == "debug":
            self.console.print(f"[dim grey]DEBUG[/dim grey] {message}")
        else:
            self.console.print(message)

    def print_markdown(self, markdown_text: str):
        self.console.print(Markdown(markdown_text, style="white"))

    def print_code(self, code: str, language: str = "python"):
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(Panel(syntax, border_style="green"))

    def start_progress(self, description: str, total: int = 100):
        task_id = self.progress.add_task(description, total=total)
        if not self.live_display:
            self.live_display = Live(self.progress, refresh_per_second=4, console=self.console)
            self.live_display.start()
        return task_id

    def update_progress(self, task_id, advance: int = 1):
        self.progress.advance(task_id, advance=advance)

    def stop_progress(self):
        if self.live_display:
            self.live_display.stop()
            self.live_display = None

    def clear_screen(self):
        self.console.clear()

    def prompt(self, message: str) -> str:
        return self.console.input(f"[bold #00D9FF]ATENA >[/bold #00D9FF] [white]{message}[/white] ")

    def print_table(self, title: str, headers: list, rows: list, color: str = "#00D9FF"):
        table = Table(title=f"[bold {color}]{title}[/bold {color}]", border_style=f"dim {color}")
        for header in headers:
            table.add_column(header, style="bold white")
        for row in rows:
            table.add_row(*[str(item) for item in row])
        self.console.print(table)

# Exemplo de uso (para testes)
if __name__ == "__main__":
    ui = AtenaUIEngine()
    ui.clear_screen()
    ui.print_header("ATENA NEURAL", "Sistema de Auto-Evolução v4.2", color="#00D9FF")

    ui.print_log("Inicializando módulos...", level="info")
    ui.print_log("Carregando motor DeepSeek-R1...", level="info")

    status_data = {
        "Geração": 42,
        "Score Atual": "0.98",
        "Agentes Ativos": 4,
        "LLM": "DeepSeek-R1-7B"
    }
    ui.print_status_panel("Status do Sistema", status_data, color="#00D9FF")

    ui.print_markdown("""
# Relatório de Progresso

Este é um relatório **dinâmico** gerado pela ATENA. 
Ele mostra o status atual dos ciclos de evolução e as métricas chave.

## Próximos Passos
- Otimizar o algoritmo de busca.
- Integrar novos datasets.
""")

    code_example = """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

for i in fibonacci(10):
    print(i)
"""
    ui.print_code(code_example, language="python")

    task_id = ui.start_progress("Executando ciclo de evolução", total=100)
    for i in range(100):
        time.sleep(0.05)
        ui.update_progress(task_id)
    ui.stop_progress()

    headers = ["Comando", "Descrição"]
    rows = [
        ["/chat <msg>", "Conversa consciente com a Atena"],
        ["/evoluir", "Inicia um ciclo de auto-evolução"],
        ["/status", "Exibe o status atual do sistema"],
    ]
    ui.print_table("Comandos Disponíveis", headers, rows, color="#00D9FF")

    user_input = ui.prompt("O que você gostaria de fazer?")
    ui.print_log(f"Você digitou: {user_input}")

    ui.print_header("Sessão Encerrada", color="red")
