import pytest
from tools.generate_knowledge_graph import build_import_result, validate_and_clean_kg


def test_validate_and_clean_kg_success():
    """测试常规合规的知识图谱数据校验。"""
    raw_data = {
        "nodes": [
            {"id": "node_1", "name": "知识点一", "chapter": "第一章"},
            {"id": "node_2", "name": "知识点二", "chapter": "第一章"},
        ],
        "edges": [
            {"from": "node_1", "to": "node_2"}
        ]
    }
    nodes, edges = validate_and_clean_kg(raw_data)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert nodes[0]["id"] == "node_1"
    assert edges[0]["from"] == "node_1"


def test_validate_and_clean_kg_missing_fields():
    """测试缺失关键字段的节点会被剔除。"""
    raw_data = {
        "nodes": [
            {"id": "node_1", "name": "有名字", "chapter": "第一章"},
            {"id": "node_2", "name": "", "chapter": "第一章"},  # 缺失 name
            {"id": "", "name": "有名字", "chapter": "第一章"},  # 缺失 id
        ],
        "edges": []
    }
    nodes, edges = validate_and_clean_kg(raw_data)
    assert len(nodes) == 1
    assert nodes[0]["id"] == "node_1"


def test_validate_and_clean_kg_duplicates():
    """测试重复节点和重复边去重。"""
    raw_data = {
        "nodes": [
            {"id": "node_1", "name": "节点一", "chapter": "第一章"},
            {"id": "node_1", "name": "节点一重复", "chapter": "第一章"},  # 重复 ID
            {"id": "node_2", "name": "节点二", "chapter": "第一章"},
        ],
        "edges": [
            {"from": "node_1", "to": "node_2"},
            {"from": "node_1", "to": "node_2"},  # 重复边
        ]
    }
    nodes, edges = validate_and_clean_kg(raw_data)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert nodes[0]["id"] == "node_1"
    assert nodes[1]["id"] == "node_2"


def test_validate_and_clean_kg_dangling_edges():
    """测试悬空边（引用不存在的节点）会被剔除。"""
    raw_data = {
        "nodes": [
            {"id": "node_1", "name": "节点一", "chapter": "第一章"},
            {"id": "node_2", "name": "节点二", "chapter": "第一章"},
        ],
        "edges": [
            {"from": "node_1", "to": "node_2"},
            {"from": "node_1", "to": "node_3"},  # 悬空边，node_3 不存在
        ]
    }
    nodes, edges = validate_and_clean_kg(raw_data)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert edges[0]["to"] == "node_2"


def test_build_import_result_uses_version_metadata():
    """测试导入结果返回版本化 KG 元数据。"""

    class Graph:
        id = "graph-1"
        course_id = "course-1"
        version = 3
        nodes = [{"id": "node_1"}, {"id": "node_2"}]
        edges = [{"from": "node_1", "to": "node_2"}]
        source_type = "outline_llm"
        generation_strategy = "legacy_outline"
        metrics = {"node_count": 2, "edge_count": 1}
        is_active = True

    result = build_import_result(Graph())

    assert result == {
        "course_id": "course-1",
        "graph_id": "graph-1",
        "version": 3,
        "node_count": 2,
        "edge_count": 1,
        "source_type": "outline_llm",
        "generation_strategy": "legacy_outline",
        "metrics": {"node_count": 2, "edge_count": 1},
        "activated": True,
    }
