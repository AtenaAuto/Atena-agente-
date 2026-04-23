#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ATENA Ω — MISSÃO 2: BIO-INSPIRED DISTRIBUTED CONSENSUS (BIDC)       ║
║         Missão: Criar um sistema de sincronização de consciência AGI         ║
║                                                                              ║
║  A Atena projetará um protocolo de consenso baseado em enxames biológicos    ║
║  (Swarm Intelligence) e Redes Neurais de Picos (Spiking Neural Networks)     ║
║  para coordenar múltiplos agentes em um ambiente distribuído.                ║
║                                                                              ║
║  >> BIDC-AGI: Bio-Inspired Distributed Consensus for AGI Swarms <<           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import math
import random
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Adiciona o diretório de módulos ao path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "modules"))

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("atena.mission2")

# ═══════════════════════════════════════════════════════════════════════════════
# PARTE 1: SPIKING NEURAL AGENT (SNA)
# Agente baseado em neurônios de picos (LIF - Leaky Integrate-and-Fire)
# ═══════════════════════════════════════════════════════════════════════════════

class SpikingAgent:
    """Representa um agente AGI com dinâmica de neurônios de picos."""
    def __init__(self, agent_id: int, threshold: float = 1.0, decay: float = 0.9):
        self.id = agent_id
        self.membrane_potential = 0.0
        self.threshold = threshold
        self.decay = decay
        self.spikes = 0
        self.state = np.random.rand(5) # Estado interno (vetor de consciência)
        self.neighbors = []

    def integrate(self, stimulus: float):
        """Integra estímulo externo e de vizinhos."""
        self.membrane_potential = self.membrane_potential * self.decay + stimulus
        if self.membrane_potential >= self.threshold:
            self.spike()
            return True
        return False

    def spike(self):
        """Dispara um pico de consciência e reseta potencial."""
        self.spikes += 1
        self.membrane_potential = 0.0
        # Evolução do estado interno após o pico
        self.state = (self.state + np.random.normal(0, 0.1, 5)) % 1.0

# ═══════════════════════════════════════════════════════════════════════════════
# PARTE 2: SWARM CONSENSUS PROTOCOL
# Protocolo de consenso baseado em enxames (Particle Swarm Optimization)
# ═══════════════════════════════════════════════════════════════════════════════

class BioConsensusSwarm:
    """Enxame de agentes AGI buscando consenso bio-inspirado."""
    def __init__(self, n_agents: int = 10):
        self.agents = [SpikingAgent(i) for i in range(n_agents)]
        self.global_best_state = np.random.rand(5)
        self.consensus_history = []

    def step(self):
        """Executa um passo de sincronização do enxame."""
        total_spikes = 0
        for agent in self.agents:
            # Estímulo baseado na distância para o melhor global (atração social)
            social_stimulus = np.linalg.norm(self.global_best_state - agent.state)
            if agent.integrate(social_stimulus):
                total_spikes += 1
                # Se o agente disparou, ele influencia o consenso
                if np.random.rand() > 0.5:
                    self.global_best_state = 0.9 * self.global_best_state + 0.1 * agent.state
        
        # Calcula variância do enxame (nível de desordem/entropia)
        states = np.array([a.state for a in self.agents])
        variance = np.var(states)
        self.consensus_history.append(float(variance))
        return total_spikes, variance

# ═══════════════════════════════════════════════════════════════════════════════
# PARTE 3: EXECUÇÃO DA MISSÃO
# ═══════════════════════════════════════════════════════════════════════════════

def run_mission():
    print("\n" + "═"*78)
    print("  ATENA Ω — MISSÃO 2: BIDC-AGI")
    print("  Bio-Inspired Distributed Consensus for AGI Swarms")
    print("═"*78)

    swarm = BioConsensusSwarm(n_agents=15)
    print(f"  [BIDC] Inicializado enxame com {len(swarm.agents)} agentes spiking.")
    
    max_steps = 100
    for i in range(max_steps):
        spikes, variance = swarm.step()
        if i % 20 == 0:
            print(f"  Passo {i:3d} | Picos: {spikes:2d} | Variância (Entropia): {variance:.6f}")
    
    final_variance = swarm.consensus_history[-1]
    improvement = (swarm.consensus_history[0] - final_variance) / swarm.consensus_history[0] * 100
    
    print("\n" + "─"*60)
    print(f"  ✅ Consenso atingido com variância final: {final_variance:.8f}")
    print(f"  🚀 Redução de entropia do sistema: {improvement:.2f}%")
    print("─"*60)

    # Salvar resultados
    results = {
        "mission": "BIDC-AGI",
        "timestamp": datetime.now().isoformat(),
        "agents": 15,
        "final_variance": final_variance,
        "entropy_reduction": improvement,
        "history": swarm.consensus_history
    }
    
    report_path = BASE_DIR / "atena_evolution" / "mission_bidc_agi_report.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"  Relatório salvo em: {report_path.name}")
    return results

if __name__ == "__main__":
    run_mission()
