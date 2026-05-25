import asyncio

from agent_service.memory.user_memory_store import QdrantUserMemoryStore
from agent_service.schemas.memory import ExtractedFact


class FakeAsyncQdrantClient:
    def __init__(self) -> None:
        self.calls = []

    async def upsert(self, **kwargs):
        self.calls.append(kwargs)


class FakeQdrantStore:
    def __init__(self) -> None:
        self.collection_name = "user_memory_v1_1024"
        self._client = FakeAsyncQdrantClient()
        self.calls = self._client.calls

    def get_client(self):
        return self._client


def test_upsert_facts_uses_configured_collection_and_payload() -> None:
    store = FakeQdrantStore()
    mem_store = QdrantUserMemoryStore(store=store)
    facts = [
        ExtractedFact(
            content="用户在递归概念上卡住",
            fact_type="blind_spot",
            knowledge_point="递归概念",
            confidence=0.8,
        )
    ]

    asyncio.run(
        mem_store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )

    assert store.calls[0]["collection_name"] == "user_memory_v1_1024"
    point = store.calls[0]["points"][0]
    assert point.payload["user_id"] == "user-1"
    assert point.payload["conversation_id"] == "conversation-1"
    assert point.payload["fact_text"] == "用户在递归概念上卡住"
    assert point.payload["fact_type"] == "blind_spot"
    assert point.payload["knowledge_point"] == "递归概念"
    assert point.payload["confidence"] == 0.8
    assert point.payload["source"] == "memory_compress"


def test_upsert_facts_generates_stable_point_ids() -> None:
    store = FakeQdrantStore()
    mem_store = QdrantUserMemoryStore(store=store)
    facts = [
        ExtractedFact(
            content="用户在递归概念上卡住",
            fact_type="blind_spot",
            knowledge_point="递归概念",
            confidence=0.8,
        )
    ]

    asyncio.run(
        mem_store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )
    asyncio.run(
        mem_store.upsert_facts(
            user_id="user-1",
            conversation_id="conversation-1",
            facts=facts,
            vectors=[[0.1, 0.2]],
        )
    )

    first_id = store.calls[0]["points"][0].id
    second_id = store.calls[1]["points"][0].id
    assert first_id == second_id
