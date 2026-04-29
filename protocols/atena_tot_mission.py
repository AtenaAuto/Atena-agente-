
import logging
import sys
import os

# Adiciona o diretório raiz do projeto ao PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.atena_tot_engine import TreeOfThoughtsEngine, Thought

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] ATENA-TOT - %(message)s')
logger = logging.getLogger(__name__)

def run_tot_mission(problem_statement: str):
    """
    Executa uma missão usando o Motor de Raciocínio por Árvore de Pensamentos da ATENA.
    """
    logger.info(f"Iniciando missão Tree-of-Thoughts para o problema: {problem_statement}")
    
    tot_engine = TreeOfThoughtsEngine(max_thoughts_per_step=3, max_depth=4, value_threshold=0.5)
    solution_content, solution_path = tot_engine.solve(problem_statement)
    
    logger.info("\n--- Caminho da Solução ATENA-TOT ---")
    for i, thought in enumerate(solution_path):
        indent = "  " * i
        logger.info(f"{indent}Passo {i+1}: {thought.content} (Valor: {thought.value:.2f})")
    
    logger.info("\n--- Solução Final ATENA-TOT ---")
    logger.info(solution_content)
    
    return solution_content, solution_path

if __name__ == "__main__":
    problem_1 = "Como a ATENA pode otimizar sua própria arquitetura para maior eficiência energética e cognitiva?"
    run_tot_mission(problem_1)
    
    print("\n" + "="*80)
    problem_2 = "Qual a melhor estratégia para integrar novos módulos de segurança quântica sem comprometer a performance?"
    run_tot_mission(problem_2)
