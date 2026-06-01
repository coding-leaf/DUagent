import asyncio
from uuid import UUID

from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
from agent_service.memory.course_knowledge_store import QdrantCourseKnowledgeStore


class FakeAsyncQdrantClient:
    def __init__(self, scroll_points=None, scroll_error: Exception | None = None) -> None:
        self.calls = []
        self._scroll_points = scroll_points or []
        self._scroll_error = scroll_error

    async def upsert(self, **kwargs):
        self.calls.append(kwargs)

    async def scroll(self, **kwargs):
        self.calls.append(kwargs)
        if self._scroll_error is not None:
            raise self._scroll_error
        return self._scroll_points, None


class FakeQdrantStore:
    def __init__(self, scroll_points=None, scroll_error: Exception | None = None) -> None:
        self.collection_name = "course_knowledge_v1_1024"
        self._client = FakeAsyncQdrantClient(scroll_points=scroll_points, scroll_error=scroll_error)
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
    assert isinstance(UUID(first_id), UUID)


def test_upsert_chunks_empty_points_no_call() -> None:
    store = FakeQdrantStore()
    course_store = QdrantCourseKnowledgeStore(store=store)

    asyncio.run(course_store.upsert_chunks(chunks=[], vectors=[]))

    assert len(store.calls) == 0


class FakeScrollPoint:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload


def test_list_ingested_source_files_returns_unique_source_files() -> None:
    store = FakeQdrantStore(
        scroll_points=[
            FakeScrollPoint({"source_file": "chapter_01.md"}),
            FakeScrollPoint({"source_file": "chapter_02.md"}),
            FakeScrollPoint({"source_file": "chapter_01.md"}),
        ]
    )
    course_store = QdrantCourseKnowledgeStore(store=store)

    ingested = asyncio.run(course_store.list_ingested_source_files("course-1"))

    assert ingested == {"chapter_01.md", "chapter_02.md"}
    assert store.calls[0]["collection_name"] == "course_knowledge_v1_1024"


def test_list_ingested_source_files_ignores_missing_source_file_payload() -> None:
    store = FakeQdrantStore(
        scroll_points=[
            FakeScrollPoint({"source_file": "chapter_01.md"}),
            FakeScrollPoint({"other_field": "value"}),
        ]
    )
    course_store = QdrantCourseKnowledgeStore(store=store)

    ingested = asyncio.run(course_store.list_ingested_source_files("course-1"))

    assert ingested == {"chapter_01.md"}


def test_list_ingested_source_files_returns_empty_when_collection_missing() -> None:
    store = FakeQdrantStore(
        scroll_error=RuntimeError("Not found: Collection `course_knowledge_v1_1024` doesn't exist!")
    )
    course_store = QdrantCourseKnowledgeStore(store=store)

    ingested = asyncio.run(course_store.list_ingested_source_files("course-1"))

    assert ingested == set()
