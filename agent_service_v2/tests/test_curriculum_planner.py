from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from agentscope.message import Msg, TextBlock
from agentscope.model import ChatResponse

from agent_service_v2.agents.curriculum_planner import (
    CourseCurriculumPlanner,
    build_curriculum_prompt,
    extract_planning_hint,
    graph_is_acyclic,
    normalize_knowledge_graph,
    run_curriculum_kg_generation,
)
from agent_service_v2.agents.model_provider import AgentModelSettings


def _text_response(text: str) -> ChatResponse:
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


async def _streamed_response(text: str):
    yield ChatResponse(content=[TextBlock(text=text[:10])], is_last=False)
    yield ChatResponse(content=[TextBlock(text=text)], is_last=True)


def _planned_graph() -> dict:
    return {
        "nodes": [
            {"id": "intro", "name": "课程导论", "chapter": "第一章 导论", "level": 1},
            {"id": "concept", "name": "核心概念", "chapter": "第一章 导论", "level": 2},
            {"id": "advanced", "name": "进阶应用", "chapter": "第二章 应用", "level": 3},
        ],
        "edges": [
            {"from": "intro", "to": "concept"},
            {"from": "concept", "to": "advanced"},
        ],
    }


# ---------------------------------------------------------------------------
# Prompt building (discipline agnostic, no hardcoded C Programming prompt)
# ---------------------------------------------------------------------------


def test_curriculum_prompt_injects_course_title_and_generic_design_rules() -> None:
    prompt = build_curriculum_prompt("第 1 章 数据结构绪论", course_title="数据结构与算法")

    assert "数据结构与算法" in prompt
    assert "第 1 章 数据结构绪论" in prompt
    assert '"level"' in prompt
    assert "directed acyclic graph" in prompt
    # 旧实现写死的 C 语言课程设计师提示词必须彻底消失
    assert "C Programming" not in prompt
    assert "C语言介绍" not in prompt


def test_curriculum_prompt_asks_model_to_infer_subject_without_course_title() -> None:
    prompt = build_curriculum_prompt("1. 计算机网络体系结构\n2. TCP/IP 协议族")

    assert "infer the subject" in prompt
    assert "计算机网络体系结构" in prompt
    assert "C Programming" not in prompt


def test_curriculum_prompt_truncates_oversized_context() -> None:
    from agent_service_v2.agents.curriculum_planner import MAX_CONTEXT_CHARS

    prompt = build_curriculum_prompt("甲" * (MAX_CONTEXT_CHARS + 5000), course_title="通识课")

    assert prompt.count("甲") == MAX_CONTEXT_CHARS


def test_curriculum_prompt_injects_pre_extracted_outline_hint() -> None:
    prompt = build_curriculum_prompt(
        "第一章 绪论",
        course_title="数据结构",
        outline_hint="- 第一章 绪论\n  * 基本概念",
    )

    assert "Pre-extracted outline" in prompt
    assert "- 第一章 绪论" in prompt


def test_extract_planning_hint_uses_builtin_outline_extractor() -> None:
    hint = extract_planning_hint("# 计算机网络\n\n## 第一章 体系结构\n\n### OSI 模型\n")

    assert "第一章 体系结构" in hint
    assert "OSI 模型" in hint


def test_extract_planning_hint_is_empty_for_plain_prose() -> None:
    assert extract_planning_hint("课程内容：变量、指针、数组。") == ""
    assert extract_planning_hint("") == ""


def test_curriculum_planner_feeds_outline_hint_into_the_prompt() -> None:
    import json

    mock_model = AsyncMock(return_value=_text_response(json.dumps(_planned_graph())))
    planner = CourseCurriculumPlanner(AgentModelSettings(), model=mock_model)

    asyncio.run(
        planner.plan_curriculum(
            "## 第一章 导论\n\n### 课程目标\n\n## 第二章 应用\n\n### 综合练习\n",
            course_title="软件工程",
        )
    )

    prompt_text = mock_model.await_args.args[0][0].content[0].text
    assert "Pre-extracted outline" in prompt_text
    assert "第二章 应用" in prompt_text


# ---------------------------------------------------------------------------
# Planner execution
# ---------------------------------------------------------------------------


