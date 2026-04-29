#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω — Knowledge Graph com Persistência Real
Versão anterior perdia tudo entre sessões (só RAM).
Agora persiste em SQLite e recarrega automaticamente.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("atena.graph_memory")

ROOT    = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atena_evolution" / "knowledge" / "graph_memory.db"


class KnowledgeGraph:
    """
    Grafo de conhecimento persistente (SQLite + cache RAM).

    Operações:
    - add_node / add_edge : escrevem no DB imediatamente
    - get_node / get_edges: lêem do cache RAM (sincronizado ao carregar)
    - find_paths          : DFS sobre grafo em RAM
    - contextual_query    : BFS de profundidade configurável
    - merge               : une dois grafos sem duplicar nós/arestas
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Cache RAM
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, list[dict[str, Any]]] = {}
        self._node_id_counter = 0
        self._init_db()
        self._load_from_db()

    # ── Esquema ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    node_id    TEXT PRIMARY KEY,
                    node_type  TEXT NOT NULL DEFAULT 'concept',
                    properties TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id  TEXT NOT NULL,
                    target_id  TEXT NOT NULL,
                    edge_type  TEXT NOT NULL DEFAULT 'relates_to',
                    properties TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    UNIQUE(source_id, target_id, edge_type)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON kg_edges(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON kg_edges(target_id)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ── Carga inicial ─────────────────────────────────────────────────────────

    def _load_from_db(self) -> None:
        with self._conn() as conn:
            for row in conn.execute("SELECT node_id, node_type, properties FROM kg_nodes"):
                nid, ntype, props_raw = row
                try:
                    props = json.loads(props_raw)
                except (json.JSONDecodeError, TypeError):
                    props = {}
                self.nodes[nid] = {"id": nid, "type": ntype, "properties": props}
                self.edges.setdefault(nid, [])

            for row in conn.execute(
                "SELECT source_id, target_id, edge_type, properties FROM kg_edges"
            ):
                src, tgt, etype, props_raw = row
                try:
                    props = json.loads(props_raw)
                except (json.JSONDecodeError, TypeError):
                    props = {}
                self.edges.setdefault(src, []).append(
                    {"source": src, "target": tgt, "type": etype, "properties": props}
                )

        logger.info(
            "KnowledgeGraph carregado: %d nós, %d arestas",
            len(self.nodes),
            sum(len(v) for v in self.edges.values()),
        )

    # ── Nós ──────────────────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: Optional[str] = None,
        node_type: str = "concept",
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        props = properties or {}
        ts = time.time()
        with self._lock:
            if node_id is None:
                node_id = f"{node_type}_{self._node_id_counter}"
                self._node_id_counter += 1

            props_json = json.dumps(props, ensure_ascii=False)
            with self._conn() as conn:
                conn.execute("""
                    INSERT INTO kg_nodes (node_id, node_type, properties, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        properties = excluded.properties,
                        updated_at = excluded.updated_at
                """, (node_id, node_type, props_json, ts, ts))

            if node_id in self.nodes:
                self.nodes[node_id]["properties"].update(props)
            else:
                self.nodes[node_id] = {"id": node_id, "type": node_type, "properties": props}
                self.edges.setdefault(node_id, [])

        logger.debug("nó: %s (%s)", node_id, node_type)
        return node_id

    def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self.nodes:
                return False
            with self._conn() as conn:
                conn.execute("DELETE FROM kg_nodes WHERE node_id = ?", (node_id,))
                conn.execute(
                    "DELETE FROM kg_edges WHERE source_id = ? OR target_id = ?",
                    (node_id, node_id),
                )
            del self.nodes[node_id]
            del self.edges[node_id]
            # Remove das listas de adjacência de outros nós
            for src in self.edges:
                self.edges[src] = [
                    e for e in self.edges[src] if e["target"] != node_id
                ]
        return True

    # ── Arestas ───────────────────────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "relates_to",
        properties: Optional[dict[str, Any]] = None,
    ) -> bool:
        props = properties or {}
        with self._lock:
            if source_id not in self.nodes:
                logger.warning("add_edge: nó origem '%s' não existe", source_id)
                return False
            if target_id not in self.nodes:
                logger.warning("add_edge: nó destino '%s' não existe", target_id)
                return False

            # Dedup em RAM
            existing = self.edges.get(source_id, [])
            for e in existing:
                if e["target"] == target_id and e["type"] == edge_type:
                    return False  # já existe

            props_json = json.dumps(props, ensure_ascii=False)
            ts = time.time()
            try:
                with self._conn() as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO kg_edges
                            (source_id, target_id, edge_type, properties, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (source_id, target_id, edge_type, props_json, ts))
            except sqlite3.IntegrityError:
                return False

            edge = {"source": source_id, "target": target_id, "type": edge_type, "properties": props}
            self.edges.setdefault(source_id, []).append(edge)

        logger.debug("aresta: %s -[%s]-> %s", source_id, edge_type, target_id)
        return True

    def get_edges_from_node(self, node_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.edges.get(node_id, []))

    # ── Buscas ────────────────────────────────────────────────────────────────

    def find_paths(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 4,
    ) -> list[list[str]]:
        """DFS para encontrar todos os caminhos entre dois nós."""
        paths: list[list[str]] = []
        with self._lock:
            stack = [(start_node_id, [start_node_id])]
            while stack:
                current, path = stack.pop()
                if current == end_node_id:
                    paths.append(path)
                    continue
                if len(path) >= max_depth:
                    continue
                for edge in self.edges.get(current, []):
                    nxt = edge["target"]
                    if nxt not in path:
                        stack.append((nxt, path + [nxt]))
        return paths

    def contextual_query(self, query_concept: str, depth: int = 2) -> dict[str, Any]:
        """BFS ao redor de um conceito até a profundidade dada."""
        relevant_nodes: set[str] = set()
        relevant_edges: list[dict] = []

        with self._lock:
            if query_concept not in self.nodes:
                return {"nodes": [], "edges": [], "concept": query_concept, "found": False}

            relevant_nodes.add(query_concept)
            queue = [(query_concept, 0)]
            visited = {query_concept}

            while queue:
                current, d = queue.pop(0)
                if d >= depth:
                    continue
                for edge in self.edges.get(current, []):
                    tgt = edge["target"]
                    relevant_edges.append(edge)
                    if tgt not in visited:
                        visited.add(tgt)
                        relevant_nodes.add(tgt)
                        queue.append((tgt, d + 1))

            nodes_data = [self.nodes[nid] for nid in relevant_nodes if nid in self.nodes]

        return {
            "concept": query_concept,
            "found": True,
            "nodes": nodes_data,
            "edges": relevant_edges,
        }

    # ── Merge ─────────────────────────────────────────────────────────────────

    def merge(self, other: "KnowledgeGraph") -> dict[str, int]:
        """Incorpora nós e arestas de outro grafo sem duplicar."""
        added_nodes = added_edges = 0
        with other._lock:
            other_nodes = dict(other.nodes)
            other_edges = {k: list(v) for k, v in other.edges.items()}

        for nid, data in other_nodes.items():
            if nid not in self.nodes:
                self.add_node(nid, data.get("type", "concept"), data.get("properties"))
                added_nodes += 1

        for src, edges in other_edges.items():
            for e in edges:
                added = self.add_edge(src, e["target"], e.get("type", "relates_to"), e.get("properties"))
                if added:
                    added_edges += 1

        return {"added_nodes": added_nodes, "added_edges": added_edges}

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        with self._lock:
            n = len(self.nodes)
            e = sum(len(v) for v in self.edges.values())
            types: dict[str, int] = {}
            for node in self.nodes.values():
                t = node.get("type", "unknown")
                types[t] = types.get(t, 0) + 1
        return {"nodes": n, "edges": e, "node_types": types, "db": str(self._db_path)}
