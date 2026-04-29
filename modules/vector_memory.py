import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("atena.memory.vector")

# Tentativa de importação do FAISS (fallback para busca linear se não disponível)
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

class VectorMemory:
    """
    Memória Episódica de Longo Prazo usando Vector Embeddings.
    Permite que a ATENA recupere experiências passadas similares ao contexto atual.
    """
    def __init__(self, dimension: int = 384, storage_path: str = "atena_evolution/knowledge/vector_memory"):
        self.dimension = dimension
        self.storage_path = storage_path
        self.index_path = os.path.join(storage_path, "memory.index")
        self.meta_path = os.path.join(storage_path, "metadata.json")
        self.metadata = []
        
        os.makedirs(storage_path, exist_ok=True)
        
        if HAS_FAISS:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                if os.path.exists(self.meta_path):
                    with open(self.meta_path, 'r') as f:
                        self.metadata = json.load(f)
            else:
                self.index = faiss.IndexFlatL2(dimension)
        else:
            self.index = [] # Lista para busca linear como fallback
            if os.path.exists(self.meta_path):
                with open(self.meta_path, 'r') as f:
                    self.metadata = json.load(f)

    def add_experience(self, embedding: np.ndarray, meta: Dict[str, Any]):
        """Adiciona uma nova experiência à memória vetorial."""
        if embedding.shape[0] != self.dimension:
            logger.error(f"Dimensão do embedding incorreta: {embedding.shape[0]} != {self.dimension}")
            return

        vector = embedding.reshape(1, -1).astype('float32')
        
        if HAS_FAISS:
            self.index.add(vector)
        else:
            self.index.append(vector[0])
            
        self.metadata.append(meta)
        self._save()

    def search_similar(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Busca experiências similares na memória."""
        if not self.metadata:
            return []

        query_vector = query_embedding.reshape(1, -1).astype('float32')
        
        if HAS_FAISS:
            distances, indices = self.index.search(query_vector, min(top_k, len(self.metadata)))
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx != -1:
                    results.append((self.metadata[idx], float(dist)))
            return results
        else:
            # Busca linear (fallback)
            similarities = []
            for i, vec in enumerate(self.index):
                dist = np.linalg.norm(query_vector - vec)
                similarities.append((self.metadata[i], float(dist)))
            similarities.sort(key=lambda x: x[1])
            return similarities[:top_k]

    def _save(self):
        """Persiste a memória em disco."""
        if HAS_FAISS:
            faiss.write_index(self.index, self.index_path)
        
        with open(self.meta_path, 'w') as f:
            json.dump(self.metadata, f)

# Instância global (dimensão 384 para all-MiniLM-L6-v2)
vector_memory = VectorMemory(dimension=384)
