import asyncio

from agent_service.agents.assessment_knowledge_guard import KnowledgePointGuard
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest, QuestionOption


def _question(
    *,
    content: str,
    knowledge_point: str,
    explanation: str = "导数用于描述函数在某一点附近的变化率。",
) -> GeneratedQuestion:
    return GeneratedQuestion(
        type="single_choice",
        content=content,
        options=[
            QuestionOption(key="A", text="变化率"),
            QuestionOption(key="B", text="截距"),
            QuestionOption(key="C", text="面积"),
            QuestionOption(key="D", text="频率"),
        ],
        answer="A",
        explanation=explanation,
        knowledge_point=knowledge_point,
        difficulty="medium",
    )


def test_guard_accepts_questions_matching_explicit_knowledge_point() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [_question(content="导数表示函数在某点的瞬时变化率，下列说法正确的是？", knowledge_point="导数")]

    result = asyncio.run(KnowledgePointGuard().review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"


def test_guard_rejects_questions_unrelated_to_explicit_knowledge_point() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [
        _question(
            content="今天的天气预报主要受哪些因素影响？",
            knowledge_point="天气",
            explanation="天气变化通常与气压、湿度和风向有关。",
        )
    ]

    result = asyncio.run(KnowledgePointGuard().review(request, questions))

    assert result.accepted is False
    assert "question_1_target_mismatch" in result.reasons


def test_guard_uses_wrong_points_when_request_has_no_knowledge_point() -> None:
    request = QuestionGenerateRequest(
        user_id="u1",
        course_id="c1",
        personalization_context={"wrong_points": ["极限"]},
        count=1,
    )
    questions = [
        _question(
            content="极限描述函数值趋近某点时的变化趋势，下列说法正确的是？",
            knowledge_point="极限",
            explanation="极限关注自变量趋近某点时函数值的趋近情况。",
        )
    ]

    result = asyncio.run(KnowledgePointGuard().review(request, questions))

    assert result.accepted is True


def test_guard_accepts_comprehensive_questions_when_no_target_exists() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", count=1)
    questions = [
        _question(
            content="函数、方程与图像之间的关系，下列说法正确的是？",
            knowledge_point="综合知识点",
            explanation="综合题可以同时检查函数概念、方程求解和图像理解。",
        )
    ]

    result = asyncio.run(KnowledgePointGuard().review(request, questions))

    assert result.accepted is True


def test_guard_llm_reject_overrides_rule_acceptance() -> None:
    class RejectingChatProvider:
        async def complete(self, messages):
            return '{"accepted": false, "reasons": ["没有基于课程上下文"]}'

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [_question(content="导数表示函数在某点的瞬时变化率，下列说法正确的是？", knowledge_point="导数")]

    result = asyncio.run(KnowledgePointGuard(chat_provider=RejectingChatProvider()).review(request, questions))

    assert result.accepted is False
    assert result.source == "llm"
    assert result.reasons == ["没有基于课程上下文"]


def test_guard_invalid_llm_json_falls_back_to_rule_result() -> None:
    class BadJsonChatProvider:
        async def complete(self, messages):
            return "不是 JSON"

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [_question(content="导数表示函数在某点的瞬时变化率，下列说法正确的是？", knowledge_point="导数")]

    result = asyncio.run(KnowledgePointGuard(chat_provider=BadJsonChatProvider()).review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"


def test_guard_llm_exception_falls_back_to_rule_result() -> None:
    class FailingChatProvider:
        async def complete(self, messages):
            raise RuntimeError("guard unavailable")

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [_question(content="导数表示函数在某点的瞬时变化率，下列说法正确的是？", knowledge_point="导数")]

    result = asyncio.run(KnowledgePointGuard(chat_provider=FailingChatProvider()).review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"
