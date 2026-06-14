import asyncio

from agent_service.agents.tutoring_react import TutorReActAgent, TUTOR_REACT_SYSTEM_PROMPT


class FakeMsg:
    """模拟 AgentScope Msg，提供 get_text_content() 与 metadata。"""

    def __init__(self, text: str, metadata: dict | None = None) -> None:
        self._text = text
        self.metadata = metadata or {}

    def get_text_content(self) -> str:
        return self._text


class FakeReActAgent:
    """模拟 AgentScope ReActAgent，记录调用参数并返回预设结果。"""

    def __init__(self, raise_error: bool = False, metadata: dict | None = None) -> None:
        self.calls: list[dict] = []
        self._raise_error = raise_error
        self._metadata = metadata

    async def __call__(self, msg, **kwargs):
        self.calls.append({"msg": msg, "kwargs": kwargs})
        if self._raise_error:
            raise RuntimeError("ReActAgent 调用失败")
        return FakeMsg(
            '{"model_text":"链式法则先看外层函数。","knowledge_points":["链式法则"],"suggestion":"先确认外层函数。"}',
            metadata=self._metadata,
        )


class FakeChatModel:
    """模拟 AgentScope OpenAIChatModel。"""

    def __init__(self, model_name: str = "generic-chat-model") -> None:
        self.model_name = model_name


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


def test_generate_returns_metadata_dict_when_structured_output_present() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(
        metadata={"model_text": "讲解指针", "knowledge_points": ["指针"]}
    )

    result = asyncio.run(agent.generate("讲讲指针"))

    assert isinstance(result, dict)
    assert result["model_text"] == "讲解指针"
    # structured_model 必须被透传给 ReActAgent
    assert "structured_model" in agent._agent.calls[0]["kwargs"]


def test_generate_skips_structured_model_for_deepseek_thinking_model() -> None:
    model = FakeChatModel(model_name="deepseek-v4-pro")
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(metadata=None)

    result = asyncio.run(agent.generate("讲讲指针"))

    assert isinstance(result, str)
    assert "structured_model" not in agent._agent.calls[0]["kwargs"]


def test_generate_falls_back_to_text_when_metadata_empty() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(metadata=None)

    result = asyncio.run(agent.generate("讲讲指针"))

    assert isinstance(result, str)
    assert "链式法则先看外层函数" in result


def test_generate_returns_none_on_exception_structured() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(raise_error=True)

    result = asyncio.run(agent.generate("讲讲指针"))

    assert result is None
