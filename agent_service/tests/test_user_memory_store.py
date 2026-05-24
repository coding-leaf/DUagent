from agent_service.memory.user_memory_store import QdrantUserMemoryStore
from agent_service.schemas.memory import ExtractedFact


class FakeQdrantClient:
    def __init__(self) -> None:
        self.calls = []

    def upsert(self, **kwargs):
        self.calls.append(kwargs)


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def test_upsert_facts_uses_configured_collection_and_payload(monkeypatch) -> None:
    import agent_service.memory.user_memory_store as store_module

    monkeypatch.setattr(
        store_module,
        "settings",
        type("FakeSettings", (), {"QDRANT_USER_MEMORY_COLLECTION": "user_memory_v1_1024"})(),
    )
    monkeypatch.setattr(store_module.asyncio, "to_thread", _run_immediately)

    client = FakeQdrantClient()
    store = QdrantUserMemoryStore(client=client)
    facts = [
        ExtractedFact(
            content="用户在递归概念上卡住",
            fact_type="blind_spot",
            knowledge_point="递归概念",
            confidence=0.8,
        )
    ]

    import asyncio

    asyncio.run(
        store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )

    assert client.calls[0]["collection_name"] == "user_memory_v1_1024"
    point = client.calls[0]["points"][0]
    assert point.payload["user_id"] == "user-1"
    assert point.payload["conversation_id"] == "conversation-1"
    assert point.payload["fact_text"] == "用户在递归概念上卡住"
    assert point.payload["fact_type"] == "blind_spot"
    assert point.payload["knowledge_point"] == "递归概念"
    assert point.payload["confidence"] == 0.8
    assert point.payload["source"] == "memory_compress"


def test_upsert_facts_generates_stable_point_ids(monkeypatch) -> None:
    import asyncio
    import agent_service.memory.user_memory_store as store_module

    monkeypatch.setattr(store_module.asyncio, "to_thread", _run_immediately)
    client = FakeQdrantClient()
    store = QdrantUserMemoryStore(client=client)
    facts = [
        ExtractedFact(
            content="用户在递归概念上卡住",
            fact_type="blind_spot",
            knowledge_point="递归概念",
            confidence=0.8,
        )
    ]

    asyncio.run(
        store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )
    asyncio.run(
        store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )

    first_id = client.calls[0]["points"][0].id
    second_id = client.calls[1]["points"][0].id
    assert first_id == second_id


def test_upsert_facts_uses_to_thread_for_sync_client(monkeypatch) -> None:
    import asyncio
    import agent_service.memory.user_memory_store as store_module

    calls = {}

    async def fake_to_thread(func, *args, **kwargs):
        calls["func"] = func
        calls["args"] = args
        calls["kwargs"] = kwargs
        return func(*args, **kwargs)

    monkeypatch.setattr(store_module.asyncio, "to_thread", fake_to_thread)

    client = FakeQdrantClient()
    store = QdrantUserMemoryStore(client=client)
    facts = [
        ExtractedFact(
            content="用户在递归概念上卡住",
            fact_type="blind_spot",
            knowledge_point="递归概念",
            confidence=0.8,
        )
    ]

    asyncio.run(
        store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )

    assert calls["func"] == client.upsert
    assert client.calls[0]["collection_name"] == store_module.settings.QDRANT_USER_MEMORY_COLLECTION
