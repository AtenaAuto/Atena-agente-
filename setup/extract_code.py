from pathlib import Path
import sys

def extract():
    report_path = Path('atena_evolution/tech_frontier_expansion_report.md')
    if not report_path.exists():
        print("Relatório não encontrado")
        return
    
    content = report_path.read_text()
    start_marker = '```python'
    end_marker = '```'
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Início do código não encontrado")
        return
    
    start_idx += len(start_marker)
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("Fim do código não encontrado")
        return
        
    code = content[start_idx:end_idx].strip()
    output_path = Path('modules/atena_agent_orchestrator.py')
    output_path.write_text(code)
    print(f"Módulo {output_path} criado com sucesso")

if __name__ == "__main__":
    extract()
