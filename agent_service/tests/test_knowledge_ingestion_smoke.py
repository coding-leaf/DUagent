"""Knowledge ingestion 端到端闭环 smoke：
课程资料 → chunk → embedding → Qdrant → search → 可用于 RAG context。
"""

import asyncio
from pathlib import Path


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeQdrantClient:
    def __init__(self) -> None:
        self._points: list[dict] = []

    async def scroll(self, collection_name, scroll_filter=None, with_payload=None, limit=256, offset=None):
        source_files = set()
        for point in self._points:
            payload = point.get("payload", {})
            source_file = payload.get("source_file")
            if isinstance(source_file, str):
                source_files.add(source_file)
        result = []
        for sf in source_files:
            result.append(type("_P", (), {"payload": {"source_file": sf}})())
        return result, None

    async def upsert(self, collection_name, points, wait=True):
        for p in points:
            self._points.append({"id": p.id, "vector": p.vector, "payload": p.payload})

    async def query_points(self, collection_name, query, query_filter=None, limit=5, with_payload=True):
        results = []
        for p in self._points:
            payload = p.get("payload", {})
            results.append(type("_R", (), {
                "text": payload.get("content", ""),
                "score": 0.9,
                "payload": payload,
            })())
        return results


class FakeQdrantStore:
    def __init__(self, client: FakeQdrantClient | None = None) -> None:
        self._client = client or FakeQdrantClient()

    def get_client(self):
        return self._client

    async def list_ingested_source_files(self, course_id: str) -> set[str]:
        source_files = set()
        for point in self._client._points:
            payload = point.get("payload", {})
            if payload.get("course_id") == course_id:
                sf = payload.get("source_file")
                if isinstance(sf, str):
                    source_files.add(sf)
        return source_files

    async def upsert_chunks(self, *, chunks, vectors):
        from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
        for chunk, vector in zip(chunks, vectors):
            self._client._points.append({
                "id": f"{chunk.course_id}::{chunk.source_file}",
                "vector": list(vector),
                "payload": {
                    "course_id": chunk.course_id,
                    "source_file": chunk.source_file,
                    "content": chunk.content,
                },
            })

    @property
    def collection_name(self):
        return "course_knowledge_v1_1024"


def test_ingestion_retrieval_e2e_smoke(tmp_path: Path) -> None:
    from agent_service.tools.ingest_knowledge import ingest_course_knowledge

    course_dir = tmp_path / "test-course"
    course_dir.mkdir()
    (course_dir / "chapter1.md").write_text("# 一次函数\n一次函数的标准形式是 y = kx + b，其中 k 为斜率，b 为截距。")

    embedding = FakeEmbeddingProvider()
    qdrant_client = FakeQdrantClient()
    qdrant_store = FakeQdrantStore(client=qdrant_client)

    result = asyncio.run(ingest_course_knowledge(
        course_dir,
        embedding_provider=embedding,
        store=qdrant_store,
    ))

    assert result.chunk_count > 0
    assert result.course_id == "test-course"
    assert len(embedding.calls) == 1

    # 检索验证
    retrieved = asyncio.run(qdrant_client.query_points(
        collection_name="course_knowledge_v1_1024",
        query=[0.1, 0.2, 0.3],
    ))

    assert len(retrieved) > 0
    content_found = any("一次函数" in r.text for r in retrieved)
    assert content_found

    # 验证可用于 RAG context 拼接
    rag_context = "\n---\n".join(r.text for r in retrieved if r.text)
    assert "y = kx + b" in rag_context
    assert "斜率" in rag_context


def test_ingestion_is_idempotent(tmp_path: Path) -> None:
    from agent_service.tools.ingest_knowledge import ingest_course_knowledge

    course_dir = tmp_path / "test-course-2"
    course_dir.mkdir()
    (course_dir / "note.md").write_text("# 导数\n导数是函数在某点的变化率。")

    qdrant_client = FakeQdrantClient()
    qdrant_store = FakeQdrantStore(client=qdrant_client)

    result1 = asyncio.run(ingest_course_knowledge(
        course_dir,
        embedding_provider=FakeEmbeddingProvider(),
        store=qdrant_store,
    ))
    assert result1.chunk_count > 0

    result2 = asyncio.run(ingest_course_knowledge(
        course_dir,
        embedding_provider=FakeEmbeddingProvider(),
        store=qdrant_store,
    ))
    assert result2.chunk_count == 0


def test_ingestion_batches_embedding_requests(tmp_path: Path) -> None:
    from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
    from agent_service.tools.ingest_knowledge import ingest_course_knowledge

    async def load_many_chunks(root, ingested_files=None):
        return [
            CourseKnowledgeChunk(
                course_id=root.name,
                source_file=f"chunk-{index}.md",
                source_type="course_material",
                content=f"第 {index} 个知识切片",
                doc_id="doc-1",
                chunk_id=index,
                total_chunks=65,
            )
            for index in range(65)
        ]

    course_dir = tmp_path / "batch-course"
    course_dir.mkdir()
    embedding = FakeEmbeddingProvider()
    qdrant_store = FakeQdrantStore(client=FakeQdrantClient())

    result = asyncio.run(ingest_course_knowledge(
        course_dir,
        embedding_provider=embedding,
        store=qdrant_store,
        chunk_loader=load_many_chunks,
    ))

    assert result.chunk_count == 65
    assert [len(call) for call in embedding.calls] == [64, 1]


def test_retrieval_results_format_suitable_for_rag() -> None:
    from agent_service.memory.vector_store import VectorSearchResult

    results = [
        VectorSearchResult(text="一次函数的标准形式是 y = kx + b。", score=0.95, payload={"content": "一次函数的标准形式是 y = kx + b。"}),
        VectorSearchResult(text="k 为斜率，b 为截距。", score=0.90, payload={"content": "k 为斜率，b 为截距。"}),
        VectorSearchResult(text="", score=0.80, payload={}),
    ]

    chunks = [r.text for r in results if r.text]
    assert len(chunks) == 2

    context = "\n---\n".join(chunks)
    assert "y = kx + b" in context
    assert "---" in context
    assert len(context) > 20
