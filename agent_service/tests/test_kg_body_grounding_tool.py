import asyncio
import json

import pytest

from agent_service.memory.kg_body_grounding import KgBodyGroundingResult
from agent_service.tools import kg_body_grounding as tool


class FakeEmbeddingProvider:
    async def embed_texts(self, texts):
        return [[float(len(texts[0]))]]


class FakeVectorStore:
    async def search_course_knowledge(self, course_id, vector, limit=5):
        return []


def test_load_nodes_from_graph_object(tmp_path) -> None:
    kg_file = tmp_path / "kg.json"
    kg_file.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "n1", "name": "顺序表"},
                    {"id": "n2", "name": "链表"},
                ],
                "edges": [{"from": "n1", "to": "n2"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert tool.load_nodes(kg_file) == [
        {"id": "n1", "name": "顺序表"},
        {"id": "n2", "name": "链表"},
    ]


def test_load_nodes_from_plain_node_list(tmp_path) -> None:
    kg_file = tmp_path / "nodes.json"
    kg_file.write_text(
        json.dumps([{"id": "n1", "name": "栈"}], ensure_ascii=False),
        encoding="utf-8",
    )

    assert tool.load_nodes(kg_file) == [{"id": "n1", "name": "栈"}]


def test_build_grounding_payload_serializes_results() -> None:
    payload = tool.build_grounding_payload(
        course_id="course-1",
        threshold=0.7,
        limit=5,
        results=[
            KgBodyGroundingResult(
                node_id="n1",
                node_name="队列",
                body_top1_score=0.81,
                chunk_id="chunk-1",
                source_file="chapter.md",
                preview="队列是一种先进先出的线性结构。",
                supported=True,
            )
        ],
    )

    assert payload == {
        "course_id": "course-1",
        "threshold": 0.7,
        "limit": 5,
        "results": [
            {
                "node_id": "n1",
                "node_name": "队列",
                "body_top1_score": 0.81,
                "chunk_id": "chunk-1",
                "source_file": "chapter.md",
                "preview": "队列是一种先进先出的线性结构。",
                "supported": True,
            }
        ],
    }


def test_run_grounding_writes_json_output(tmp_path) -> None:
    kg_file = tmp_path / "kg.json"
    output_file = tmp_path / "grounding.json"
    kg_file.write_text(
        json.dumps({"nodes": [{"id": "n1", "name": "哈希表"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    class FakeProviders:
        embedding = FakeEmbeddingProvider()

    async def fake_score_kg_body_grounding(
        course_id,
        nodes,
        embedding_provider,
        vector_store=None,
        *,
        limit=5,
        threshold=0.7,
        preview_chars=120,
    ):
        assert course_id == "course-1"
        assert nodes == [{"id": "n1", "name": "哈希表"}]
        assert isinstance(embedding_provider, FakeEmbeddingProvider)
        assert vector_store is None
        assert limit == 3
        assert threshold == 0.75
        assert preview_chars == 80
        return [
            KgBodyGroundingResult(
                node_id="n1",
                node_name="哈希表",
                body_top1_score=0.76,
                chunk_id="chunk-hash",
                source_file="hash.md",
                preview="哈希表通过散列函数定位桶。",
                supported=True,
            )
        ]

    result = asyncio.run(
        tool.run_grounding(
            course_id="course-1",
            kg_file=kg_file,
            output_file=output_file,
            threshold=0.75,
            limit=3,
            preview_chars=80,
            provider_factory=lambda: FakeProviders(),
            scorer=fake_score_kg_body_grounding,
        )
    )

    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert result == saved
    assert saved["results"][0]["node_id"] == "n1"
    assert saved["results"][0]["supported"] is True


def test_run_grounding_requires_embedding_provider(tmp_path) -> None:
    kg_file = tmp_path / "kg.json"
    kg_file.write_text(json.dumps({"nodes": [{"id": "n1"}]}), encoding="utf-8")

    class FakeProviders:
        embedding = None

    with pytest.raises(RuntimeError, match="embedding provider"):
        asyncio.run(
            tool.run_grounding(
                course_id="course-1",
                kg_file=kg_file,
                provider_factory=lambda: FakeProviders(),
            )
        )
