import asyncio

import pytest

from agent_service.core import ai as ai_module
from agent_service.core.ai import (
    AgentScopeChatProvider,
    AgentScopeEmbeddingProvider,
    ChatMessage,
    OpenAICompatibleRerankerProvider,
    get_ai_providers,
)


def test_unconfigured_ai_providers_fail_explicitly(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "none"
        EMBEDDING_BASE_URL = None
        EMBEDDING_API_KEY = None
        EMBEDDING_MODEL = None
        RERANKER_PROVIDER = "none"
        RERANKER_BASE_URL = None
        RERANKER_API_KEY = None
        RERANKER_MODEL = None
        LLM_PROVIDER = "none"
        LLM_BASE_URL = None
        LLM_API_KEY = None
        LLM_MODEL = None

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert providers.embedding is None
    assert providers.reranker is None
    assert providers.chat is None


def test_get_ai_providers_accepts_injected_providers() -> None:
    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[float(len(text))] for text in texts]

    class FakeChatProvider:
        async def complete(self, messages):
            return messages[-1].content

    class FakeRerankerProvider:
        async def score(self, query, documents):
            return [float(len(query) + len(document)) for document in documents]

    providers = get_ai_providers(
        embedding_provider=FakeEmbeddingProvider(),
        reranker_provider=FakeRerankerProvider(),
        chat_provider=FakeChatProvider(),
    )

    assert asyncio.run(providers.embedding.embed_texts(["导数"])) == [[2.0]]
    assert asyncio.run(providers.reranker.score("导数", ["导数定义"])) == [6.0]
    assert asyncio.run(providers.chat.complete([ChatMessage(role="user", content="解释导数")])) == "解释导数"


def test_get_ai_providers_builds_agentscope_embedding_from_settings(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "agentscope_openai"
        EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
        EMBEDDING_API_KEY = "test-key"
        EMBEDDING_MODEL = "BAAI/bge-m3"
        EMBEDDING_DIMENSION = 1024
        EMBEDDING_REQUEST_DIMENSIONS_ENABLED = False

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.embedding, AgentScopeEmbeddingProvider)
    assert providers.embedding.model.dimensions is None


def test_get_ai_providers_can_send_embedding_dimensions_when_enabled(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "agentscope_openai"
        EMBEDDING_BASE_URL = "https://api.openai.com/v1"
        EMBEDDING_API_KEY = "test-key"
        EMBEDDING_MODEL = "text-embedding-3-large"
        EMBEDDING_DIMENSION = 1024
        EMBEDDING_REQUEST_DIMENSIONS_ENABLED = True

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.embedding, AgentScopeEmbeddingProvider)
    assert providers.embedding.model.dimensions == 1024


def test_agentscope_embedding_provider_wraps_embedding_model() -> None:
    class FakeEmbeddingResponse:
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

    class FakeEmbeddingModel:
        def __init__(self) -> None:
            self.calls = []

        async def __call__(self, texts):
            self.calls.append(texts)
            return FakeEmbeddingResponse()

    model = FakeEmbeddingModel()
    provider = AgentScopeEmbeddingProvider(model)

    vectors = asyncio.run(provider.embed_texts(["第一段", "第二段"]))

    assert model.calls == [["第一段", "第二段"]]
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_get_ai_providers_builds_agentscope_chat_from_settings(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "none"
        EMBEDDING_BASE_URL = None
        EMBEDDING_API_KEY = None
        EMBEDDING_MODEL = None
        LLM_PROVIDER = "agentscope_openai"
        LLM_BASE_URL = "https://api.deepseek.com"
        LLM_API_KEY = "test-key"
        LLM_MODEL = "deepseek-v4-flash"
        LLM_STRUCTURED_OUTPUT_ENABLED = False

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.chat, AgentScopeChatProvider)
    assert providers.chat.json_mode is False


def test_agentscope_chat_provider_formats_messages_and_returns_text() -> None:
    class FakeFormatter:
        def __init__(self) -> None:
            self.names = []

        def format(self, msgs):
            self.names = [message.name for message in msgs]
            return [{"role": message.role, "content": message.content} for message in msgs]

    class FakeChatModel:
        def __init__(self) -> None:
            self.calls = []

        async def __call__(self, messages):
            self.calls.append(messages)
            return type("FakeChatResponse", (), {"content": [{"text": "导数表示函数变化率。"}]})()

    formatter = FakeFormatter()
    model = FakeChatModel()
    provider = AgentScopeChatProvider(model=model, formatter=formatter)

    text = asyncio.run(
        provider.complete(
            [
                ChatMessage(role="system", content="你是老师"),
                ChatMessage(role="user", content="解释导数"),
            ]
        )
    )

    assert formatter.names == ["system", "user"]
    assert model.calls == [
        [
            {"role": "system", "content": "你是老师"},
            {"role": "user", "content": "解释导数"},
        ]
    ]
    assert text == "导数表示函数变化率。"


