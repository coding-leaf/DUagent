import asyncio
from unittest.mock import patch

from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
from agent_service.agents.tutoring_strategy import TutoringStrategy
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import RecentMessage, TutoringChatRequest, TutoringUserProfile


def _make_request() -> TutoringChatRequest:
    return TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(
            guidance_level="L2",
            knowledge_weak=["导数"],
            knowledge_mastered=["函数"],
        ),
    )


def _make_context() -> TutoringRetrievalContext:
    return TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="链式法则怎么用？",
        include_course_knowledge=True,
        knowledge_points=["链式法则"],
        user_memory_facts=["用户容易把内外层顺序写反"],
        course_knowledge_chunks=["链式法则用于复合函数求导，先求外层再乘内层"],
    )


class FakeReactAgent:
    """模拟 TutorReActAgent，可配置 generate 的返回值和行为。"""

    def __init__(self, output=None, should_raise: bool = False) -> None:
        self._output = output
        self._should_raise = should_raise
        self.calls = []

    async def generate(self, user_message: str):
        self.calls.append(user_message)
        if self._should_raise:
            raise RuntimeError("agent failure")
        return self._output


def test_react_response_returns_parsed_model_on_valid_json() -> None:
    request = _make_request()
    context = _make_context()

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output='{"model_text":"链式法则先看外层函数，再乘以内层导数。",'
        '"knowledge_points":["链式法则","复合函数"],'
        '"suggestion":"先确认外层函数，再检查内层导数。"}'
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(request, context, FakeProvider())
        )

    assert result is not None
    assert result.model_text == "链式法则先看外层函数，再乘以内层导数。"
    assert result.knowledge_point_names == ["链式法则", "复合函数"]
    assert result.suggestion_text == "先确认外层函数，再检查内层导数。"
    assert len(fake_agent.calls) == 1
    assert "链式法则怎么用？" in fake_agent.calls[0]
    assert "用户容易把内外层顺序写反" in fake_agent.calls[0]


def test_react_response_includes_strategy_context_in_user_message() -> None:
    request = _make_request()
    context = _make_context()
    strategy = TutoringStrategy(
        strategy="worked_example",
        instruction="用相似例题或完整过程解释，再回到学生当前问题。",
        focus_points=["链式法则", "复合函数"],
        source="rule",
    )

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output='{"model_text":"先看一个相似例题。","knowledge_points":["链式法则"],"suggestion":"再做一题。"}'
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        asyncio.run(
            generate_tutoring_react_response(
                request,
                context,
                FakeProvider(),
                strategy=strategy,
            )
        )

    assert "辅导策略：worked_example" in fake_agent.calls[0]
    assert "策略要求：用相似例题或完整过程解释，再回到学生当前问题。" in fake_agent.calls[0]
    assert "策略关注点：链式法则、复合函数" in fake_agent.calls[0]


def test_react_user_message_marks_recent_messages_as_short_term_context() -> None:
    request = _make_request().model_copy(update={
        "message": "我刚才让你记住的变量名是什么？",
        "recent_messages": [
            RecentMessage(role="user", content="请记住：变量名是 alpha_count"),
            RecentMessage(role="assistant", content="我记住了，变量名是 alpha_count。"),
        ],
    })
    context = _make_context()

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output='{"model_text":"你刚才让我记住的变量名是 alpha_count。","knowledge_points":[]}'
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        asyncio.run(
            generate_tutoring_react_response(request, context, FakeProvider())
        )

    prompt = fake_agent.calls[0]
    assert "最近对话（短期上下文）" in prompt
    assert "当前问题提到刚才、上文或之前时，优先依据最近对话回答" in prompt
    assert "[user] 请记住：变量名是 alpha_count" in prompt
    assert "[assistant] 我记住了，变量名是 alpha_count。" in prompt
    assert prompt.rindex("当前问题：我刚才让你记住的变量名是什么？") > prompt.index("最近对话（短期上下文）")


def test_react_response_returns_none_for_non_agentscope_provider() -> None:
    result = asyncio.run(
        generate_tutoring_react_response(
            _make_request(), _make_context(), None
        )
    )
    assert result is None


def test_react_response_returns_none_when_agent_raises() -> None:
    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(should_raise=True)

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(
                _make_request(), _make_context(), FakeProvider()
            )
        )

    assert result is None


def test_react_response_returns_none_when_agent_generates_none() -> None:
    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(output=None)

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(
                _make_request(), _make_context(), FakeProvider()
            )
        )

    assert result is None


def test_react_response_parses_plain_text_as_model_text() -> None:
    """ReActAgent 返回非 JSON 的纯文本时，model_text 仍能被提取。"""
    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output="链式法则需要从外层函数开始，逐步向内层求导。这是一个常见考点。"
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(
                _make_request(), _make_context(), FakeProvider()
            )
        )

    assert result is not None
    assert result.model_text == "链式法则需要从外层函数开始，逐步向内层求导。这是一个常见考点。"
    assert result.knowledge_point_names == []
    assert result.suggestion_text is None


def test_react_response_builds_from_metadata_dict() -> None:
    request = _make_request()
    context = _make_context()

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output={
            "model_text": "链式法则先看外层函数，再乘内层导数。",
            "knowledge_points": ["链式法则", "复合函数"],
            "suggestion": "先确认外层，再检查内层。",
            "diagram": "flowchart TD\n A-->B",
        }
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(request, context, FakeProvider())
        )

    assert result is not None
    assert result.model_text == "链式法则先看外层函数，再乘内层导数。"
    assert result.knowledge_point_names == ["链式法则", "复合函数"]
    assert result.suggestion_text == "先确认外层，再检查内层。"
    assert result.diagram == "flowchart TD\n A-->B"


def test_react_response_does_not_log_succeeded_when_none(caplog) -> None:
    import logging

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(output=None)

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        with caplog.at_level(logging.INFO, logger="agent_service.agents.tutoring_react_flow"):
            result = asyncio.run(
                generate_tutoring_react_response(
                    _make_request(), _make_context(), FakeProvider()
                )
            )

    assert result is None
    assert "Tutoring ReAct succeeded" not in caplog.text
