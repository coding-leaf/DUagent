from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from tools import generate_knowledge_graph as generate_kg_module
from app.services.kg_generation import (
    generate_kg_from_llm,
    load_kg_json_file,
    load_grounding_matches,
    prune_kg_with_grounding_file,
    route_a_generation_strategy_for_threshold,
    validate_kg_json_payload,
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
    nodes, edges = validate_kg_json_payload(raw_data)
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
    nodes, edges = validate_kg_json_payload(raw_data)
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
    nodes, edges = validate_kg_json_payload(raw_data)
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
    nodes, edges = validate_kg_json_payload(raw_data)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert edges[0]["to"] == "node_2"


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

    nodes, edges = load_kg_json_file(kg_file)

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


def test_build_arg_parser_defaults_grounding_threshold_to_usable_060() -> None:
    parser = generate_kg_module.build_arg_parser()

    args = parser.parse_args(
        [
            "--course-id",
            "course-1",
            "--kg-json",
            "/tmp/kg.json",
            "--grounding-file",
            "/tmp/grounding.json",
        ]
    )

    assert args.grounding_threshold == 0.60


def test_route_a_generation_strategy_uses_usable_name_only_for_default_threshold() -> None:
    assert route_a_generation_strategy_for_threshold(0.60) == "route_a_prune_usable_060"
    assert route_a_generation_strategy_for_threshold(0.6000000001) == "route_a_prune_usable_060"
    assert route_a_generation_strategy_for_threshold(0.70) == "route_a_prune_unsupported"


@pytest.mark.asyncio
async def test_generate_kg_from_llm_uses_backend_settings_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with patch("app.services.kg_generation.settings.LLM_API_KEY", "settings-key"), patch(
        "app.services.kg_generation.settings.LLM_BASE_URL", "https://settings.example"
    ), patch("app.services.kg_generation.settings.LLM_MODEL", "settings-model"), patch(
        "app.services.kg_generation.httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"nodes":[],"edges":[]}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = await generate_kg_from_llm("课程内容")

    assert result == {"nodes": [], "edges": []}
    called_url = mock_post.await_args.args[0]
    called_payload = mock_post.await_args.kwargs["json"]
    called_headers = mock_post.await_args.kwargs["headers"]
    assert called_url == "https://settings.example/chat/completions"
    assert called_payload["model"] == "settings-model"
    assert called_headers["Authorization"] == "Bearer settings-key"


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
    assert metrics["usable_support_ratio"] == pytest.approx(1.0)
    assert metrics["strong_support_ratio"] == pytest.approx(2 / 3)
    assert metrics["good_or_strong_support_ratio"] == pytest.approx(1.0)
    assert metrics["support_band_counts"] == {
        "strong": 2,
        "good": 1,
        "weak_but_usable": 0,
        "unsupported": 0,
    }
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


def test_prune_kg_with_grounding_file_defaults_to_usable_threshold(tmp_path: Path) -> None:
    nodes = [
        {"id": "node_1", "name": "变量", "chapter": "第一章"},
        {"id": "node_2", "name": "指针", "chapter": "第二章"},
        {"id": "node_3", "name": "数组", "chapter": "第三章"},
        {"id": "node_4", "name": "结构体", "chapter": "第四章"},
    ]
    edges = [
        {"from": "node_1", "to": "node_2"},
        {"from": "node_2", "to": "node_3"},
        {"from": "node_3", "to": "node_4"},
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
              "body_top1_score": 0.62,
              "chunk_id": "chunk-b",
              "preview": "指针保存地址。"
            },
            {
              "node_id": "node_3",
              "body_top1_score": 0.59,
              "chunk_id": "chunk-c",
              "preview": "数组候选分数不足。"
            },
            {
              "node_id": "node_4",
              "body_top1_score": null,
              "chunk_id": null,
              "preview": ""
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
    )

    assert kept_nodes == nodes[:2]
    assert kept_edges == [{"from": "node_1", "to": "node_2"}]
    assert metrics["body_top1_threshold"] == 0.60
    assert metrics["candidate_node_count"] == 4
    assert metrics["kept_node_count"] == 2
    assert metrics["pruned_node_count"] == 2
    assert metrics["body_support_pass_ratio"] == 0.5
    assert metrics["usable_support_ratio"] == 0.5
    assert metrics["strong_support_ratio"] == 0.25
    assert metrics["good_or_strong_support_ratio"] == 0.25
    assert metrics["support_band_counts"] == {
        "strong": 1,
        "good": 0,
        "weak_but_usable": 1,
        "unsupported": 2,
    }


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
