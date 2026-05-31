import asyncio

from agent_service.agents.tutoring_strategy import select_tutoring_strategy
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def _make_request(guidance_level: str, message: str = "帮我讲一下链式法则") -> TutoringChatRequest:
    return TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message=message,
        user_profile=TutoringUserProfile(guidance_level=guidance_level, knowledge_weak=["导数"]),
    )


def _make_context() -> TutoringRetrievalContext:
    return TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["链式法则"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )


def test_rule_strategy_maps_l1_to_guided_hint() -> None:
    strategy = asyncio.run(select_tutoring_strategy(_make_request("L1"), _make_context(), None))

    assert strategy.strategy == "guided_hint"
    assert strategy.source == "rule"


def test_rule_strategy_maps_l2_to_worked_example() -> None:
    strategy = asyncio.run(select_tutoring_strategy(_make_request("L2"), _make_context(), None))

    assert strategy.strategy == "worked_example"
    assert strategy.source == "rule"


def test_rule_strategy_maps_l3_to_direct_explanation() -> None:
    strategy = asyncio.run(select_tutoring_strategy(_make_request("L3"), _make_context(), None))

    assert strategy.strategy == "direct_explanation"
    assert strategy.source == "rule"


def test_rule_strategy_uses_clarifying_question_for_short_ambiguous_message() -> None:
    strategy = asyncio.run(select_tutoring_strategy(_make_request("L3", message="这个"), _make_context(), None))

    assert strategy.strategy == "clarifying_question"
    assert strategy.source == "rule"


def test_llm_strategy_valid_json_overrides_rule_strategy() -> None:
    class FakeChatProvider:
        async def complete(self, messages):
            return '{"strategy":"direct_explanation","focus_points":["复合函数"],"reason":"用户需要概念解释"}'

    strategy = asyncio.run(select_tutoring_strategy(_make_request("L1"), _make_context(), FakeChatProvider()))

    assert strategy.strategy == "direct_explanation"
    assert strategy.focus_points == ["复合函数"]
    assert strategy.source == "llm"


def test_llm_strategy_invalid_json_falls_back_to_rule_strategy() -> None:
    class FakeChatProvider:
        async def complete(self, messages):
            return "not json"

    strategy = asyncio.run(select_tutoring_strategy(_make_request("L2"), _make_context(), FakeChatProvider()))

    assert strategy.strategy == "worked_example"
    assert strategy.source == "rule"


def test_llm_strategy_exception_falls_back_to_rule_strategy() -> None:
    class FakeChatProvider:
        async def complete(self, messages):
            raise RuntimeError("selector failed")

    strategy = asyncio.run(select_tutoring_strategy(_make_request("L3"), _make_context(), FakeChatProvider()))

    assert strategy.strategy == "direct_explanation"
    assert strategy.source == "rule"
