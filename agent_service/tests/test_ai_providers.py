import asyncio

import pytest

from agent_service.core.ai import ChatMessage, get_ai_providers


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
