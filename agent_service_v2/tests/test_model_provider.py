from unittest.mock import MagicMock, patch

from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_chat_model_from_settings,
)


def test_build_chat_model_returns_none_without_complete_settings():
    settings = AgentModelSettings(_env_file=None, LLM_PROVIDER="agentscope_openai")

    assert build_chat_model_from_settings(settings) is None


def test_build_chat_model_creates_agentscope_openai_model():
    settings = AgentModelSettings(
        LLM_PROVIDER="agentscope_openai",
        LLM_BASE_URL="https://example.com/v1",
        LLM_API_KEY="sk-test",
        LLM_MODEL="deepseek-chat",
        LLM_TIMEOUT=42.0,
    )
    captured: dict = {}

    class FakeCredential:
        def __init__(self, **kwargs):
            captured["credential"] = kwargs

    class FakeModel:
        def __init__(self, **kwargs):
            captured["model"] = kwargs

    with (
        patch("agentscope.credential.OpenAICredential", FakeCredential),
        patch("agentscope.model.OpenAIChatModel", FakeModel),
        patch("agentscope.formatter.DeepSeekChatFormatter", MagicMock()),
    ):
        model = build_chat_model_from_settings(settings)

    assert isinstance(model, FakeModel)
    assert captured["credential"] == {
        "api_key": "sk-test",
        "base_url": "https://example.com/v1",
    }
    assert captured["model"]["model"] == "deepseek-chat"
    assert captured["model"]["stream"] is True
    assert captured["model"]["client_kwargs"] == {"timeout": 42.0}


def test_build_chat_model_can_disable_streaming_for_background_json_tasks():
    settings = AgentModelSettings(
        LLM_PROVIDER="agentscope_openai",
        LLM_BASE_URL="https://example.com/v1",
        LLM_API_KEY="sk-test",
        LLM_MODEL="deepseek-chat",
    )
    captured: dict = {}

    class FakeCredential:
        def __init__(self, **kwargs):
            captured["credential"] = kwargs

    class FakeModel:
        def __init__(self, **kwargs):
            captured["model"] = kwargs

    with (
        patch("agentscope.credential.OpenAICredential", FakeCredential),
        patch("agentscope.model.OpenAIChatModel", FakeModel),
        patch("agentscope.formatter.DeepSeekChatFormatter", MagicMock()),
    ):
        model = build_chat_model_from_settings(settings, stream=False)

    assert isinstance(model, FakeModel)
    assert captured["model"]["stream"] is False
