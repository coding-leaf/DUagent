import asyncio

from agent_service.core import readiness


class FakeChatProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def complete(self, messages):
        self.calls.append(messages)
        if self.should_raise:
            raise RuntimeError("chat failed")
        return "pong"


class FakeEmbeddingProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def embed_texts(self, texts):
        self.calls.append(texts)
        if self.should_raise:
            raise RuntimeError("embedding failed")
        return [[0.1, 0.2]]


class FakeRerankerProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def score(self, query, documents):
        self.calls.append((query, documents))
        if self.should_raise:
            raise RuntimeError("reranker failed")
        return [0.9]


class FakeSettings:
    LLM_PROVIDER = "none"
    LLM_BASE_URL = None
    LLM_API_KEY = None
    LLM_MODEL = None
    EMBEDDING_PROVIDER = "none"
    EMBEDDING_BASE_URL = None
    EMBEDDING_API_KEY = None
    EMBEDDING_MODEL = None
    RERANKER_PROVIDER = "none"
    RERANKER_BASE_URL = None
    RERANKER_API_KEY = None
    RERANKER_MODEL = None
    QDRANT_USER_MEMORY_COLLECTION = "user_memory_v1_1024"


def test_readiness_default_mode_does_not_call_live_providers() -> None:
    chat = FakeChatProvider()
    embedding = FakeEmbeddingProvider()
    reranker = FakeRerankerProvider()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=FakeSettings(),
        live=False,
        chat_provider=chat,
        embedding_provider=embedding,
        reranker_provider=reranker,
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "ready"
    assert chat.calls == []
    assert embedding.calls == []
    assert reranker.calls == []
    assert report["checks"]["qdrant"]["ok"] is True


def test_readiness_live_mode_calls_fake_providers() -> None:
    configured = type("Configured", (FakeSettings,), {
        "LLM_PROVIDER": "agentscope_openai",
        "LLM_BASE_URL": "http://llm",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
        "EMBEDDING_PROVIDER": "agentscope_openai",
        "EMBEDDING_BASE_URL": "http://embedding",
        "EMBEDDING_API_KEY": "key",
        "EMBEDDING_MODEL": "embedding",
        "RERANKER_PROVIDER": "openai_compatible",
        "RERANKER_BASE_URL": "http://reranker",
        "RERANKER_API_KEY": "key",
        "RERANKER_MODEL": "reranker",
    })()
    chat = FakeChatProvider()
    embedding = FakeEmbeddingProvider()
    reranker = FakeRerankerProvider()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=configured,
        live=True,
        chat_provider=chat,
        embedding_provider=embedding,
        reranker_provider=reranker,
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "ready"
    assert len(chat.calls) == 1
    assert embedding.calls == [["ping"]]
    assert reranker.calls == [("ping", ["ping document"])]
    assert report["checks"]["llm"]["live_checked"] is True


def test_readiness_live_failure_marks_degraded() -> None:
    configured = type("Configured", (FakeSettings,), {
        "LLM_PROVIDER": "agentscope_openai",
        "LLM_BASE_URL": "http://llm",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
    })()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=configured,
        live=True,
        chat_provider=FakeChatProvider(should_raise=True),
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "degraded"
    assert report["checks"]["llm"]["ok"] is False
    assert "chat failed" in report["checks"]["llm"]["error"]


def test_readiness_qdrant_failure_marks_degraded() -> None:
    def failing_probe():
        raise RuntimeError("qdrant down")

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=FakeSettings(),
        live=False,
        qdrant_probe=failing_probe,
    ))

    assert report["status"] == "degraded"
    assert report["checks"]["qdrant"]["ok"] is False
    assert "qdrant down" in report["checks"]["qdrant"]["error"]


def test_readiness_cli_imports() -> None:
    from agent_service.tools import readiness_check

    assert callable(readiness_check.main)
