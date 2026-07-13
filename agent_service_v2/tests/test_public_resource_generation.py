from __future__ import annotations

import asyncio
import importlib
import importlib.util
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agentscope.message import TextBlock
from agentscope.model import ChatResponse
from fastapi.testclient import TestClient

from agent_service_v2.main import app


MODULE_NAME = "agent_service_v2.generators.public_resources"
client = TestClient(app)


def _load_module():
    try:
        spec = importlib.util.find_spec(MODULE_NAME)
    except ModuleNotFoundError:
        spec = None
    assert spec is not None, "public resources need a dedicated typed generator"
    return importlib.import_module(MODULE_NAME)


def test_public_resource_types_are_truthful_and_bounded():
    module = _load_module()

    assert module.PUBLIC_RESOURCE_TYPES == {"lesson", "diagram", "example"}
    with pytest.raises(ValueError, match="unsupported_public_resource_type"):
        module.build_public_resource_prompt("reading", "第一章", "变量", "")


@pytest.mark.parametrize(
    ("resource_type", "payload", "expected_format"),
    [
        (
            "lesson",
            {"title": "变量讲义", "content": "# 变量\n\n变量用于保存数据。"},
            "markdown",
        ),
        (
            "diagram",
            {
                "title": "变量关系图",
                "content": "flowchart TD\n  A[声明] --> B[使用]",
                "diagram_kind": "flowchart",
            },
            "mermaid",
        ),
        (
            "example",
            {
                "title": "变量示例",
                "content": "# 示例\n\n```c\nint value = 1;\n```",
            },
            "markdown",
        ),
    ],
)
def test_normalize_public_asset_uses_one_webhook_shape(
    resource_type,
    payload,
    expected_format,
):
    module = _load_module()

    asset = module.normalize_public_asset(
        resource_type,
        payload,
        chapter="第一章",
        knowledge_point="变量",
        sources=[{"chunk_id": "chunk-1"}],
    )

    assert asset["type"] == resource_type
    assert asset["format"] == expected_format
    assert asset["chapter"] == "第一章"
    assert asset["knowledge_point"] == "变量"
    assert asset["sources"] == [{"chunk_id": "chunk-1"}]


@pytest.mark.anyio
async def test_generator_reuses_one_course_rag_and_model_call_for_selected_types():
    module = _load_module()
    response = ChatResponse(
        content=[
            TextBlock(
                text="""{
                  "resources": [
                    {"type":"lesson","title":"变量讲义","content":"# 变量\\n\\n基于课程原文。"},
                    {"type":"diagram","title":"变量图解","content":"flowchart TD\\nA[声明] --> B[使用]","diagram_kind":"flowchart"},
                    {"type":"example","title":"变量示例","content":"# 示例\\n\\n```c\\nint value = 1;\\n```"}
                  ]
                }"""
            )
        ],
        is_last=True,
    )
    model = AsyncMock(return_value=response)
    generator = module.PublicResourceGenerator(model=model)
    retrieve = AsyncMock(
        return_value={
            "context_text": "教材中的变量定义",
            "sources": [{"chunk_id": "chunk-1"}],
        }
    )

    with patch(
        f"{MODULE_NAME}.retrieve_course_context",
        new=retrieve,
    ):
        assets = await generator.generate_many(
            ["lesson", "diagram", "example"],
            chapter="第一章",
            knowledge_point="变量",
            course_id="catalog-1",
            course_title="C语言",
        )

    assert [asset["type"] for asset in assets] == ["lesson", "diagram", "example"]
    assert all(asset["sources"] == [{"chunk_id": "chunk-1"}] for asset in assets)
    retrieve.assert_awaited_once()
    model.assert_awaited_once()
    messages = model.await_args.args[0]
    assert len(messages) == 1
    assert "教材中的变量定义" in messages[0].content[0].text
    assert "C语言" in messages[0].content[0].text
    assert "每种类型恰好返回一项" in messages[0].content[0].text


