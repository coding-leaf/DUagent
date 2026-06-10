import asyncio

from agent_service.memory.kg_body_grounding import score_kg_body_grounding
from agent_service.memory.vector_store import VectorSearchResult


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(len(texts[0]))]]


class FakeVectorStore:
    def __init__(self, results_by_vector: dict[float, list[VectorSearchResult]]) -> None:
        self.results_by_vector = results_by_vector
        self.calls: list[dict] = []

    async def search_course_knowledge(self, course_id, vector, limit=5):
        self.calls.append({"course_id": course_id, "vector": list(vector), "limit": limit})
        return self.results_by_vector.get(float(vector[0]), [])


def test_scores_each_node_with_embedding_and_course_search() -> None:
    embedding = FakeEmbeddingProvider()
    nodes = [
        {"id": "n1", "name": "顺序表"},
        {"id": "n2", "name": "链表"},
    ]
    store = FakeVectorStore(
        {
            float(len("顺序表")): [
                VectorSearchResult(
                    text="顺序表是一种使用连续存储空间保存线性表元素的数据结构，支持按下标随机访问。",
                    score=0.82,
                    payload={"chunk_id": "c1", "source_file": "chapter1.md"},
                )
            ],
            float(len("链表")): [
                VectorSearchResult(
                    text="链表通过指针把节点连接起来，插入和删除时通常不需要移动大量元素。",
                    score=0.78,
                    payload={"chunk_id": "c2", "source_file": "chapter2.md"},
                )
            ],
        }
    )

    results = asyncio.run(score_kg_body_grounding("course-1", nodes, embedding, vector_store=store, limit=4))

    assert embedding.calls == [["顺序表"], ["链表"]]
    assert store.calls == [
        {"course_id": "course-1", "vector": [3.0], "limit": 4},
        {"course_id": "course-1", "vector": [2.0], "limit": 4},
    ]
    assert [result.node_id for result in results] == ["n1", "n2"]
    assert [result.node_name for result in results] == ["顺序表", "链表"]
    assert [result.supported for result in results] == [True, True]
    assert results[0].body_top1_score == 0.82
    assert results[0].chunk_id == "c1"
    assert results[0].source_file == "chapter1.md"
    assert len(results[0].preview) <= 120


def test_filters_toc_like_top_hit_and_uses_next_body_hit() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("二叉树")): [
                VectorSearchResult(
                    text="目录\n1. 树的概念\n2. 二叉树\n3. 遍历",
                    score=0.94,
                    payload={"chunk_id": "toc", "source_file": "chapter3.md"},
                ),
                VectorSearchResult(
                    text="二叉树是每个节点至多有两个子节点的树形结构，常见遍历方式包括前序、中序和后序。",
                    score=0.76,
                    payload={"chunk_id": "body", "source_file": "chapter3.md"},
                ),
            ]
        }
    )

    result = asyncio.run(score_kg_body_grounding("course-1", [{"id": "n1", "name": "二叉树"}], embedding, vector_store=store))[0]

    assert result.supported is True
    assert result.body_top1_score == 0.76
    assert result.chunk_id == "body"
    assert "目录" not in result.preview


def test_unsupported_when_no_body_candidate_or_score_below_threshold() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("图")): [
                VectorSearchResult(
                    text="索引\n图\n树\n排序",
                    score=0.91,
                    payload={"chunk_id": "index", "source_file": "index.md"},
                )
            ],
            float(len("队列")): [
                VectorSearchResult(
                    text="队列是一种先进先出的线性结构，入队发生在队尾，出队发生在队首。",
                    score=0.61,
                    payload={"chunk_id": "queue", "source_file": "chapter4.md"},
                )
            ],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [{"id": "n1", "name": "图"}, {"id": "n2", "name": "队列"}],
            embedding,
            vector_store=store,
            threshold=0.70,
        )
    )

    assert [(result.node_id, result.supported, result.body_top1_score) for result in results] == [
        ("n1", False, None),
        ("n2", False, 0.61),
    ]
    assert results[0].chunk_id is None
    assert results[0].preview == ""
    assert results[1].chunk_id == "queue"


def test_extracts_node_name_with_title_label_and_id_fallbacks() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("哈希表")): [],
            float(len("栈")): [],
            float(len("node-only")): [],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [
                {"id": "n1", "title": "哈希表"},
                {"id": "n2", "label": "栈"},
                {"id": "node-only"},
            ],
            embedding,
            vector_store=store,
        )
    )

    assert embedding.calls == [["哈希表"], ["栈"], ["node-only"]]
    assert [(result.node_id, result.node_name) for result in results] == [
        ("n1", "哈希表"),
        ("n2", "栈"),
        ("node-only", "node-only"),
    ]
