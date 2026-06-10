from pathlib import Path

import pytest
from tools import generate_knowledge_graph as generate_kg_module
from tools.generate_knowledge_graph import (
    build_import_result,
    load_kg_json,
    load_grounding_matches,
    prune_kg_with_grounding_file,
    validate_and_clean_kg,
)


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


def test_load_kg_json_validates_existing_graph_file(tmp_path: Path) -> None:
    kg_file = tmp_path / "kg.json"
    kg_file.write_text(
        """
        {
          "nodes": [
            {"id": "node_1", "name": "变量", "chapter": "第一章"},
            {"id": "node_2", "name": "指针", "chapter": "第二章"}
          ],
          "edges": [
            {"from": "node_1", "to": "node_2"}
          ]
        }
        """,
        encoding="utf-8",
    )

    nodes, edges = load_kg_json(kg_file)

    assert nodes == [
        {"id": "node_1", "name": "变量", "chapter": "第一章"},
        {"id": "node_2", "name": "指针", "chapter": "第二章"},
    ]
    assert edges == [{"from": "node_1", "to": "node_2"}]


def test_load_grounding_matches_reads_agent_json(tmp_path: Path) -> None:
    grounding_file = tmp_path / "grounding.json"
    grounding_file.write_text(
        """
        {
          "course_id": "course-1",
          "threshold": 0.7,
          "results": [
            {
              "node_id": "node_1",
              "body_top1_score": 0.82,
              "chunk_id": "chunk-1",
              "preview": "指针保存变量地址。"
            },
            {
              "node_id": "node_2",
              "body_top1_score": null,
              "chunk_id": null,
              "preview": ""
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    matches = load_grounding_matches(grounding_file)

    assert [(match.node_id, match.score, match.chunk_id, match.content_preview) for match in matches] == [
        ("node_1", 0.82, "chunk-1", "指针保存变量地址。"),
        ("node_2", 0.0, "", ""),
    ]


def test_prune_kg_with_grounding_file_keeps_supported_nodes_and_metrics(tmp_path: Path) -> None:
    nodes = [
        {"id": "node_1", "name": "变量", "chapter": "第一章"},
        {"id": "node_2", "name": "指针", "chapter": "第二章"},
        {"id": "node_3", "name": "数组", "chapter": "第三章"},
    ]
    edges = [
        {"from": "node_1", "to": "node_2"},
        {"from": "node_2", "to": "node_3"},
    ]
    grounding_file = tmp_path / "grounding.json"
    grounding_file.write_text(
        """
        {
          "course_id": "course-1",
          "threshold": 0.7,
          "results": [
            {
              "node_id": "node_1",
              "body_top1_score": 0.91,
              "chunk_id": "chunk-a",
              "preview": "变量用于保存程序运行中的数据。"
            },
            {
              "node_id": "node_2",
              "body_top1_score": 0.69,
              "chunk_id": "chunk-b",
              "preview": "指针保存地址。"
            },
            {
              "node_id": "node_3",
              "body_top1_score": 0.70,
              "chunk_id": "chunk-c",
              "preview": "数组是一组连续元素。"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    kept_nodes, kept_edges, metrics = prune_kg_with_grounding_file(
        nodes,
        edges,
        grounding_file,
        threshold=0.70,
    )

    assert kept_nodes == [nodes[0], nodes[2]]
    assert kept_edges == []
    assert metrics["body_top1_threshold"] == 0.70
    assert metrics["candidate_node_count"] == 3
    assert metrics["kept_node_count"] == 2
    assert metrics["pruned_node_count"] == 1
    assert metrics["body_support_pass_ratio"] == pytest.approx(2 / 3)
    assert metrics["grounding_source_file"] == str(grounding_file)
    assert metrics["pruned_nodes"] == [
        {
            "node_id": "node_2",
            "node_name": "指针",
            "chapter": "第二章",
            "body_top1_score": 0.69,
            "chunk_id": "chunk-b",
            "content_preview": "指针保存地址。",
        }
    ]


def test_main_disposes_engine_after_command(monkeypatch) -> None:
    calls = []

    async def fake_main_async():
        calls.append("main")

    class FakeEngine:
        async def dispose(self):
            calls.append("disposed")

    monkeypatch.setattr(generate_kg_module, "main_async", fake_main_async)
    monkeypatch.setattr(generate_kg_module, "engine", FakeEngine(), raising=False)

    generate_kg_module.main()

    assert calls == ["main", "disposed"]
