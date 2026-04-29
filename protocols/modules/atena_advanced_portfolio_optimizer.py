#!/usr/bin/env python3
"""
atena_advanced_portfolio_optimizer.py

Módulo avançado de otimização de portfólio financeiro utilizando:
- Algoritmo Genético para seleção de ativos
- Simulação de Monte Carlo para análise de risco
- Fronteira Eficiente de Markowitz
- Índice de Sharpe como função de fitness

Dependências: numpy, scipy, matplotlib
"""

import numpy as np
import scipy.optimize as sco
import matplotlib.pyplot as plt
import json
import os


class PortfolioOptimizer:
    """
    Otimizador avançado de portfólio financeiro.

    Métodos:
    - monte_carlo_simulation(n_portfolios=5000): gera portfólios aleatórios e calcula retorno/risco.
    - genetic_algorithm_optimize(generations=50): usa algoritmo genético para encontrar portfólio ótimo.
    - efficient_frontier(): calcula e plota a fronteira eficiente.
    - sharpe_ratio(returns, risk, risk_free=0.02): calcula índice de Sharpe.
    """

    def __init__(self, returns, cov_matrix, asset_names, risk_free_rate=0.02):
        """
        Inicializa o otimizador com os dados dos ativos.

        :param returns: np.array com retornos anuais esperados dos ativos.
        :param cov_matrix: matriz de covariância dos retornos.
        :param asset_names: lista de strings com nomes dos ativos.
        :param risk_free_rate: taxa livre de risco anual.
        """
        self.returns = returns
        self.cov = cov_matrix
        self.n_assets = len(returns)
        self.asset_names = asset_names
        self.risk_free_rate = risk_free_rate

        # Validar dimensões
        if self.cov.shape != (self.n_assets, self.n_assets):
            raise ValueError("Dimensão da matriz de covariância incompatível com número de ativos.")
        if len(asset_names) != self.n_assets:
            raise ValueError("Número de nomes de ativos diferente do número de ativos.")

    def sharpe_ratio(self, returns, risk, risk_free=None):
        """
        Calcula o índice de Sharpe.

        :param returns: retorno esperado do portfólio.
        :param risk: volatilidade do portfólio.
        :param risk_free: taxa livre de risco (se None, usa a configurada no objeto).
        :return: índice de Sharpe.
        """
        if risk_free is None:
            risk_free = self.risk_free_rate
        if risk == 0:
            return 0  # Evitar divisão por zero
        return (returns - risk_free) / risk

    def monte_carlo_simulation(self, n_portfolios=5000, seed=42):
        """
        Realiza simulação de Monte Carlo gerando portfólios aleatórios.

        :param n_portfolios: número de portfólios simulados.
        :param seed: semente para reprodutibilidade.
        :return: dict com arrays de pesos, retornos, riscos e sharpe ratios.
        """
        np.random.seed(seed)
        weights = np.random.dirichlet(np.ones(self.n_assets), size=n_portfolios)
        portfolio_returns = weights.dot(self.returns)
        portfolio_risks = np.sqrt(np.einsum('ij,jk,ik->i', weights, self.cov, weights))
        sharpe_ratios = np.array([self.sharpe_ratio(r, s) for r, s in zip(portfolio_returns, portfolio_risks)])

        return {
            "weights": weights,
            "returns": portfolio_returns,
            "risks": portfolio_risks,
            "sharpe": sharpe_ratios
        }

    def efficient_frontier(self, points=100):
        """
        Calcula e plota a fronteira eficiente usando otimização quadrática.

        :param points: número de pontos na fronteira.
        :return: dict com retornos, riscos e pesos dos portfólios da fronteira.
        """
        def portfolio_volatility(weights):
            return np.sqrt(weights.T @ self.cov @ weights)

        frontier_returns = np.linspace(min(self.returns)*0.8, max(self.returns)*1.2, points)
        frontier_risks = []
        frontier_weights = []

        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})

        for target_return in frontier_returns:
            cons = (
                constraints,
                {'type': 'eq', 'fun': lambda x, r=target_return: x.dot(self.returns) - r}
            )
            result = sco.minimize(portfolio_volatility,
                                  x0=np.ones(self.n_assets) / self.n_assets,
                                  bounds=bounds,
                                  constraints=cons,
                                  method='SLSQP',
                                  options={'disp': False})
            if result.success:
                frontier_risks.append(result.fun)
                frontier_weights.append(result.x)
            else:
                frontier_risks.append(np.nan)
                frontier_weights.append(np.full(self.n_assets, np.nan))

        frontier_risks = np.array(frontier_risks)
        frontier_weights = np.array(frontier_weights)

        # Plotar fronteira eficiente
        plt.figure(figsize=(10, 6))
        plt.plot(frontier_risks, frontier_returns, 'b--', linewidth=2, label='Fronteira Eficiente')
        plt.xlabel('Risco (Volatilidade Anual)')
        plt.ylabel('Retorno Esperado Anual')
        plt.title('Fronteira Eficiente de Markowitz')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

        return {
            "returns": frontier_returns,
            "risks": frontier_risks,
            "weights": frontier_weights
        }

    def genetic_algorithm_optimize(self, generations=50, population_size=100,
                                   tournament_size=5, crossover_rate=0.8,
                                   mutation_rate=0.15, mutation_std=0.05, seed=42):
        """
        Otimiza os pesos do portfólio usando Algoritmo Genético.

        :param generations: número de gerações.
        :param population_size: tamanho da população.
        :param tournament_size: tamanho do torneio para seleção.
        :param crossover_rate: probabilidade de crossover.
        :param mutation_rate: probabilidade de mutação.
        :param mutation_std: desvio padrão da mutação gaussiana.
        :param seed: semente para reprodutibilidade.
        :return: dict com melhor portfólio (pesos, retorno, risco, sharpe).
        """
        np.random.seed(seed)

        # Inicializa população com vetores de pesos válidos (somam 1)
        population = np.random.dirichlet(np.ones(self.n_assets), size=population_size)

        def fitness(weights):
            # Fitness é o índice de Sharpe
            port_return = np.dot(weights, self.returns)
            port_risk = np.sqrt(weights.T @ self.cov @ weights)
            return self.sharpe_ratio(port_return, port_risk)

        def tournament_selection(pop, fits):
            # Seleciona um indivíduo via torneio
            selected_idx = np.random.choice(len(pop), tournament_size, replace=False)
            best_idx = selected_idx[0]
            best_fit = fits[best_idx]
            for idx in selected_idx[1:]:
                if fits[idx] > best_fit:
                    best_fit = fits[idx]
                    best_idx = idx
            return pop[best_idx]

        def arithmetic_crossover(parent1, parent2):
            alpha = np.random.rand()
            child = alpha * parent1 + (1 - alpha) * parent2
            # Normalizar para soma 1
            child = np.clip(child, 0, None)
            s = np.sum(child)
            if s == 0:
                child = np.ones_like(child) / len(child)
            else:
                child /= s
            return child

        def mutate(weights):
            # Adiciona ruído gaussiano e normaliza
            mutated = weights + np.random.normal(0, mutation_std, size=self.n_assets)
            mutated = np.clip(mutated, 0, None)
            s = np.sum(mutated)
            if s == 0:
                mutated = np.ones_like(mutated) / len(mutated)
            else:
                mutated /= s
            return mutated

        best_solution = None
        best_fitness = -np.inf

        for gen in range(generations):
            fitnesses = np.array([fitness(ind) for ind in population])
            new_population = []

            # Armazenar melhor solução da geração
            gen_best_idx = np.argmax(fitnesses)
            gen_best_fit = fitnesses[gen_best_idx]
            if gen_best_fit > best_fitness:
                best_fitness = gen_best_fit
                best_solution = population[gen_best_idx].copy()

            while len(new_population) < population_size:
                # Seleção
                parent1 = tournament_selection(population, fitnesses)
                parent2 = tournament_selection(population, fitnesses)

                # Crossover
                if np.random.rand() < crossover_rate:
                    child = arithmetic_crossover(parent1, parent2)
                else:
                    child = parent1.copy()

                # Mutação
                if np.random.rand() < mutation_rate:
                    child = mutate(child)

                new_population.append(child)

            population = np.array(new_population)

        # Melhor resultado final
        best_return = np.dot(best_solution, self.returns)
        best_risk = np.sqrt(best_solution.T @ self.cov @ best_solution)
        best_sharpe = self.sharpe_ratio(best_return, best_risk)

        return {
            "weights": best_solution,
            "return": best_return,
            "risk": best_risk,
            "sharpe": best_sharpe
        }