def test_curriculum_planner_generates_graph_for_any_discipline() -> None:
    payload = {
        "nodes": [
            {"id": "osi_model", "name": "OSI 七层模型", "chapter": "第一章 体系结构", "level": 1},
            {"id": "tcp_congestion", "name": "TCP 拥塞控制", "chapter": "第三章 传输层", "level": 3},
        ],
        "edges": [{"from": "osi_model", "to": "tcp_congestion"}],
    }
    mock_model = AsyncMock(return_value=_text_response(__import__("json").dumps(payload)))

    with patch(
        "agent_service_v2.agents.curriculum_planner.build_chat_model_from_settings",
        return_value=mock_model,
    ) as mock_build_model:
        result = asyncio.run(
            CourseCurriculumPlanner(AgentModelSettings()).plan_curriculum(
                "第一章 体系结构\n第三章 传输层",
                course_title="计算机网络",
            )
        )

    assert mock_build_model.call_args.kwargs["stream"] is False
    assert [node["id"] for node in result["nodes"]] == ["osi_model", "tcp_congestion"]
    assert result["edges"] == [{"from": "osi_model", "to": "tcp_congestion"}]
    mock_model.assert_awaited_once()

    messages = mock_model.await_args.args[0]
    assert isinstance(messages, list)
    assert isinstance(messages[0], Msg)
    assert messages[0].role == "user"
    prompt_text = messages[0].content[0].text
    assert "计算机网络" in prompt_text
    assert "第一章 体系结构" in prompt_text


def test_curriculum_planner_handles_streaming_model_output() -> None:
    import json

    mock_model = AsyncMock(return_value=_streamed_response(json.dumps(_planned_graph())))

    planner = CourseCurriculumPlanner(AgentModelSettings(), model=mock_model)
    result = asyncio.run(
        planner.plan_curriculum("第一章 导论\n第二章 应用", course_title="数据结构")
    )

    assert len(result["nodes"]) == 3
    assert graph_is_acyclic(result["nodes"], result["edges"])


def test_curriculum_planner_strips_markdown_json_fences() -> None:
    import json

    fenced = "```json\n" + json.dumps(_planned_graph()) + "\n```"
    planner = CourseCurriculumPlanner(
        AgentModelSettings(),
        model=AsyncMock(return_value=_text_response(fenced)),
    )

    result = asyncio.run(planner.plan_curriculum("第一章 导论", course_title="数学分析"))

    assert result["nodes"][0]["id"] == "intro"


def test_curriculum_planner_requires_context_and_model() -> None:
    planner = CourseCurriculumPlanner(AgentModelSettings(), model=AsyncMock())

    with pytest.raises(ValueError, match="context must not be empty"):
        asyncio.run(planner.plan_curriculum("   "))

    with patch(
        "agent_service_v2.agents.curriculum_planner.build_chat_model_from_settings",
        return_value=None,
    ):
        unconfigured = CourseCurriculumPlanner(AgentModelSettings())
    with pytest.raises(RuntimeError, match="LLM Model not configured"):
        asyncio.run(unconfigured.plan_curriculum("第一章 导论"))


def test_curriculum_planner_rejects_non_json_output() -> None:
    planner = CourseCurriculumPlanner(
        AgentModelSettings(),
        model=AsyncMock(return_value=_text_response("抱歉，我无法完成该任务。")),
    )

    with pytest.raises(ValueError, match="JSON object"):
        asyncio.run(planner.plan_curriculum("第一章 导论"))


def test_curriculum_planner_extracts_json_object_embedded_in_prose() -> None:
    import json

    noisy = "Here is the graph:\n" + json.dumps(_planned_graph()) + "\nHope it helps."
    planner = CourseCurriculumPlanner(
        AgentModelSettings(),
        model=AsyncMock(return_value=_text_response(noisy)),
    )

    result = asyncio.run(planner.plan_curriculum("第一章 导论"))

    assert [node["id"] for node in result["nodes"]] == ["intro", "concept", "advanced"]


# ---------------------------------------------------------------------------
# DAG self-check / normalization
# ---------------------------------------------------------------------------


def test_normalize_breaks_dependency_cycles() -> None:
    payload = {
        "nodes": [
            {"id": "a", "name": "A", "chapter": "第一章", "level": 1},
            {"id": "b", "name": "B", "chapter": "第一章", "level": 2},
            {"id": "c", "name": "C", "chapter": "第二章", "level": 3},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "a"},
        ],
    }

    graph = normalize_knowledge_graph(payload)

    assert graph_is_acyclic(graph["nodes"], graph["edges"])
    assert len(graph["edges"]) == 2
    assert {"from": "c", "to": "a"} not in graph["edges"]


def test_normalize_drops_dangling_self_and_duplicate_edges() -> None:
    payload = {
        "nodes": [
            {"id": "a", "name": "A", "chapter": "第一章"},
            {"id": "b", "name": "B", "chapter": "第一章"},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "a", "to": "b"},
            {"from": "a", "to": "a"},
            {"from": "a", "to": "ghost"},
            {"from": "", "to": "b"},
            "not-an-edge",
        ],
    }

    graph = normalize_knowledge_graph(payload)

    assert graph["edges"] == [{"from": "a", "to": "b"}]


