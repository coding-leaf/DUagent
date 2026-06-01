import asyncio

from agent_service.agents.assessment_difficulty_balancer import DifficultyBalancer
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest, QuestionOption


def _question(
    *,
    content: str,
    explanation: str,
    difficulty: str | None = "medium",
) -> GeneratedQuestion:
    return GeneratedQuestion(
        type="single_choice",
        content=content,
        options=[
            QuestionOption(key="A", text="O(1)"),
            QuestionOption(key="B", text="O(n)"),
            QuestionOption(key="C", text="O(log n)"),
            QuestionOption(key="D", text="O(n log n)"),
        ],
        answer="A",
        explanation=explanation,
        knowledge_point="顺序存储结构",
        difficulty=difficulty,
    )


def test_balancer_accepts_easy_foundation_question() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="easy", count=1)
    questions = [
        _question(
            content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？",
            explanation="顺序存储结构可直接根据下标计算地址，因此访问时间复杂度为 O(1)。",
            difficulty="easy",
        )
    ]

    result = asyncio.run(DifficultyBalancer().review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"


def test_balancer_rejects_easy_question_with_complex_reasoning() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="easy", count=1)
    questions = [
        _question(
            content="综合证明顺序表插入、删除和扩容策略在均摊复杂度下的性能边界，并分析多概念联立条件。",
            explanation="需要结合均摊分析、扩容策略和复杂度证明进行综合推导。",
            difficulty="easy",
        )
    ]

    result = asyncio.run(DifficultyBalancer().review(request, questions))

    assert result.accepted is False
    assert "question_1_too_hard_for_easy" in result.reasons


def test_balancer_accepts_hard_comprehensive_question() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="hard", count=1)
    questions = [
        _question(
            content="给定顺序表频繁插入、删除和随机访问的混合场景，综合分析扩容策略对时间与空间复杂度的影响。",
            explanation="需要比较随机访问、移动元素成本、扩容时机和空间冗余，综合推理不同操作比例下的复杂度。",
            difficulty="hard",
        )
    ]

    result = asyncio.run(DifficultyBalancer().review(request, questions))

    assert result.accepted is True


def test_balancer_rejects_hard_question_that_only_recalls_definition() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="hard", count=1)
    questions = [
        _question(
            content="什么是顺序存储结构？",
            explanation="顺序存储结构是用连续存储空间保存元素。",
            difficulty="hard",
        )
    ]

    result = asyncio.run(DifficultyBalancer().review(request, questions))

    assert result.accepted is False
    assert "question_1_too_shallow_for_hard" in result.reasons


def test_balancer_accepts_when_request_has_no_difficulty() -> None:
    request = QuestionGenerateRequest(user_id="u1", course_id="c1", count=1)
    questions = [
        _question(
            content="什么是顺序存储结构？",
            explanation="顺序存储结构是用连续存储空间保存元素。",
            difficulty=None,
        )
    ]

    result = asyncio.run(DifficultyBalancer().review(request, questions))

    assert result.accepted is True


def test_balancer_llm_reject_overrides_rule_acceptance() -> None:
    class RejectingChatProvider:
        async def complete(self, messages):
            return '{"accepted": false, "reasons": ["难度过浅"]}'

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="medium", count=1)
    questions = [
        _question(
            content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？",
            explanation="顺序存储结构可直接根据下标计算地址，因此访问时间复杂度为 O(1)。",
        )
    ]

    result = asyncio.run(DifficultyBalancer(chat_provider=RejectingChatProvider()).review(request, questions))

    assert result.accepted is False
    assert result.source == "llm"
    assert result.reasons == ["难度过浅"]


def test_balancer_invalid_llm_json_falls_back_to_rule_result() -> None:
    class BadJsonChatProvider:
        async def complete(self, messages):
            return "不是 JSON"

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="medium", count=1)
    questions = [
        _question(
            content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？",
            explanation="顺序存储结构可直接根据下标计算地址，因此访问时间复杂度为 O(1)。",
        )
    ]

    result = asyncio.run(DifficultyBalancer(chat_provider=BadJsonChatProvider()).review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"


def test_balancer_llm_exception_falls_back_to_rule_result() -> None:
    class FailingChatProvider:
        async def complete(self, messages):
            raise RuntimeError("balancer unavailable")

    request = QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="medium", count=1)
    questions = [
        _question(
            content="顺序存储结构中，按下标访问元素的时间复杂度通常是多少？",
            explanation="顺序存储结构可直接根据下标计算地址，因此访问时间复杂度为 O(1)。",
        )
    ]

    result = asyncio.run(DifficultyBalancer(chat_provider=FailingChatProvider()).review(request, questions))

    assert result.accepted is True
    assert result.source == "rule"
