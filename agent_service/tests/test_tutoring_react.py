import asyncio

from agent_service.agents.tutoring_react import TutorReActAgent, TUTOR_REACT_SYSTEM_PROMPT


class FakeMsg:
    """模拟 AgentScope Msg，提供 get_text_content()。"""

    def __init__(self, text: str) -> None:
        self._text = text

    def get_text_content(self) -> str:
        return self._text


class FakeReActAgent:
    """模拟 AgentScope ReActAgent，记录调用参数并返回预设结果。"""

    def __init__(self, raise_error: bool = False) -> None:
        self.calls: list[dict] = []
        self._raise_error = raise_error

    async def __call__(self, msg):
        self.calls.append({"msg": msg})
        if self._raise_error:
            raise RuntimeError("ReActAgent 调用失败")
        return FakeMsg('{"model_text":"链式法则先看外层函数。","knowledge_points":["链式法则"],"suggestion":"先确认外层函数。"}')


class FakeChatModel:
    """模拟 AgentScope OpenAIChatModel。"""
    pass


class FakeFormatter:
    """模拟 AgentScope DeepSeekChatFormatter。"""
    pass


def test_tutor_react_agent_constructs_with_required_params() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)

    assert agent._agent is not None


def test_tutor_react_agent_generate_calls_react_agent_and_returns_text() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent()

    result = asyncio.run(agent.generate("帮我讲一下链式法则"))

    assert result is not None
    assert "链式法则" in result
    assert agent._agent.calls
    assert agent._agent.calls[0]["msg"].get_text_content() == "帮我讲一下链式法则"


def test_tutor_react_agent_generate_returns_none_on_exception() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(raise_error=True)

    result = asyncio.run(agent.generate("帮我讲一下链式法则"))

    assert result is None


def test_tutor_react_system_prompt_contains_tutoring_conventions() -> None:
    assert "EDUagent" in TUTOR_REACT_SYSTEM_PROMPT
    assert "knowledge_points" in TUTOR_REACT_SYSTEM_PROMPT
    assert "suggestion" in TUTOR_REACT_SYSTEM_PROMPT
    assert "model_text" in TUTOR_REACT_SYSTEM_PROMPT
