import asyncio

from agent_service.agents.tutoring import TutoringModelResponse
from agent_service.agents.tutoring_response_critic import evaluate_tutoring_response
from agent_service.agents.tutoring_strategy import TutoringStrategy
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def _make_request(message: str = "讲讲导数") -> TutoringChatRequest:
    return TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message=message,
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )


def _make_context() -> TutoringRetrievalContext:
    return TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="讲讲导数",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=[],
        course_knowledge_chunks=["导数表示函数变化率"],
    )


def _make_strategy(name: str = "worked_example") -> TutoringStrategy:
    return TutoringStrategy(
        strategy=name,
        instruction="用相似例题或完整过程解释，再回到学生当前问题。",
        focus_points=["导数"],
        source="rule",
    )


def test_rule_critic_accepts_relevant_tutoring_response() -> None:
    response = TutoringModelResponse(
        model_text="导数可以理解为函数在某一点附近的变化率。",
        knowledge_point_names=["导数"],
        suggestion_text="先画图理解变化率。",
    )

    result = asyncio.run(evaluate_tutoring_response(_make_request(), _make_context(), response, _make_strategy(), None))

    assert result.accepted is True
    assert result.source == "rule"


def test_rule_critic_rejects_empty_response() -> None:
    result = asyncio.run(
        evaluate_tutoring_response(_make_request(), _make_context(), TutoringModelResponse(), _make_strategy(), None)
    )

    assert result.accepted is False
    assert result.reason == "empty_response"


def test_rule_critic_rejects_off_topic_response() -> None:
    response = TutoringModelResponse(
        model_text="今天天气不错，适合散步。",
        knowledge_point_names=["天气"],
        suggestion_text="出去走走。",
    )

    result = asyncio.run(evaluate_tutoring_response(_make_request(), _make_context(), response, _make_strategy(), None))

    assert result.accepted is False
    assert result.reason == "off_topic"


def test_rule_critic_requires_question_for_clarifying_strategy() -> None:
    response = TutoringModelResponse(
        model_text="我先直接讲导数的定义。",
        knowledge_point_names=["导数"],
        suggestion_text="先看定义。",
    )

    result = asyncio.run(
        evaluate_tutoring_response(_make_request("这个"), _make_context(), response, _make_strategy("clarifying_question"), None)
    )

    assert result.accepted is False
    assert result.reason == "missing_clarifying_question"


def test_llm_critic_valid_json_overrides_rule_result() -> None:
    response = TutoringModelResponse(
        model_text="导数表示变化率。",
        knowledge_point_names=["导数"],
        suggestion_text="先做一道题。",
    )

    class FakeChatProvider:
        async def complete(self, messages):
            return '{"accepted": false, "reason": "too_direct"}'

    result = asyncio.run(
        evaluate_tutoring_response(_make_request(), _make_context(), response, _make_strategy(), FakeChatProvider())
    )

    assert result.accepted is False
    assert result.reason == "too_direct"
    assert result.source == "llm"


def test_llm_critic_invalid_json_falls_back_to_rule_result() -> None:
    response = TutoringModelResponse(
        model_text="导数表示变化率。",
        knowledge_point_names=["导数"],
        suggestion_text="先做一道题。",
    )

    class FakeChatProvider:
        async def complete(self, messages):
            return "not json"

    result = asyncio.run(
        evaluate_tutoring_response(_make_request(), _make_context(), response, _make_strategy(), FakeChatProvider())
    )

    assert result.accepted is True
    assert result.source == "rule"


def test_llm_critic_exception_falls_back_to_rule_result() -> None:
    response = TutoringModelResponse(
        model_text="今天天气不错，适合散步。",
        knowledge_point_names=["天气"],
        suggestion_text="出去走走。",
    )

    class FakeChatProvider:
        async def complete(self, messages):
            raise RuntimeError("critic failed")

    result = asyncio.run(
        evaluate_tutoring_response(_make_request(), _make_context(), response, _make_strategy(), FakeChatProvider())
    )

    assert result.accepted is False
    assert result.reason == "off_topic"
    assert result.source == "rule"
