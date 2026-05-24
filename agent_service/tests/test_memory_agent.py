import importlib
import asyncio

from agent_service.schemas.memory import MemoryCompressRequest, MemoryMessage


def test_compress_memory_merges_old_summary_and_messages() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary="此前用户在学习函数基础。",
            messages=[
                MemoryMessage(role="user", content="我总是在导数定义上卡住", timestamp="2026-05-22T10:00:00Z"),
                MemoryMessage(role="assistant", content="可以从极限定义开始拆解。", timestamp="2026-05-22T10:01:00Z"),
            ],
        )
    )

    assert result.new_summary == "此前用户在学习函数基础。 本轮对话：用户提到：我总是在导数定义上卡住；助手回应：可以从极限定义开始拆解。"


def test_compress_memory_extracts_blind_spot_fact() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary=None,
            messages=[
                MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
            ],
        )
    )

    assert len(result.extracted_facts) == 1
    assert result.extracted_facts[0].content == "用户在递归概念上卡住"
    assert result.extracted_facts[0].fact_type == "blind_spot"
    assert result.extracted_facts[0].knowledge_point == "递归概念"
    assert result.extracted_facts[0].confidence == 0.8


def test_compress_memory_skips_existing_fact_content() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary=None,
            messages=[
                MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
            ],
            existing_facts=["用户在递归概念上卡住"],
        )
    )

    assert result.extracted_facts == []


def test_compress_and_persist_memory_upserts_extracted_facts() -> None:
    memory = importlib.import_module("agent_service.agents.memory")
    calls = {}

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            calls["embedded_texts"] = texts
            return [[0.1, 0.2]]

    class FakeMemoryStore:
        async def upsert_facts(self, *, user_id, conversation_id, facts, vectors):
            calls["upsert"] = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "facts": facts,
                "vectors": vectors,
            }

    result = asyncio.run(
        memory.compress_and_persist_memory(
            _build_request(
                old_summary=None,
                messages=[
                    MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
                ],
            ),
            embedding_provider=FakeEmbeddingProvider(),
            memory_store=FakeMemoryStore(),
        )
    )

    assert result.extracted_facts[0].content == "用户在递归概念上卡住"
    assert calls["embedded_texts"] == ["用户在递归概念上卡住"]
    assert calls["upsert"]["user_id"] == "user-1"
    assert calls["upsert"]["conversation_id"] == "conversation-1"
    assert calls["upsert"]["vectors"] == [[0.1, 0.2]]
    assert calls["upsert"]["facts"][0].content == "用户在递归概念上卡住"


def test_compress_and_persist_memory_skips_embedding_when_no_facts() -> None:
    memory = importlib.import_module("agent_service.agents.memory")
    calls = {"embedding": 0, "upsert": 0}

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            calls["embedding"] += 1
            return [[0.1, 0.2]]

    class FakeMemoryStore:
        async def upsert_facts(self, *, user_id, conversation_id, facts, vectors):
            calls["upsert"] += 1

    result = asyncio.run(
        memory.compress_and_persist_memory(
            _build_request(
                old_summary=None,
                messages=[
                    MemoryMessage(role="assistant", content="这里没有用户事实", timestamp="2026-05-22T10:00:00Z"),
                ],
            ),
            embedding_provider=FakeEmbeddingProvider(),
            memory_store=FakeMemoryStore(),
        )
    )

    assert result.extracted_facts == []
    assert calls == {"embedding": 0, "upsert": 0}


def test_compress_and_persist_memory_degrades_when_embedding_fails(caplog) -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    class FailingEmbeddingProvider:
        async def embed_texts(self, texts):
            raise RuntimeError("embedding unavailable")

    class FakeMemoryStore:
        async def upsert_facts(self, *, user_id, conversation_id, facts, vectors):
            raise AssertionError("upsert should not be called")

    with caplog.at_level("WARNING", logger="agent_service.agents.memory"):
        result = asyncio.run(
            memory.compress_and_persist_memory(
                _build_request(
                    old_summary=None,
                    messages=[
                        MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
                    ],
                ),
                embedding_provider=FailingEmbeddingProvider(),
                memory_store=FakeMemoryStore(),
            )
        )

    assert result.extracted_facts[0].content == "用户在递归概念上卡住"
    assert "Memory persistence failed" in caplog.text


def test_compress_and_persist_memory_degrades_when_store_init_fails(caplog, monkeypatch) -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2]]

    def failing_store_factory():
        raise RuntimeError("qdrant init failed")

    monkeypatch.setattr(memory, "QdrantUserMemoryStore", failing_store_factory)

    with caplog.at_level("WARNING", logger="agent_service.agents.memory"):
        result = asyncio.run(
            memory.compress_and_persist_memory(
                _build_request(
                    old_summary=None,
                    messages=[
                        MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
                    ],
                ),
                embedding_provider=FakeEmbeddingProvider(),
                memory_store=None,
            )
        )

    assert result.extracted_facts[0].content == "用户在递归概念上卡住"
    assert "Memory persistence failed" in caplog.text


def _build_request(
    old_summary: str | None,
    messages: list[MemoryMessage],
    existing_facts: list[str] | None = None,
) -> MemoryCompressRequest:
    return MemoryCompressRequest(
        user_id="user-1",
        conversation_id="conversation-1",
        old_summary=old_summary,
        messages_to_compress=messages,
        existing_facts=existing_facts or [],
    )
