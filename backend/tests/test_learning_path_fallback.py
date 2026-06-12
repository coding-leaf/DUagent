"""Unit tests for _topo_sort_kg_nodes in learning_path.py fallback path.

Run: python -m pytest tests/test_learning_path_fallback.py -v
"""
import pytest
from app.api.v1.learning_path import _topo_sort_kg_nodes


class TestTopoSortKgNodes:
    def test_sorts_simple_dag(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids == ["a", "b", "c"]

    def test_multiple_roots(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "c"},
            {"from": "b", "to": "c"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids[0] in ("a", "b")
        assert ids[1] in ("a", "b")
        assert ids[2] == "c"

    def test_no_edges_falls_back_to_original_order(self):
        nodes = [
            {"id": "z", "name": "Z", "chapter": "Ch3"},
            {"id": "a", "name": "A", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [])
        ids = [n["id"] for n in result]
        assert ids == ["z", "a"]

    def test_empty_nodes(self):
        assert _topo_sort_kg_nodes([], []) == []

    def test_preserves_all_node_fields(self):
        nodes = [
            {"id": "n1", "name": "Node1", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [{"from": "n1", "to": "n2"}])
        assert result[0]["id"] == "n1"
        assert result[0]["name"] == "Node1"
        assert result[0]["chapter"] == "Ch1"

    def test_disjoint_subgraphs(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
            {"id": "d", "name": "D", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "c", "to": "d"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")