def test_normalize_fills_missing_chapter_level_and_sanitizes_ids() -> None:
    payload = {
        "nodes": [
            {"id": "Data Structures/Intro!", "name": "绪论", "level": "9"},
            {"id": "Data Structures/Intro!", "name": "重复节点"},
            {"id": "", "name": "数组", "chapter": "第二章 数组", "level": "bad"},
        ],
        "edges": [],
    }

    graph = normalize_knowledge_graph(payload)

    assert [node["id"] for node in graph["nodes"]] == ["data_structures_intro", "node_3"]
    assert graph["nodes"][0]["chapter"] == "课程总览"
    assert graph["nodes"][0]["level"] == 5
    assert graph["nodes"][1]["chapter"] == "第二章 数组"
    assert graph["nodes"][1]["level"] == 1


def test_normalize_keeps_edges_that_reference_unsanitized_node_ids() -> None:
    # 大模型常把节点 id 写成 "1.1" / "Ch-1"，归一化后这些 id 会变成 "1_1" / "ch_1"；
    # 引用原始 id 的边必须被重新映射，而不是因为“找不到节点”被整批丢弃。
    payload = {
        "nodes": [
            {"id": "1.1", "name": "绪论", "chapter": "第一章"},
            {"id": "Ch-2", "name": "线性表", "chapter": "第二章"},
        ],
        "edges": [{"from": "1.1", "to": "Ch-2"}],
    }

    graph = normalize_knowledge_graph(payload)

    assert [node["id"] for node in graph["nodes"]] == ["1_1", "ch_2"]
    assert graph["edges"] == [{"from": "1_1", "to": "ch_2"}]
    assert graph_is_acyclic(graph["nodes"], graph["edges"])


def test_normalize_rejects_payloads_without_usable_nodes() -> None:
    with pytest.raises(ValueError, match="non-empty 'nodes'"):
        normalize_knowledge_graph({"nodes": [], "edges": []})

    with pytest.raises(ValueError, match="non-empty 'nodes'"):
        normalize_knowledge_graph({"edges": []})

    with pytest.raises(ValueError, match="no usable nodes"):
        normalize_knowledge_graph({"nodes": [{"id": "a"}], "edges": []})

    with pytest.raises(ValueError, match="must be a JSON object"):
        normalize_knowledge_graph(["not", "a", "dict"])


def test_graph_is_acyclic_detects_self_and_mutual_cycles() -> None:
    nodes = [{"id": "a"}, {"id": "b"}]

    assert graph_is_acyclic(nodes, [{"from": "a", "to": "b"}])
    assert not graph_is_acyclic(nodes, [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])
    assert not graph_is_acyclic(nodes, [{"from": "a", "to": "a"}])


# ---------------------------------------------------------------------------
# Entry point used by the knowledge API
# ---------------------------------------------------------------------------


def test_run_curriculum_kg_generation_forwards_course_title() -> None:
    mock_model = AsyncMock(return_value=_text_response(__import__("json").dumps(_planned_graph())))

    with patch(
        "agent_service_v2.agents.curriculum_planner.build_chat_model_from_settings",
        return_value=mock_model,
    ):
        result = asyncio.run(
            run_curriculum_kg_generation(
                AgentModelSettings(),
                "第一章 导论",
                course_title="Python 程序设计",
            )
        )

    assert result["nodes"][0]["name"] == "课程导论"
    prompt_text = mock_model.await_args.args[0][0].content[0].text
    assert "Python 程序设计" in prompt_text


def test_leader_team_course_planner_is_backward_compatible_alias() -> None:
    import json

    from agent_service_v2.agents.leader_team import (
        CoursePlannerAgent,
        run_leader_team_kg_generation,
    )

    assert issubclass(CoursePlannerAgent, CourseCurriculumPlanner)

    def _fresh_streaming_model():
        return AsyncMock(
            side_effect=lambda *args, **kwargs: _streamed_response(json.dumps(_planned_graph()))
        )

    with patch(
        "agent_service_v2.agents.leader_team.build_chat_model_from_settings",
        return_value=_fresh_streaming_model(),
    ):
        result = asyncio.run(CoursePlannerAgent(AgentModelSettings()).plan_curriculum("第一章 导论"))

    assert len(result["nodes"]) == 3

    with patch(
        "agent_service_v2.agents.curriculum_planner.build_chat_model_from_settings",
        return_value=_fresh_streaming_model(),
    ):
        legacy = asyncio.run(
            run_leader_team_kg_generation(AgentModelSettings(), "第一章 导论")
        )

    assert len(legacy["nodes"]) == 3
