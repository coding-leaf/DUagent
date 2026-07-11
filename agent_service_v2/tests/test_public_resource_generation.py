from __future__ import annotations

import importlib
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
async def test_generator_uses_course_rag_and_returns_normalized_asset():
    module = _load_module()
    response = MagicMock()
    response.text = '{"title":"变量讲义","content":"# 变量\\n\\n基于课程原文。"}'
    model = AsyncMock(return_value=response)
    generator = module.PublicResourceGenerator(model=model)

    with patch(
        f"{MODULE_NAME}.retrieve_course_context",
        new=AsyncMock(
            return_value={
                "context_text": "教材中的变量定义",
                "sources": [{"chunk_id": "chunk-1"}],
            }
        ),
    ):
        asset = await generator.generate(
            "lesson",
            chapter="第一章",
            knowledge_point="变量",
            course_id="catalog-1",
        )

    assert asset["type"] == "lesson"
    assert asset["sources"] == [{"chunk_id": "chunk-1"}]
    messages = model.await_args.args[0]
    assert len(messages) == 1
    assert "教材中的变量定义" in messages[0].content[0].text


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
