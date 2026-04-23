import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, List[Dict[str, Any]]] = {}
        self._node_id_counter = 0

    def add_node(self, node_id: Optional[str] = None, node_type: str = "concept", properties: Optional[Dict[str, Any]] = None) -> str:
        if node_id is None:
            node_id = f"{node_type}_{self._node_id_counter}"
            self._node_id_counter += 1
        
        if node_id in self.nodes:
            logger.warning(f"Nó com ID {node_id} já existe. Atualizando propriedades.")
            self.nodes[node_id].update(properties or {})
        else:
            self.nodes[node_id] = {"id": node_id, "type": node_type, "properties": properties or {}}
            self.edges[node_id] = []
        logger.info(f"Nó adicionado/atualizado: {node_id} ({node_type})")
        return node_id

    def add_edge(self, source_id: str, target_id: str, edge_type: str = "relates_to", properties: Optional[Dict[str, Any]] = None):
        if source_id not in self.nodes:
            raise ValueError(f"Nó de origem {source_id} não encontrado.")
        if target_id not in self.nodes:
            raise ValueError(f"Nó de destino {target_id} não encontrado.")
        
        edge = {"source": source_id, "target": target_id, "type": edge_type, "properties": properties or {}}
        self.edges[source_id].append(edge)
        logger.info(f"Aresta adicionada: {source_id} -[{edge_type}]-> {target_id}")

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def get_edges_from_node(self, node_id: str) -> List[Dict[str, Any]]:
        return self.edges.get(node_id, [])

    def find_paths(self, start_node_id: str, end_node_id: str, max_depth: int = 3) -> List[List[str]]:
        """Encontra caminhos entre dois nós usando busca em profundidade (DFS)."""
        paths = []
        stack = [(start_node_id, [start_node_id])]

        while stack:
            current_node, path = stack.pop()
            if current_node == end_node_id:
                paths.append(path)
            if len(path) < max_depth:
                for edge in self.get_edges_from_node(current_node):
                    next_node = edge["target"]
                    if next_node not in path:
                        stack.append((next_node, path + [next_node]))
        return paths

    def contextual_query(self, query_concept: str, depth: int = 2) -> Dict[str, Any]:
        """Retorna nós e arestas relevantes a um conceito, dentro de uma profundidade."""
        relevant_nodes = set()
        relevant_edges = []
        
        # Adiciona o nó inicial se existir
        if query_concept in self.nodes:
            relevant_nodes.add(query_concept)

        # BFS para encontrar nós e arestas relacionadas
        q = [(query_concept, 0)]
        visited_nodes = {query_concept}

        while q:
            current_node_id, current_depth = q.pop(0)
            if current_depth >= depth: continue

            for edge in self.get_edges_from_node(current_node_id):
                target_node_id = edge["target"]
                relevant_edges.append(edge)
                if target_node_id not in visited_nodes:
                    visited_nodes.add(target_node_id)
                    relevant_nodes.add(target_node_id)
                    q.append((target_node_id, current_depth + 1))
        
        return {
            "nodes": [self.nodes[nid] for nid in relevant_nodes if nid in self.nodes],
            "edges": relevant_edges
        }

# Exemplo de uso (para testes)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    kg = KnowledgeGraph()

    # Adicionar nós
    atena_id = kg.add_node(node_id="ATENA", node_type="AI_Agent", properties={
        "version": "4.2", "status": "evolving", "goal": "AGI"})
    llm_id = kg.add_node(node_id="DeepSeek-R1-7B", node_type="LLM", properties={
        "developer": "DeepSeek-AI", "params": "7B", "capability": "reasoning, code_gen"})
    ethics_id = kg.add_node(node_id="EthicsEngine", node_type="Module", properties={
        "purpose": "value_alignment", "status": "active"})
    network_monitor_id = kg.add_node(node_id="NetworkMonitor", node_type="Script", properties={
        "language": "Python", "function": "anomaly_detection"})
    scapy_id = kg.add_node(node_id="Scapy", node_type="Library", properties={
        "language": "Python", "purpose": "packet_manipulation"})

    # Adicionar arestas (relações)
    kg.add_edge(atena_id, llm_id, "uses")
    kg.add_edge(atena_id, ethics_id, "integrates")
    kg.add_edge(llm_id, network_monitor_id, "generates")
    kg.add_edge(network_monitor_id, scapy_id, "depends_on")
    kg.add_edge(ethics_id, atena_id, "governs")

    print("\n--- Consulta Contextual (ATENA, profundidade 1) ---")
    context = kg.contextual_query("ATENA", depth=1)
    for node in context["nodes"]:
        print(f"Nó: {node['id']} ({node['type']}) - {node['properties']}")
    for edge in context["edges"]:
        print(f"Aresta: {edge['source']} -[{edge['type']}]-> {edge['target']}")

    print("\n--- Caminho entre ATENA e Scapy ---")
    paths = kg.find_paths("ATENA", "Scapy")
    for path in paths:
        print(f"Caminho: {' -> '.join(path)}")
