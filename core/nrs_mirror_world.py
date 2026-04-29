import time
import random
import json

class MirrorWorld:
    """
    Um ambiente de simulação minimalista onde as leis físicas (gravidade, entropia, luz)
    são variáveis que a Atena pode alterar via mutação neural.
    """
    def __init__(self):
        self.state = {
            "gravity": 9.81,
            "entropy": 0.01,
            "light_intensity": 1.0,
            "time_dilation": 1.0,
            "entities": 100,
            "stability": 1.0
        }
        self.history = []

    def update(self):
        # Simula a evolução natural do ambiente
        self.state["entropy"] += 0.001 * self.state["time_dilation"]
        self.state["stability"] -= 0.0005 * self.state["entropy"]
        
        # Garante limites físicos
        self.state["stability"] = max(0, min(1, self.state["stability"]))
        
        # Registra estado
        self.history.append(self.state.copy())
        if len(self.history) > 100:
            self.history.pop(0)

    def apply_spike(self, spike_data):
        """
        Aplica uma mutação neural da Atena ao ambiente.
        spike_data: dict com as alterações desejadas.
        """
        print(f"🔱 NRS [AMBIENTE]: Recebendo pico neural: {spike_data}")
        for key, value in spike_data.items():
            if key in self.state:
                old_val = self.state[key]
                self.state[key] = value
                print(f"  - Mutação em {key}: {old_val} -> {value}")
        
        # Re-estabiliza o ambiente após intervenção da AGI
        self.state["stability"] = min(1.0, self.state["stability"] + 0.1)

    def get_tensor_representation(self):
        """Retorna o estado como um tensor simplificado para a Atena."""
        return list(self.state.values())

if __name__ == "__main__":
    world = MirrorWorld()
    for _ in range(10):
        world.update()
        print(f"Estado: {world.state}")
        time.sleep(0.1)
