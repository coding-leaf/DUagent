from agent_service.agents.tutoring import TutoringModelResponse
from agent_service.agents.tutoring_response_critic import evaluate_tutoring_response_by_rule
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

    result = evaluate_tutoring_response_by_rule(_make_request(), _make_context(), response, _make_strategy())

    assert result.accepted is True
    assert result.source == "rule"


def test_rule_critic_rejects_empty_response() -> None:
    result = evaluate_tutoring_response_by_rule(
        _make_request(), _make_context(), TutoringModelResponse(), _make_strategy()
    )

    assert result.accepted is False
    assert result.reason == "empty_response"


def test_rule_critic_rejects_off_topic_response() -> None:
    response = TutoringModelResponse(
        model_text="今天天气不错，适合散步。",
        knowledge_point_names=["天气"],
        suggestion_text="出去走走。",
    )

    result = evaluate_tutoring_response_by_rule(_make_request(), _make_context(), response, _make_strategy())

    assert result.accepted is False
    assert result.reason == "off_topic"


def test_rule_critic_accepts_when_no_trusted_terms_available() -> None:
    """检索为空且画像/策略均无可对齐术语时，不据相关性判 off_topic（避免把有效回答清零）。"""
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我解释一个核心概念",
        user_profile=TutoringUserProfile(guidance_level="L2"),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我解释一个核心概念",
        include_course_knowledge=True,
        knowledge_points=[],
        user_memory_facts=[],
        course_knowledge_chunks=[],
    )
    strategy = TutoringStrategy(
        strategy="worked_example",
        instruction="用相似例题或完整过程解释，再回到学生当前问题。",
        focus_points=[],
        source="rule",
    )
    response = TutoringModelResponse(
        model_text="指针是存放内存地址的变量，通过解引用可以操作目标变量。",
        knowledge_point_names=["指针"],
        suggestion_text="动手写一个 swap 函数。",
    )

    result = evaluate_tutoring_response_by_rule(request, context, response, strategy)

    assert result.accepted is True
    assert result.reason == "accepted"


def test_rule_critic_requires_question_for_clarifying_strategy() -> None:
    response = TutoringModelResponse(
        model_text="我先直接讲导数的定义。",
        knowledge_point_names=["导数"],
        suggestion_text="先看定义。",
    )

    result = evaluate_tutoring_response_by_rule(
        _make_request("这个"), _make_context(), response, _make_strategy("clarifying_question")
    )

    assert result.accepted is False
    assert result.reason == "missing_clarifying_question"
