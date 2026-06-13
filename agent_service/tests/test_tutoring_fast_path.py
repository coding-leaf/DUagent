"""快速链路端到端测试：Guard + 重试 + 规则兜底 + review 事件。"""

import asyncio
import json

from agent_service.agents.tutoring import generate_tutoring_sse_events
from agent_service.agents.tutoring import TutoringModelResponse
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def _make_request(message: str = "指针怎么用？", weak: list[str] | None = None) -> TutoringChatRequest:
    return TutoringChatRequest(
        user_id="u1",
        course_id="c1",
        message=message,
        user_profile=TutoringUserProfile(
            guidance_level="L2",
            knowledge_weak=["指针"] if weak is None else weak,
        ),
    )


async def _collect_events(request, providers) -> list[dict]:
    events = []
    async for line in generate_tutoring_sse_events(request, providers=providers):
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if data:
                events.append(json.loads(data))
    return events


class _FakeChat:
    model = object()
    formatter = object()


class _FakeProviders:
    def __init__(self):
        self.chat = _FakeChat()
        self.embedding = None
        self.reranker = None


def test_fast_path_no_llm_critic_no_fallback(monkeypatch) -> None:
    async def fake_react(*args, **kwargs):
        return TutoringModelResponse(
            model_text="指针是存储内存地址的变量，使用时注意 malloc/free 配对。",
            knowledge_point_names=["指针"],
            suggestion_text="继续练习动态内存分配。",
        )

    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    providers = _FakeProviders()
    events = asyncio.run(_collect_events(_make_request(), providers))

    types = [event.get("type") for event in events]

    assert "chunk" in types
    assert "done" in types
    assert "review" not in types


def test_fast_path_guard_reject_triggers_retry_then_rule_fallback(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_react(*args, **kwargs):
        calls["count"] += 1
        return TutoringModelResponse()

    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    providers = _FakeProviders()
    events = asyncio.run(_collect_events(_make_request(), providers))

    types = [event.get("type") for event in events]
    chunks = [event["content"] for event in events if event.get("type") == "chunk"]

    assert "chunk" in types
    assert "done" in types
    assert calls["count"] == 2
    assert "这次重点看指针" in chunks[-1]


def test_fast_path_review_event_after_done_on_rule_fallback(monkeypatch) -> None:
    async def fake_react(*args, **kwargs):
        return TutoringModelResponse()

    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    providers = _FakeProviders()
    events = asyncio.run(_collect_events(_make_request(), providers))

    types = [event.get("type") for event in events]
    done_idx = types.index("done")
    review_idx = types.index("review")
    review = events[review_idx]

    assert review_idx > done_idx
    assert review["status"] == "flagged"
    assert review["reason"] == "empty_response"
