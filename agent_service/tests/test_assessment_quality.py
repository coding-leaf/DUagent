import asyncio

from agent_service.agents.assessment_quality import review_generated_questions
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest, QuestionOption


def _question(
    *,
    content: str,
    knowledge_point: str = "顺序存储结构",
    explanation: str = "顺序存储结构可直接根据下标计算地址，因此访问时间复杂度为 O(1)。",
    difficulty: str | None = "medium",
    options: list[QuestionOption] | None = None,
) -> GeneratedQuestion:
    return GeneratedQuestion(
        type="single_choice",
        content=content,
        options=options if options is not None else [
            QuestionOption(key="A", text="O(1)"),
            QuestionOption(key="B", text="O(n)"),
            QuestionOption(key="C", text="O(log n)"),
            QuestionOption(key="D", text="O(n log n)"),
        ],
        answer="A",
        explanation=explanation,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
    )


def test_quality_accepts_rule_passed_question() -> None:
    request = QuestionGenerateRequest(
        user_id="u1",
        course_id="c1",
        knowledge_point="顺序存储结构",
        difficulty="medium",
        count=1,
    )
    questions = [
        _question(content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？")
    ]

    result = asyncio.run(review_generated_questions(request, questions))

    assert result.accepted is True
    assert result.gate == "all"
    assert result.source == "rule"


def test_quality_rejects_bad_choice_options_when_basic_gate_enabled() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", count=1)
    questions = [
        _question(
            content="顺序表的随机访问时间复杂度是多少？",
            options=[QuestionOption(key="A", text="O(1)")],
        )
    ]

    result = asyncio.run(review_generated_questions(request, questions))

    assert result.accepted is False
    assert result.gate == "basic_quality"
    assert "question_1_choice_options_count" in result.reasons


def test_quality_can_skip_basic_gate_for_existing_llm_fallback_semantics() -> None:
    request = QuestionGenerateRequest(
        user_id="u1",
        course_id="c1",
        knowledge_point="顺序存储结构",
        count=1,
    )
    questions = [
        _question(
            content="顺序存储结构支持按下标随机访问，下列说法正确的是？",
            options=[],
        )
    ]

    result = asyncio.run(
        review_generated_questions(request, questions, include_basic_quality=False)
    )

    assert result.accepted is True


def test_quality_rejects_knowledge_point_mismatch() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="导数", count=1)
    questions = [
        _question(
            content="今天的天气预报主要受哪些因素影响？",
            knowledge_point="天气",
            explanation="天气变化通常与气压、湿度和风向有关。",
        )
    ]

    result = asyncio.run(review_generated_questions(request, questions))

    assert result.accepted is False
    assert result.gate == "knowledge_point"
    assert "question_1_target_mismatch" in result.reasons


def test_quality_rejects_difficulty_mismatch() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="easy", count=1)
    questions = [
        _question(
            content="综合证明顺序表插入、删除和扩容策略在均摊复杂度下的性能边界，并分析多概念联立条件。",
            explanation="需要结合均摊分析、扩容策略和复杂度证明进行综合推导。",
            difficulty="easy",
        )
    ]

    result = asyncio.run(review_generated_questions(request, questions))

    assert result.accepted is False
    assert result.gate == "difficulty"
    assert "question_1_too_hard_for_easy" in result.reasons


def test_quality_llm_rejection_overrides_rule_acceptance() -> None:
    class RejectingChatProvider:
        async def complete(self, messages):
            if "知识点贴合度" in messages[0].content:
                return '{"accepted": false, "reasons": ["没有基于课程上下文"]}'
            return '{"accepted": true, "reasons": []}'

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="顺序存储结构", count=1)
    questions = [
        _question(content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？")
    ]

    result = asyncio.run(
        review_generated_questions(request, questions, chat_provider=RejectingChatProvider())
    )

    assert result.accepted is False
    assert result.gate == "knowledge_point"
    assert result.source == "llm"
    assert result.reasons == ["没有基于课程上下文"]


def test_quality_llm_exception_falls_back_to_rule_result() -> None:
    class FailingChatProvider:
        async def complete(self, messages):
            raise RuntimeError("review unavailable")

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", knowledge_point="顺序存储结构", count=1)
    questions = [
        _question(content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？")
    ]

    result = asyncio.run(
        review_generated_questions(request, questions, chat_provider=FailingChatProvider())
    )

    assert result.accepted is True
    assert result.source == "rule"
