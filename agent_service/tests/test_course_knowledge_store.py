import asyncio
from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
from agent_service.memory.course_knowledge_store import QdrantCourseKnowledgeStore


class FakeAsyncQdrantClient:
    def __init__(self) -> None:
        self.calls = []

    async def upsert(self, **kwargs):
        self.calls.append(kwargs)


class FakeQdrantStore:
    def __init__(self) -> None:
        self.collection_name = "course_knowledge_v1_1024"
        self._client = FakeAsyncQdrantClient()
        self.calls = self._client.calls

    def get_client(self):
        return self._client


def test_upsert_chunks_uses_configured_collection_and_payload() -> None:
    store = FakeQdrantStore()
    course_store = QdrantCourseKnowledgeStore(store=store)

    asyncio.run(
        course_store.upsert_chunks(
            chunks=[
                CourseKnowledgeChunk(
                    course_id="course-1",
                    source_file="chapter_01.md",
                    source_type="course_material",
                    content="链式法则用于复合函数求导",
                    doc_id="doc-1",
                    chunk_id=0,
                    total_chunks=1,
                )
            ],
            vectors=[[0.1, 0.2]],
        )
    )

    assert store.calls[0]["collection_name"] == "course_knowledge_v1_1024"
    point = store.calls[0]["points"][0]
    assert point.vector == [0.1, 0.2]
    assert point.payload["course_id"] == "course-1"
    assert point.payload["source_file"] == "chapter_01.md"
    assert point.payload["source_type"] == "course_material"
    assert point.payload["content"] == "链式法则用于复合函数求导"
    assert point.payload["doc_id"] == "doc-1"
    assert point.payload["chunk_id"] == 0
    assert point.payload["total_chunks"] == 1


def test_upsert_chunks_generates_stable_point_ids() -> None:
    store = FakeQdrantStore()
    course_store = QdrantCourseKnowledgeStore(store=store)
    chunks = [
        CourseKnowledgeChunk(
            course_id="course-1",
            source_file="chapter_01.md",
            source_type="course_material",
            content="链式法则用于复合函数求导",
            doc_id="doc-1",
            chunk_id=0,
            total_chunks=1,
        )
    ]

    asyncio.run(course_store.upsert_chunks(chunks=chunks, vectors=[[0.1, 0.2]]))
    asyncio.run(course_store.upsert_chunks(chunks=chunks, vectors=[[0.1, 0.2]]))

    first_id = store.calls[0]["points"][0].id
    second_id = store.calls[1]["points"][0].id
    assert first_id == second_id


def test_upsert_chunks_empty_points_no_call() -> None:
    store = FakeQdrantStore()
    course_store = QdrantCourseKnowledgeStore(store=store)

    asyncio.run(course_store.upsert_chunks(chunks=[], vectors=[]))

    assert len(store.calls) == 0