@pytest.mark.anyio
async def test_generator_retries_invalid_structure_once_without_repeating_rag():
    module = _load_module()
    invalid_response = ChatResponse(
        content=[TextBlock(text='{"resources": []}')],
        is_last=True,
    )
    valid_response = ChatResponse(
        content=[
            TextBlock(
                text='{"resources":[{"type":"lesson","title":"变量讲义","content":"# 变量"}]}'
            )
        ],
        is_last=True,
    )
    model = AsyncMock(side_effect=[invalid_response, valid_response])
    retrieve = AsyncMock(return_value={"context_text": "变量定义", "sources": []})
    generator = module.PublicResourceGenerator(model=model)

    with patch(f"{MODULE_NAME}.retrieve_course_context", new=retrieve):
        assets = await generator.generate_many(
            ["lesson"],
            chapter="第一章",
            knowledge_point="变量",
            course_id="catalog-1",
        )

    assert [asset["type"] for asset in assets] == ["lesson"]
    retrieve.assert_awaited_once()
    assert model.await_count == 2
    retry_messages = model.await_args_list[1].args[0]
    assert "上一次输出未通过结构校验" in retry_messages[0].content[0].text


@pytest.mark.anyio
async def test_public_resource_flow_limits_node_generation_concurrency_and_uses_short_error_code():
    from agent_service_v2.generators import public_resource_flow as flow

    active = 0
    max_active = 0
    first_two_started = asyncio.Event()
    release = asyncio.Event()

    async def generate_many(*_args, **_kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        if active == 2:
            first_two_started.set()
        await release.wait()
        active -= 1
        return [{"type": "lesson"}]

    fake_generator = MagicMock()
    fake_generator.generate_many = AsyncMock(side_effect=generate_many)
    settings = SimpleNamespace(WEBHOOK_SECRET="")

    with (
        patch.object(flow, "build_chat_model_from_settings", return_value=MagicMock()),
        patch.object(flow, "PublicResourceGenerator", return_value=fake_generator),
        patch.object(flow, "_post_webhook", new=AsyncMock()),
    ):
        tasks = [
            asyncio.create_task(
                flow.run_public_resource_generation(
                    settings=settings,
                    task_id=f"task-{index}",
                    course_id="catalog-1",
                    chapter="第一章",
                    knowledge_point=f"知识点-{index}",
                    resource_types=["lesson"],
                    webhook_url="http://backend.test/webhook",
                )
            )
            for index in range(3)
        ]
        await asyncio.wait_for(first_two_started.wait(), timeout=1)
        await asyncio.sleep(0)
        assert max_active == 2
        assert fake_generator.generate_many.await_count == 2
        release.set()
        await asyncio.gather(*tasks)

        fake_generator.generate_many.side_effect = RuntimeError("model failed")
        result = await flow.run_public_resource_generation(
            settings=settings,
            task_id="task-failed",
            course_id="catalog-1",
            chapter="第一章",
            knowledge_point="失败节点",
            resource_types=["lesson"],
            webhook_url="http://backend.test/webhook",
        )

        assert result == []
        failure_payload = flow._post_webhook.await_args.args[2]
        assert failure_payload["error_code"] == "resource_gen_failed"
        assert len(failure_payload["error_code"]) <= 20


def test_resource_generation_api_accepts_only_truthful_public_types():
    payload = {
        "task_id": "task-1",
        "course_id": "catalog-1",
        "chapter": "第一章",
        "knowledge_point": "变量",
        "resource_types": ["lesson", "diagram", "example"],
        "webhook_url": "http://backend.test/api/v1/webhooks/agent",
    }

    def close_background(coroutine):
        coroutine.close()
        return MagicMock()

    with patch("agent_service_v2.api.knowledge.asyncio.create_task", side_effect=close_background):
        response = client.post("/agent/v2/knowledge/resources/generations", json=payload)
        legacy = client.post(
            "/agent/v2/knowledge/resources/generations",
            json={**payload, "resource_types": ["document"]},
        )

    assert response.status_code == 202
    assert legacy.status_code == 422
