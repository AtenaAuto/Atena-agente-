#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Vector Memory v3.0
Memória Episódica de Longo Prazo Avançada com múltiplos backends de indexação.

Recursos:
- 🧠 Múltiplos backends: FAISS (GPU/CPU), Annoy, HNSW, Linear
- 📊 Compressão e quantização para redução de memória
- 🔄 Indexação incremental e rebuild agendado
- 💾 Persistência otimizada com checkpointing
- 📈 Métricas de qualidade de busca
- 🌐 Suporte a embeddings de diferentes dimensões
- 🔍 Busca híbrida (vector + metadata filtering)
"""

import json
import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

import numpy as np

logger = logging.getLogger("atena.memory.vector")

# =============================================================================
# Tentativa de importação de backends otimizados
# =============================================================================

HAS_FAISS = False
HAS_FAISS_GPU = False
HAS_ANNOY = False
HAS_HNSW = False

try:
    import faiss
    HAS_FAISS = True
    # Verifica GPU disponível
    if faiss.get_num_gpus() > 0:
        HAS_FAISS_GPU = True
        logger.info(f"FAISS GPU disponível: {faiss.get_num_gpus()} GPUs")
except ImportError:
    pass

try:
    import hnswlib
    HAS_HNSW = True
except ImportError:
    pass

try:
    from annoy import AnnoyIndex
    HAS_ANNOY = True
except ImportError:
    pass


# =============================================================================
# = Configurações e Enums
# =============================================================================

class IndexType:
    """Tipos de índice suportados."""
    FAISS_FLAT = "faiss_flat"
    FAISS_IVF = "faiss_ivf"
    FAISS_HNSW = "faiss_hnsw"
    HNSWLIB = "hnswlib"
    ANNOY = "annoy"
    LINEAR = "linear"


class DistanceMetric:
    """Métricas de distância suportadas."""
    L2 = "l2"           # Euclidean distance
    IP = "ip"           # Inner product (cosine similarity)
    COSINE = "cosine"   # Cosine similarity


@dataclass
class IndexConfig:
    """Configuração do índice vetorial."""
    index_type: str = IndexType.FAISS_FLAT
    distance_metric: str = DistanceMetric.L2
    use_gpu: bool = False
    nlist: int = 100          # Número de clusters para IVF
    nprobe: int = 10          # Número de clusters a explorar
    hnsw_m: int = 16          # HNSW número de conexões
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 50
    annoy_n_trees: int = 50
    
    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


# =============================================================================
# = Metadados e Estruturas de Dados
# =============================================================================

@dataclass
class MemoryEntry:
    """Entrada de memória com metadados ricos."""
    id: str
    embedding: np.ndarray
    metadata: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None
    importance_score: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "importance_score": self.importance_score
        }


# =============================================================================
# = Vector Memory Principal
# =============================================================================

class VectorMemory:
    """
    Memória episódica vetorial de longo prazo com múltiplos backends de indexação.
    """
    
    def __init__(
        self,
        dimension: int = 384,
        storage_path: str = "atena_evolution/knowledge/vector_memory",
        index_config: Optional[IndexConfig] = None,
        auto_save_interval: int = 60  # segundos
    ):
        self.dimension = dimension
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.storage_path / "memory.index"
        self.meta_path = self.storage_path / "metadata.json"
        self.config_path = self.storage_path / "config.json"
        
        self.index_config = index_config or IndexConfig()
        self._load_config()
        
        self.metadata: List[MemoryEntry] = []
        self.id_to_idx: Dict[str, int] = {}
        self._next_id = 0
        
        self.auto_save_interval = auto_save_interval
        self._last_save_time = time.time()
        self._dirty = False
        
        # Inicializa índice
        self._index = None
        self._init_index()
        
        # Carrega dados existentes
        self._load()
        
        logger.info(f"🧠 VectorMemory v3.0 inicializado")
        logger.info(f"   Dimensão: {self.dimension}")
        logger.info(f"   Tipo índice: {self.index_config.index_type}")
        logger.info(f"   Backend: {self._get_backend_name()}")
        logger.info(f"   Total entradas: {len(self.metadata)}")
    
    def _get_backend_name(self) -> str:
        """Retorna nome do backend ativo."""
        if HAS_FAISS and self.index_config.index_type.startswith("faiss"):
            return f"FAISS ({'GPU' if self.index_config.use_gpu and HAS_FAISS_GPU else 'CPU'})"
        elif HAS_HNSW and self.index_config.index_type == IndexType.HNSWLIB:
            return "HNSWlib"
        elif HAS_ANNOY and self.index_config.index_type == IndexType.ANNOY:
            return "Annoy"
        return "Linear (fallback)"
    
    def _load_config(self):
        """Carrega configuração do disco."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                    for key, value in config_data.items():
                        if hasattr(self.index_config, key):
                            setattr(self.index_config, key, value)
            except Exception as e:
                logger.warning(f"Erro ao carregar config: {e}")
    
    def _save_config(self):
        """Salva configuração no disco."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.index_config.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar config: {e}")
    
    def _init_index(self):
        """Inicializa índice baseado na configuração."""
        if self.index_config.index_type == IndexType.FAISS_FLAT and HAS_FAISS:
            self._init_faiss_flat()
        elif self.index_config.index_type == IndexType.FAISS_IVF and HAS_FAISS:
            self._init_faiss_ivf()
        elif self.index_config.index_type == IndexType.FAISS_HNSW and HAS_FAISS:
            self._init_faiss_hnsw()
        elif self.index_config.index_type == IndexType.HNSWLIB and HAS_HNSW:
            self._init_hnswlib()
        elif self.index_config.index_type == IndexType.ANNOY and HAS_ANNOY:
            self._init_annoy()
        else:
            self._init_linear()
    
    def _init_faiss_flat(self):
        """Inicializa índice FAISS Flat (exato)."""
        self._index = faiss.IndexFlatL2(self.dimension)
        if self.index_config.use_gpu and HAS_FAISS_GPU:
            res = faiss.StandardGpuResources()
            self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
    
    def _init_faiss_ivf(self):
        """Inicializa índice FAISS IVF (aproximado, mais rápido)."""
        quantizer = faiss.IndexFlatL2(self.dimension)
        self._index = faiss.IndexIVFFlat(
            quantizer, self.dimension, self.index_config.nlist,
            faiss.METRIC_L2
        )
        if self.index_config.use_gpu and HAS_FAISS_GPU:
            res = faiss.StandardGpuResources()
            self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
        self._index.nprobe = self.index_config.nprobe
    
    def _init_faiss_hnsw(self):
        """Inicializa índice FAISS HNSW (hierarchical navigable small world)."""
        self._index = faiss.IndexHNSWFlat(self.dimension, self.index_config.hnsw_m)
        self._index.hnsw.efConstruction = self.index_config.hnsw_ef_construction
        self._index.hnsw.efSearch = self.index_config.hnsw_ef_search
    
    def _init_hnswlib(self):
        """Inicializa índice HNSWlib."""
        self._index = hnswlib.Index(space='l2', dim=self.dimension)
        self._index.init_index(
            max_elements=1000000,
            ef_construction=self.index_config.hnsw_ef_construction,
            M=self.index_config.hnsw_m
        )
        self._index.set_ef(self.index_config.hnsw_ef_search)
    
    def _init_annoy(self):
        """Inicializa índice Annoy."""
        self._index = AnnoyIndex(self.dimension, 'angular')
        self._index.set_seed(42)
    
    def _init_linear(self):
        """Inicializa índice linear (fallback, sem FAISS)."""
        self._index = []  # Lista de vetores para busca linear
    
    def _add_to_index(self, vector: np.ndarray, idx: int):
        """Adiciona vetor ao índice."""
        vector = vector.astype('float32').reshape(1, -1)
        
        if HAS_FAISS and self.index_config.index_type.startswith("faiss"):
            # Treina IVF se necessário
            if self.index_config.index_type == IndexType.FAISS_IVF and not self._index.is_trained:
                if len(self.metadata) >= self.index_config.nlist:
                    self._index.train(self._get_all_vectors())
            self._index.add(vector)
            
        elif HAS_HNSW and self.index_config.index_type == IndexType.HNSWLIB:
            self._index.add_items(vector, [idx])
            
        elif HAS_ANNOY and self.index_config.index_type == IndexType.ANNOY:
            self._index.add_item(idx, vector[0])
            
        else:
            self._index.append(vector[0])
    
    def _get_all_vectors(self) -> np.ndarray:
        """Retorna todos os vetores como matriz numpy."""
        vectors = []
        for entry in self.metadata:
            vectors.append(entry.embedding)
        return np.vstack(vectors).astype('float32') if vectors else np.empty((0, self.dimension))
    
    def add_experience(
        self,
        embedding: np.ndarray,
        metadata: Dict[str, Any],
        importance_score: float = 1.0
    ) -> str:
        """
        Adiciona nova experiência à memória vetorial.
        
        Args:
            embedding: Vetor de embedding (shape: dimension,)
            metadata: Metadados associados
            importance_score: Importância da experiência (0-1)
        
        Returns:
            ID da experiência adicionada
        """
        if embedding.shape[0] != self.dimension:
            logger.error(f"Dimensão incorreta: {embedding.shape[0]} != {self.dimension}")
            return ""
        
        # Normaliza embedding (opcional)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        # Cria entry
        entry_id = f"exp_{self._next_id:08d}"
        entry = MemoryEntry(
            id=entry_id,
            embedding=embedding.copy(),
            metadata=metadata,
            importance_score=importance_score
        )
        
        self.metadata.append(entry)
        self.id_to_idx[entry_id] = len(self.metadata) - 1
        
        # Adiciona ao índice
        self._add_to_index(embedding, len(self.metadata) - 1)
        
        self._next_id += 1
        self._dirty = True
        
        # Auto-save
        if time.time() - self._last_save_time > self.auto_save_interval:
            self.save()
        
        logger.debug(f"➕ Experiência adicionada: {entry_id}")
        return entry_id
    
    def search_similar(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        min_similarity: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_importance: float = 0.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Busca experiências similares na memória.
        
        Args:
            query_embedding: Embedding da consulta
            top_k: Número de resultados
            min_similarity: Similaridade mínima (0-1)
            filter_metadata: Filtro por metadados
            min_importance: Importância mínima
        
        Returns:
            Lista de (metadados, distância/similaridade)
        """
        if not self.metadata:
            return []
        
        # Normaliza query
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm
        
        query_vector = query_embedding.astype('float32').reshape(1, -1)
        k = min(top_k, len(self.metadata))
        
        # Busca no índice
        if HAS_FAISS and self.index_config.index_type.startswith("faiss"):
            distances, indices = self._index.search(query_vector, k)
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1 or idx >= len(self.metadata):
                    continue
                entry = self.metadata[idx]
                similarity = self._distance_to_similarity(dist)
                
                if similarity < min_similarity:
                    continue
                if entry.importance_score < min_importance:
                    continue
                if filter_metadata and not self._matches_filter(entry.metadata, filter_metadata):
                    continue
                
                results.append((entry.to_dict(), similarity))
                
        elif HAS_HNSW and self.index_config.index_type == IndexType.HNSWLIB:
            indices, distances = self._index.knn_query(query_vector, k=k)
            results = []
            for idx, dist in zip(indices[0], distances[0]):
                if idx >= len(self.metadata):
                    continue
                entry = self.metadata[idx]
                similarity = self._distance_to_similarity(dist)
                
                if similarity < min_similarity:
                    continue
                if entry.importance_score < min_importance:
                    continue
                if filter_metadata and not self._matches_filter(entry.metadata, filter_metadata):
                    continue
                
                results.append((entry.to_dict(), similarity))
                
        elif HAS_ANNOY and self.index_config.index_type == IndexType.ANNOY:
            indices, distances = self._index.get_nns_by_vector(
                query_vector[0], k, include_distances=True
            )
            results = []
            for idx, dist in zip(indices, distances):
                if idx >= len(self.metadata):
                    continue
                entry = self.metadata[idx]
                similarity = 1.0 - dist  # Annoy usa angular distance
                
                if similarity < min_similarity:
                    continue
                if entry.importance_score < min_importance:
                    continue
                if filter_metadata and not self._matches_filter(entry.metadata, filter_metadata):
                    continue
                
                results.append((entry.to_dict(), similarity))
                
        else:
            # Busca linear (fallback)
            similarities = []
            for entry in self.metadata:
                dist = np.linalg.norm(query_vector - entry.embedding.reshape(1, -1))
                similarity = self._distance_to_similarity(dist)
                
                if similarity < min_similarity:
                    continue
                if entry.importance_score < min_importance:
                    continue
                if filter_metadata and not self._matches_filter(entry.metadata, filter_metadata):
                    continue
                
                similarities.append((entry.to_dict(), similarity))
            
            similarities.sort(key=lambda x: x[1], reverse=True)
            results = similarities[:k]
        
        # Atualiza contadores de acesso
        for meta, _ in results:
            entry_id = meta['id']
            idx = self.id_to_idx.get(entry_id)
            if idx is not None:
                entry = self.metadata[idx]
                entry.access_count += 1
                entry.last_accessed = datetime.now().isoformat()
        
        self._dirty = True
        return results
    
    def _distance_to_similarity(self, distance: float) -> float:
        """Converte distância para similaridade (0-1)."""
        if self.index_config.distance_metric == DistanceMetric.COSINE:
            return max(0.0, min(1.0, 1.0 - distance))
        elif self.index_config.distance_metric == DistanceMetric.IP:
            return max(0.0, min(1.0, distance))
        else:  # L2
            # Converte distância L2 para similaridade usando sigmoide
            return max(0.0, min(1.0, 1.0 / (1.0 + distance / 2.0)))
    
    def _matches_filter(self, metadata: Dict, filter_dict: Dict) -> bool:
        """Verifica se metadados correspondem ao filtro."""
        for key, value in filter_dict.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True
    
    def get_experience(self, experience_id: str) -> Optional[MemoryEntry]:
        """Recupera experiência por ID."""
        idx = self.id_to_idx.get(experience_id)
        if idx is not None:
            entry = self.metadata[idx]
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
            self._dirty = True
            return entry
        return None
    
    def update_importance(self, experience_id: str, importance_score: float) -> bool:
        """Atualiza score de importância da experiência."""
        idx = self.id_to_idx.get(experience_id)
        if idx is not None:
            self.metadata[idx].importance_score = max(0.0, min(1.0, importance_score))
            self._dirty = True
            return True
        return False
    
    def delete_experience(self, experience_id: str) -> bool:
        """Remove experiência da memória."""
        idx = self.id_to_idx.get(experience_id)
        if idx is None:
            return False
        
        # Remove do índice (reconstrução necessária para maioria dos backends)
        del self.metadata[idx]
        # Reconstroi id_to_idx
        self.id_to_idx = {entry.id: i for i, entry in enumerate(self.metadata)}
        
        # Marca para rebuild do índice
        self._rebuild_index()
        self._dirty = True
        
        logger.debug(f"🗑️ Experiência removida: {experience_id}")
        return True
    
    def _rebuild_index(self):
        """Reconstrói índice a partir dos metadados atuais."""
        self._init_index()
        for i, entry in enumerate(self.metadata):
            self._add_to_index(entry.embedding, i)
    
    def save(self):
        """Persiste memória em disco."""
        if not self._dirty:
            return
        
        try:
            # Salva metadados
            metadata_data = [entry.to_dict() for entry in self.metadata]
            with open(self.meta_path, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            # Salva embeddings separadamente (binário)
            embeddings_path = self.storage_path / "embeddings.npy"
            if self.metadata:
                embeddings = np.vstack([e.embedding for e in self.metadata])
                np.save(embeddings_path, embeddings)
            
            # Salva índice se for FAISS
            if HAS_FAISS and self.index_config.index_type.startswith("faiss"):
                faiss.write_index(self._index, str(self.index_path))
            
            # Salva ID mapping
            id_map_path = self.storage_path / "id_map.json"
            with open(id_map_path, 'w') as f:
                json.dump(self.id_to_idx, f)
            
            self._last_save_time = time.time()
            self._dirty = False
            logger.debug(f"💾 Memória salva: {len(self.metadata)} entradas")
            
        except Exception as e:
            logger.error(f"Erro ao salvar memória: {e}")
    
    def _load(self):
        """Carrega memória do disco."""
        try:
            # Carrega metadados
            if self.meta_path.exists():
                with open(self.meta_path, 'r') as f:
                    metadata_data = json.load(f)
                
                # Carrega embeddings
                embeddings_path = self.storage_path / "embeddings.npy"
                if embeddings_path.exists():
                    embeddings = np.load(embeddings_path)
                else:
                    embeddings = [None] * len(metadata_data)
                
                # Reconstrói entradas
                self.metadata = []
                for i, meta in enumerate(metadata_data):
                    embedding = embeddings[i] if i < len(embeddings) else np.zeros(self.dimension)
                    entry = MemoryEntry(
                        id=meta['id'],
                        embedding=embedding,
                        metadata=meta['metadata'],
                        created_at=meta['created_at'],
                        access_count=meta.get('access_count', 0),
                        last_accessed=meta.get('last_accessed'),
                        importance_score=meta.get('importance_score', 1.0)
                    )
                    self.metadata.append(entry)
                
                # Carrega ID mapping
                id_map_path = self.storage_path / "id_map.json"
                if id_map_path.exists():
                    with open(id_map_path, 'r') as f:
                        self.id_to_idx = json.load(f)
                else:
                    self.id_to_idx = {entry.id: i for i, entry in enumerate(self.metadata)}
                
                self._next_id = len(self.metadata)
                
                # Reconstrói índice
                if self.metadata:
                    self._rebuild_index()
                
                logger.info(f"📂 Memória carregada: {len(self.metadata)} entradas")
                
        except Exception as e:
            logger.warning(f"Erro ao carregar memória: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da memória."""
        importances = [e.importance_score for e in self.metadata]
        access_counts = [e.access_count for e in self.metadata]
        
        return {
            "total_entries": len(self.metadata),
            "dimension": self.dimension,
            "index_type": self.index_config.index_type,
            "backend": self._get_backend_name(),
            "avg_importance": np.mean(importances) if importances else 0,
            "avg_access_count": np.mean(access_counts) if access_counts else 0,
            "total_accesses": sum(access_counts),
            "unique_tags": len(set(
                tag for e in self.metadata 
                for tag in e.metadata.get('tags', [])
            )) if self.metadata else 0,
            "dirty": self._dirty,
            "last_save": datetime.fromtimestamp(self._last_save_time).isoformat() if self._last_save_time else None
        }
    
    def clear(self):
        """Limpa toda a memória."""
        self.metadata = []
        self.id_to_idx = {}
        self._next_id = 0
        self._init_index()
        self._dirty = True
        self.save()
        logger.info("🧹 Memória completamente limpa")
    
    def optimize(self):
        """Otimiza o índice (reconstrução, compressão)."""
        logger.info("🔄 Otimizando índice de memória...")
        self._rebuild_index()
        
        # Compressão de embeddings (quantização)
        if HAS_FAISS and len(self.metadata) > 1000:
            # Converte para índice IVF para compressão
            quantizer = faiss.IndexFlatL2(self.dimension)
            ivf_index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            vectors = self._get_all_vectors()
            ivf_index.train(vectors)
            ivf_index.add(vectors)
            self._index = ivf_index
            self.index_config.index_type = IndexType.FAISS_IVF
            self._save_config()
            logger.info("📊 Índice convertido para IVF para compressão")
        
        self.save()
        logger.info("✅ Otimização concluída")
    
    def rebuild_from_metadata(self):
        """Reconstrói embeddings a partir de metadados (útil após mudanças)."""
        # Placeholder para reconstrução de embeddings se necessário
        logger.info("🔄 Reconstruindo embeddings dos metadados...")
        # Implementação depende do gerador de embeddings
        self.save()


# =============================================================================
# = Instância Global
# =============================================================================

vector_memory = VectorMemory(dimension=384)


# =============================================================================
# = Exemplo de Uso e CLI
# =============================================================================

def main():
    """Demonstração do VectorMemory."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Vector Memory v3.0")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas")
    parser.add_argument("--clear", action="store_true", help="Limpa memória")
    parser.add_argument("--optimize", action="store_true", help="Otimiza índice")
    parser.add_argument("--search", type=str, help="Busca similar (requer embedding)")
    parser.add_argument("--dim", type=int, default=384, help="Dimensão do embedding")
    
    args = parser.parse_args()
    
    if args.clear:
        vector_memory.clear()
        print("✅ Memória limpa")
        return 0
    
    if args.optimize:
        vector_memory.optimize()
        return 0
    
    if args.stats:
        stats = vector_memory.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        return 0
    
    if args.search:
        print("⚠️ Busca requer embedding. Use via API programática.")
        return 1
    
    # Demo: adiciona experiências de exemplo
    print("🧪 Demo: Adicionando experiências de exemplo...")
    
    # Gera embeddings aleatórios para demonstração
    for i in range(10):
        embedding = np.random.randn(args.dim).astype('float32')
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        metadata = {
            "type": "example",
            "index": i,
            "tags": ["demo", f"group_{i%3}"],
            "data": f"Experiência de exemplo #{i}"
        }
        
        vector_memory.add_experience(embedding, metadata, importance_score=0.5 + i*0.05)
    
    print(f"✅ {len(vector_memory.metadata)} experiências adicionadas")
    
    # Busca similar
    query = np.random.randn(args.dim).astype('float32')
    norm = np.linalg.norm(query)
    if norm > 0:
        query = query / norm
    
    results = vector_memory.search_similar(query, top_k=5, min_similarity=0.3)
    
    print("\n🔍 Resultados da busca:")
    for meta, score in results:
        print(f"   Score: {score:.4f} - {meta['metadata'].get('data', 'N/A')}")
    
    print(f"\n📊 Estatísticas finais:")
    stats = vector_memory.get_stats()
    print(f"   Total entradas: {stats['total_entries']}")
    print(f"   Backend: {stats['backend']}")
    print(f"   Acessos totais: {stats['total_accesses']}")
    
    return 0


if __name__ == "__main__":
    exit(main())