def test_agentscope_chat_provider_awaits_async_formatter() -> None:
    class FakeFormatter:
        async def format(self, msgs):
            return [{"role": message.role, "content": message.content} for message in msgs]

    class FakeChatModel:
        def __init__(self) -> None:
            self.calls = []

        async def __call__(self, messages):
            self.calls.append(messages)
            return type("FakeChatResponse", (), {"content": [{"text": "异步 formatter 可用。"}]})()

    model = FakeChatModel()
    provider = AgentScopeChatProvider(model=model, formatter=FakeFormatter())

    text = asyncio.run(provider.complete([ChatMessage(role="user", content="测试")]))

    assert model.calls == [[{"role": "user", "content": "测试"}]]
    assert text == "异步 formatter 可用。"


def test_agentscope_chat_provider_passes_json_mode_request_format() -> None:
    class FakeFormatter:
        def format(self, msgs):
            return [{"role": message.role, "content": message.content} for message in msgs]

    class FakeChatModel:
        def __init__(self) -> None:
            self.kwargs = None

        async def __call__(self, messages, **kwargs):
            self.kwargs = kwargs
            return type(
                "FakeChatResponse",
                (),
                {"content": [{"text": "{\"model_text\":\"JSON 答案\"}"}]},
            )()

    model = FakeChatModel()
    provider = AgentScopeChatProvider(model=model, formatter=FakeFormatter(), json_mode=True)

    result = asyncio.run(provider.complete([ChatMessage(role="user", content="解释导数")]))

    assert model.kwargs == {"response_format": {"type": "json_object"}}
    assert result == "{\"model_text\":\"JSON 答案\"}"


def test_get_ai_providers_builds_openai_compatible_reranker_from_settings(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "none"
        EMBEDDING_BASE_URL = None
        EMBEDDING_API_KEY = None
        EMBEDDING_MODEL = None
        LLM_PROVIDER = "none"
        LLM_BASE_URL = None
        LLM_API_KEY = None
        LLM_MODEL = None
        RERANKER_PROVIDER = "openai_compatible"
        RERANKER_BASE_URL = "http://localhost:8000/v1"
        RERANKER_API_KEY = "test-key"
        RERANKER_MODEL = "bge-reranker-v2-m3"

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.reranker, OpenAICompatibleRerankerProvider)


def test_openai_compatible_reranker_provider_posts_scores_request() -> None:
    captured = {}

    def fake_request(url: str, headers: dict[str, str], payload: dict) -> dict:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "data": [
                {"index": 1, "score": 0.2},
                {"index": 0, "score": 0.9},
            ]
        }

    provider = OpenAICompatibleRerankerProvider(
        base_url="http://localhost:8000/v1",
        api_key="test-key",
        model="bge-reranker-v2-m3",
        request_sender=fake_request,
    )

    scores = asyncio.run(provider.score("导数", ["导数定义", "函数图像"]))

    assert captured["url"] == "http://localhost:8000/v1/rerank"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "bge-reranker-v2-m3",
        "query": "导数",
        "documents": ["导数定义", "函数图像"],
    }
    assert scores == [0.9, 0.2]


def test_openai_compatible_reranker_provider_accepts_siliconflow_results() -> None:
    def fake_request(url: str, headers: dict[str, str], payload: dict) -> dict:
        return {
            "results": [
                {"index": 1, "document": {"text": "函数图像"}, "relevance_score": 0.2},
                {"index": 0, "document": {"text": "导数定义"}, "relevance_score": 0.9},
            ]
        }

    provider = OpenAICompatibleRerankerProvider(
        base_url="https://api.siliconflow.cn/v1",
        api_key="test-key",
        model="BAAI/bge-reranker-v2-m3",
        request_sender=fake_request,
    )

    scores = asyncio.run(provider.score("导数", ["导数定义", "函数图像"]))

    assert scores == [0.9, 0.2]


def test_openai_compatible_reranker_provider_rejects_misaligned_scores() -> None:
    def fake_request(url: str, headers: dict[str, str], payload: dict) -> dict:
        return {"data": [{"index": 0, "score": 0.9}]}

    provider = OpenAICompatibleRerankerProvider(
        base_url="http://localhost:8000/v1",
        api_key="test-key",
        model="bge-reranker-v2-m3",
        request_sender=fake_request,
    )

    with pytest.raises(ValueError, match="Reranker response length does not match documents"):
        asyncio.run(provider.score("导数", ["导数定义", "函数图像"]))