def generate_synthetic_data():
    """
    Gera dados sintéticos realistas para 6 ativos brasileiros.

    Retornos e volatilidades anuais aproximados para:
    PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3

    Retornos estimados e matriz de covariância simulada.

    :return: tuple (returns, cov_matrix, asset_names)
    """
    asset_names = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'WEGE3']
    # Retornos anuais esperados (%)
    expected_returns = np.array([0.15, 0.18, 0.12, 0.11, 0.10, 0.14])

    # Volatilidades anuais (%)
    volatilities = np.array([0.30, 0.35, 0.25, 0.22, 0.20, 0.28])

    # Correlações aproximadas (simétricas e diagonais 1)
    corr_matrix = np.array([
        [1.00, 0.60, 0.55, 0.50, 0.45, 0.50],
        [0.60, 1.00, 0.50, 0.45, 0.40, 0.42],
        [0.55, 0.50, 1.00, 0.70, 0.65, 0.60],
        [0.50, 0.45, 0.70, 1.00, 0.55, 0.58],
        [0.45, 0.40, 0.65, 0.55, 1.00, 0.50],
        [0.50, 0.42, 0.60, 0.58, 0.50, 1.00]
    ])

    # Matriz de covariância = vol_i * vol_j * corr_ij
    cov_matrix = np.outer(volatilities, volatilities) * corr_matrix

    return expected_returns, cov_matrix, asset_names


