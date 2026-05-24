import asyncio

import pytest

from agent_service.core import ai as ai_module
from agent_service.core.ai import (
    ChatMessage,
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleRerankerProvider,
    get_ai_providers,
)


def test_unconfigured_ai_providers_fail_explicitly() -> None:
    providers = get_ai_providers()

    with pytest.raises(NotImplementedError, match="Embedding provider is not configured"):
        asyncio.run(providers.embedding.embed_texts(["一次函数"]))

    with pytest.raises(NotImplementedError, match="Reranker provider is not configured"):
        asyncio.run(providers.reranker.score("一次函数", ["一次函数图像性质"]))

    with pytest.raises(NotImplementedError, match="Chat provider is not configured"):
        asyncio.run(providers.chat.complete([ChatMessage(role="user", content="解释一次函数")]))


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


def test_get_ai_providers_builds_openai_compatible_embedding_from_settings(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "openai_compatible"
        EMBEDDING_BASE_URL = "http://localhost:8000/v1"
        EMBEDDING_API_KEY = "test-key"
        EMBEDDING_MODEL = "BAAI/bge-m3"

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.embedding, OpenAICompatibleEmbeddingProvider)


def test_openai_compatible_embedding_provider_posts_embeddings_request() -> None:
    captured = {}

    def fake_request(url: str, headers: dict[str, str], payload: dict) -> dict:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ]
        }

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="http://localhost:8000/v1",
        api_key="test-key",
        model="BAAI/bge-m3",
        request_sender=fake_request,
    )

    vectors = asyncio.run(provider.embed_texts(["第一段", "第二段"]))

    assert captured["url"] == "http://localhost:8000/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {"model": "BAAI/bge-m3", "input": ["第一段", "第二段"]}
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_get_ai_providers_builds_openai_compatible_chat_from_settings(monkeypatch) -> None:
    class FakeSettings:
        EMBEDDING_PROVIDER = "none"
        EMBEDDING_BASE_URL = None
        EMBEDDING_API_KEY = None
        EMBEDDING_MODEL = None
        LLM_PROVIDER = "openai_compatible"
        LLM_BASE_URL = "http://localhost:8000/v1"
        LLM_API_KEY = "test-key"
        LLM_MODEL = "gpt-4o-mini"

    monkeypatch.setattr(ai_module, "settings", FakeSettings())

    providers = get_ai_providers()

    assert isinstance(providers.chat, OpenAICompatibleChatProvider)


def test_openai_compatible_chat_provider_posts_chat_completions_request() -> None:
    captured = {}

    def fake_request(url: str, headers: dict[str, str], payload: dict) -> dict:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "content": "导数表示函数变化率。"
                    }
                }
            ]
        }

    provider = OpenAICompatibleChatProvider(
        base_url="http://localhost:8000/v1",
        api_key="test-key",
        model="gpt-4o-mini",
        request_sender=fake_request,
    )

    text = asyncio.run(
        provider.complete(
            [
                ChatMessage(role="system", content="你是老师"),
                ChatMessage(role="user", content="解释导数"),
            ]
        )
    )

    assert captured["url"] == "http://localhost:8000/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "你是老师"},
            {"role": "user", "content": "解释导数"},
        ],
    }
    assert text == "导数表示函数变化率。"


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
