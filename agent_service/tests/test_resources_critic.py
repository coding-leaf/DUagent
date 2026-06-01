import asyncio

from agent_service.agents.resources_agents import ResourceResult
from agent_service.agents.resources_critic import ResourceCriticAgent
from agent_service.schemas.resources import ResourceGenerateRequest


def _request(**kwargs) -> ResourceGenerateRequest:
    defaults = dict(
        task_id="t-critic",
        user_id="u1",
        course_id="c1",
        webhook_url="https://example.com/hook",
        chapter="函数",
        knowledge_point="一次函数",
    )
    defaults.update(kwargs)
    return ResourceGenerateRequest(**defaults)


def _result(**kwargs) -> ResourceResult:
    defaults = dict(
        title="一次函数讲解",
        type="document",
        description="面向一次函数的知识讲解。",
        content="## 一次函数\n一次函数 y=kx+b 的图像是一条直线，k 表示斜率，b 表示截距。",
        chapter="函数",
        knowledge_point="一次函数",
        tags=["函数", "一次函数", "document"],
        generated_by="llm",
        fallback_reason=None,
        is_skeleton=False,
    )
    defaults.update(kwargs)
    return ResourceResult(**defaults)


def test_resource_critic_accepts_valid_document() -> None:
    result = asyncio.run(ResourceCriticAgent().review(_request(), _result()))

    assert result.accepted is True
    assert result.source == "rule"


def test_resource_critic_rejects_empty_content() -> None:
    result = asyncio.run(ResourceCriticAgent().review(_request(), _result(content="")))

    assert result.accepted is False
    assert "empty_content" in result.reasons


def test_resource_critic_rejects_skeleton_result() -> None:
    result = asyncio.run(ResourceCriticAgent().review(_request(), _result(is_skeleton=True)))

    assert result.accepted is False
    assert "skeleton_result" in result.reasons


def test_resource_critic_rejects_document_unrelated_to_knowledge_point() -> None:
    resource = _result(
        title="天气资料",
        description="气象科普",
        content="## 天气\n气压、湿度和风向会影响天气变化。",
        tags=["天气", "气象", "document"],
    )

    result = asyncio.run(ResourceCriticAgent().review(_request(), resource))

    assert result.accepted is False
    assert "topic_mismatch" in result.reasons


def test_resource_critic_accepts_mermaid_mindmap() -> None:
    resource = _result(
        type="mindmap",
        title="一次函数导图",
        description="一次函数知识导图",
        content="mindmap\n  root((一次函数))\n    定义\n      y = kx + b",
        tags=["函数", "一次函数", "mindmap"],
    )

    result = asyncio.run(ResourceCriticAgent().review(_request(), resource))

    assert result.accepted is True


def test_resource_critic_accepts_markdown_tree_mindmap_fallback() -> None:
    resource = _result(
        type="mindmap",
        title="一次函数树",
        description="一次函数 markdown 树",
        content="- 一次函数\n  - 定义\n  - 性质",
        tags=["函数", "一次函数", "mindmap"],
        generated_by="fallback_mermaid",
        fallback_reason="mermaid_invalid",
    )

    result = asyncio.run(ResourceCriticAgent().review(_request(), resource))

    assert result.accepted is True


def test_resource_critic_rejects_invalid_mindmap_content() -> None:
    resource = _result(
        type="mindmap",
        title="一次函数导图",
        description="一次函数知识导图",
        content="这是一段普通说明，不是导图。",
        tags=["函数", "一次函数", "mindmap"],
    )

    result = asyncio.run(ResourceCriticAgent().review(_request(), resource))

    assert result.accepted is False
    assert "invalid_mindmap_content" in result.reasons


def test_resource_critic_llm_reject_overrides_rule_acceptance() -> None:
    class RejectingChatProvider:
        async def complete(self, messages):
            return '{"accepted": false, "reasons": ["内容不够完整"]}'

    result = asyncio.run(
        ResourceCriticAgent(chat_provider=RejectingChatProvider()).review(_request(), _result())
    )

    assert result.accepted is False
    assert result.source == "llm"
    assert result.reasons == ["内容不够完整"]


def test_resource_critic_invalid_llm_json_falls_back_to_rule_result() -> None:
    class BadJsonChatProvider:
        async def complete(self, messages):
            return "不是 JSON"

    result = asyncio.run(
        ResourceCriticAgent(chat_provider=BadJsonChatProvider()).review(_request(), _result())
    )

    assert result.accepted is True
    assert result.source == "rule"


def test_resource_critic_llm_exception_falls_back_to_rule_result() -> None:
    class FailingChatProvider:
        async def complete(self, messages):
            raise RuntimeError("critic unavailable")

    result = asyncio.run(
        ResourceCriticAgent(chat_provider=FailingChatProvider()).review(_request(), _result())
    )

    assert result.accepted is True
    assert result.source == "rule"
