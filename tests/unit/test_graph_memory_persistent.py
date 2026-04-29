"""Testa KnowledgeGraph com persistência SQLite."""
import tempfile, pytest
from modules.graph_memory import KnowledgeGraph

def _graph():
    tmp = tempfile.mktemp(suffix=".db")
    return KnowledgeGraph(db_path=tmp)

def test_add_and_get_node():
    g = _graph()
    nid = g.add_node("ATENA", "AI", {"version": "2"})
    assert nid == "ATENA"
    node = g.get_node("ATENA")
    assert node is not None
    assert node["type"] == "AI"

def test_persistence_across_instances():
    tmp = tempfile.mktemp(suffix=".db")
    g1 = KnowledgeGraph(db_path=tmp)
    g1.add_node("X", "concept", {"val": 42})
    del g1
    g2 = KnowledgeGraph(db_path=tmp)
    node = g2.get_node("X")
    assert node is not None
    assert node["properties"]["val"] == 42

def test_add_edge_dedup():
    g = _graph()
    g.add_node("A", "t"); g.add_node("B", "t")
    assert g.add_edge("A", "B", "uses")
    assert not g.add_edge("A", "B", "uses")  # duplicata

def test_contextual_query():
    g = _graph()
    g.add_node("A"); g.add_node("B"); g.add_node("C")
    g.add_edge("A", "B"); g.add_edge("B", "C")
    result = g.contextual_query("A", depth=2)
    ids = {n["id"] for n in result["nodes"]}
    assert "A" in ids and "B" in ids and "C" in ids

def test_remove_node():
    g = _graph()
    g.add_node("X"); g.add_node("Y")
    g.add_edge("X", "Y")
    g.remove_node("X")
    assert g.get_node("X") is None

def test_merge():
    g1 = _graph(); g2 = _graph()
    g1.add_node("A"); g2.add_node("B")
    g2.add_node("A")  # mesmo nó, não deve duplicar
    report = g1.merge(g2)
    assert report["added_nodes"] == 1  # só B é novo
