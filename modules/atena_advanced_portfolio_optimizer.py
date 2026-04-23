#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Ω - Portfolio Optimizer (fallback local)."""

import json
from pathlib import Path
import numpy as np


class PortfolioOptimizer:
    """Otimizador de portfólio com Monte Carlo + AG simplificado."""

    def __init__(self):
        self.assets = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3"]
        self.returns = np.array([0.18, 0.16, 0.14, 0.13, 0.10, 0.12], dtype=float)
        self.volatility = np.array([0.32, 0.28, 0.22, 0.24, 0.18, 0.20], dtype=float)
        base_corr = np.full((6, 6), 0.35)
        np.fill_diagonal(base_corr, 1.0)
        self.cov = np.outer(self.volatility, self.volatility) * base_corr
        self.rng = np.random.default_rng(42)

    def sharpe_ratio(self, returns, risk, risk_free=0.02):
        if risk <= 0:
            return -1e9
        return (returns - risk_free) / risk

    def monte_carlo_simulation(self, n_portfolios=2500):
        best = {"sharpe": -1e9}
        for _ in range(n_portfolios):
            w = self.rng.random(len(self.assets))
            w = w / w.sum()
            ret = float(np.dot(w, self.returns))
            risk = float(np.sqrt(w @ self.cov @ w))
            sharpe = float(self.sharpe_ratio(ret, risk))
            if sharpe > best["sharpe"]:
                best = {"weights": w, "return": ret, "risk": risk, "sharpe": sharpe}
        return best

    def genetic_algorithm_optimize(self, generations=40, pop_size=60, mutation_rate=0.15):
        def normalize(weights):
            weights = np.clip(weights, 1e-9, None)
            return weights / weights.sum()

        population = [normalize(self.rng.random(len(self.assets))) for _ in range(pop_size)]
        best = {"sharpe": -1e9}

        for _ in range(generations):
            scored = []
            for individual in population:
                ret = float(np.dot(individual, self.returns))
                risk = float(np.sqrt(individual @ self.cov @ individual))
                sharpe = float(self.sharpe_ratio(ret, risk))
                scored.append((sharpe, individual))
                if sharpe > best["sharpe"]:
                    best = {"weights": individual.copy(), "return": ret, "risk": risk, "sharpe": sharpe}

            scored.sort(key=lambda x: x[0], reverse=True)
            elites = [ind for _, ind in scored[: max(2, pop_size // 5)]]
            next_population = elites.copy()

            while len(next_population) < pop_size:
                p1, p2 = self.rng.choice(elites, size=2, replace=True)
                alpha = float(self.rng.uniform(0.2, 0.8))
                child = normalize(alpha * p1 + (1 - alpha) * p2)
                if self.rng.random() < mutation_rate:
                    child = normalize(child + self.rng.normal(0, 0.05, size=len(self.assets)))
                next_population.append(child)

            population = next_population

        return best

    def efficient_frontier(self):
        target_returns = np.linspace(0.10, 0.19, 12)
        frontier = []
        for target in target_returns:
            best_risk = None
            for _ in range(2000):
                w = self.rng.random(len(self.assets))
                w = w / w.sum()
                ret = float(np.dot(w, self.returns))
                if abs(ret - target) <= 0.004:
                    risk = float(np.sqrt(w @ self.cov @ w))
                    if best_risk is None or risk < best_risk:
                        best_risk = risk
            if best_risk is not None:
                frontier.append({"target_return": float(target), "risk": float(best_risk)})
        return frontier


def main():
    optimizer = PortfolioOptimizer()
    mc = optimizer.monte_carlo_simulation()
    ga = optimizer.genetic_algorithm_optimize()
    frontier = optimizer.efficient_frontier()

    best = ga if ga["sharpe"] >= mc["sharpe"] else mc
    weights_dict = {asset: round(float(weight), 4) for asset, weight in zip(optimizer.assets, best["weights"])}

    report = {
        "method": "genetic_algorithm" if best is ga else "monte_carlo",
        "best_portfolio": weights_dict,
        "expected_return": round(float(best["return"]), 6),
        "expected_risk": round(float(best["risk"]), 6),
        "sharpe": round(float(best["sharpe"]), 6),
        "comparison": {
            "monte_carlo_sharpe": round(float(mc["sharpe"]), 6),
            "genetic_algorithm_sharpe": round(float(ga["sharpe"]), 6)
        },
        "efficient_frontier_points": frontier
    }

    out = Path("atena_evolution/portfolio_optimization_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("=== RELATÓRIO FINAL ATENA Ω ===")
    print("Portfólio ótimo:", report["best_portfolio"])
    print("Retorno esperado anual:", report["expected_return"])
    print("Volatilidade anual:", report["expected_risk"])
    print("Índice de Sharpe:", report["sharpe"])
    print("Comparação MC vs AG:", report["comparison"])
    print("Resultados salvos em:", out)


if __name__ == "__main__":
    main()