def save_results(results, filename='atena_evolution/portfolio_optimization_results.json'):
    """
    Salva os resultados da otimização em JSON.

    :param results: dict com resultados da otimização.
    :param filename: caminho do arquivo para salvar.
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    # Converter numpy arrays para listas para JSON
    def convert(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError

    with open(filename, 'w') as f:
        json.dump(results, f, default=convert, indent=4)


def print_report(mc_results, ga_result, asset_names):
    """
    Imprime relatório detalhado comparando Monte Carlo e Algoritmo Genético.

    :param mc_results: dict com resultados Monte Carlo.
    :param ga_result: dict com resultado Algoritmo Genético.
    :param asset_names: nomes dos ativos.
    """
    # Monte Carlo melhor portfólio
    mc_best_idx = np.argmax(mc_results['sharpe'])
    mc_best_weights = mc_results['weights'][mc_best_idx]
    mc_best_return = mc_results['returns'][mc_best_idx]
    mc_best_risk = mc_results['risks'][mc_best_idx]
    mc_best_sharpe = mc_results['sharpe'][mc_best_idx]

    print("\n====== RELATÓRIO FINAL DE OTIMIZAÇÃO DE PORTFÓLIO ======\n")

    print("MÉTODO: SIMULAÇÃO DE MONTE CARLO")
    print(f"Índice de Sharpe Máximo: {mc_best_sharpe:.4f}")
    print(f"Retorno Esperado Anual: {mc_best_return:.4f}")
    print(f"Volatilidade Anual: {mc_best_risk:.4f}")
    print("Pesos dos ativos:")
    for name, weight in zip(asset_names, mc_best_weights):
        print(f"  {name}: {weight:.4f}")

    print("\nMÉTODO: ALGORITMO GENÉTICO")
    print(f"Índice de Sharpe Ótimo: {ga_result['sharpe']:.4f}")
    print(f"Retorno Esperado Anual: {ga_result['return']:.4f}")
    print(f"Volatilidade Anual: {ga_result['risk']:.4f}")
    print("Pesos dos ativos:")
    for name, weight in zip(asset_names, ga_result['weights']):
        print(f"  {name}: {weight:.4f}")

    print("\nCOMPARAÇÃO:")
    diff_sharpe = ga_result['sharpe'] - mc_best_sharpe
    print(f"Melhoria no Índice de Sharpe pelo AG em relação ao Monte Carlo: {diff_sharpe:.4f}")

    print("\n=========================================================\n")


def run_tests():
    """
    Testes inline para demonstrar funcionamento dos métodos.
    """
    print("Executando testes inline básicos...")

    # Gerar dados sintéticos
    returns, cov, assets = generate_synthetic_data()
    optimizer = PortfolioOptimizer(returns, cov, assets)

    # Teste Monte Carlo
    mc = optimizer.monte_carlo_simulation(n_portfolios=1000)
    assert len(mc['weights']) == 1000
    assert mc['returns'].shape == (1000,)
    assert mc['risks'].shape == (1000,)
    assert mc['sharpe'].shape == (1000,)

    # Teste Sharpe
    sample_return = 0.15
    sample_risk = 0.25
    sharpe = optimizer.sharpe_ratio(sample_return, sample_risk)
    assert isinstance(sharpe, float)

    # Teste fronteira eficiente
    frontier = optimizer.efficient_frontier(points=20)
    assert len(frontier['returns']) == 20
    assert len(frontier['risks']) == 20
    assert frontier['weights'].shape == (20, optimizer.n_assets)

    # Teste Algoritmo Genético (reduzido para teste rápido)
    ga_res = optimizer.genetic_algorithm_optimize(generations=10, population_size=50)
    assert 'weights' in ga_res and 'return' in ga_res and 'risk' in ga_res and 'sharpe' in ga_res
    assert abs(np.sum(ga_res['weights']) - 1) < 1e-6

    print("Todos os testes básicos foram concluídos com sucesso!\n")


def main():
    # Gerar dados sintéticos
    returns, cov, assets = generate_synthetic_data()

    # Inicializar otimizador
    optimizer = PortfolioOptimizer(returns, cov, assets)

    # Executar Monte Carlo
    mc_results = optimizer.monte_carlo_simulation(n_portfolios=5000)

    # Executar Algoritmo Genético
    ga_result = optimizer.genetic_algorithm_optimize(generations=50, population_size=100)

    # Calcular e plotar fronteira eficiente
    frontier = optimizer.efficient_frontier(points=100)

    # Imprimir relatório final
    print_report(mc_results, ga_result, assets)

    # Salvar resultados
    save_data = {
        "monte_carlo": {
            "weights": mc_results['weights'],
            "returns": mc_results['returns'],
            "risks": mc_results['risks'],
            "sharpe": mc_results['sharpe'],
            "asset_names": assets
        },
        "genetic_algorithm": {
            "weights": ga_result['weights'],
            "return": ga_result['return'],
            "risk": ga_result['risk'],
            "sharpe": ga_result['sharpe'],
            "asset_names": assets
        },
        "efficient_frontier": {
            "returns": frontier['returns'],
            "risks": frontier['risks'],
            "weights": frontier['weights'],
            "asset_names": assets
        }
    }
    save_results(save_data)


if __name__ == "__main__":
    run_tests()
    main()