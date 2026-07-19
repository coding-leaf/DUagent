from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agentscope.rag import Chunk, VectorSearchResult
from agent_service_v2.tools.rag import (
    build_catalog_kg_context,
    ingest_course_material,
    retrieve_course_context,
)
from agent_service_v2.agents.model_provider import AgentModelSettings


def test_retrieve_course_context_with_mocked_kb_and_rerank() -> None:
    settings = AgentModelSettings()
    
    # Mock VectorSearchResult
    from agentscope.message import TextBlock
    
    mock_res1 = MagicMock(spec=VectorSearchResult)
    mock_res1.chunk = Chunk(
        content=TextBlock(text="Python variable scopes include local, global, nonlocal."),
        source="python_textbook.pdf",
        chunk_index=0,
        total_chunks=2,
        metadata={"filename": "python_textbook.pdf", "course_id": "c1"},
    )
    mock_res1.score = 0.85

    mock_res2 = MagicMock(spec=VectorSearchResult)
    mock_res2.chunk = Chunk(
        content=TextBlock(text="Global variables can be modified inside functions using global keyword."),
        source="python_textbook.pdf",
        chunk_index=1,
        total_chunks=2,
        metadata={"filename": "python_textbook.pdf", "course_id": "c1"},
    )
    mock_res2.score = 0.70

    # Mock KnowledgeBase
    mock_kb = MagicMock()
    mock_kb.search = AsyncMock(return_value=[mock_res1, mock_res2])

    # Mock Reranker
    mock_reranker = AsyncMock()
    # 模拟重排得分：颠倒两个文档的排序，使第二个文档置顶
    mock_reranker.score.return_value = [0.1, 0.9]

    with (
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("agent_service_v2.tools.rag.build_reranker_model_from_settings", return_value=mock_reranker),
    ):
        result = asyncio.run(
            retrieve_course_context(
                query="how to modify global variables",
                course_id="c1",
                limit=2,
                settings=settings,
            )
        )

        assert "context_text" in result
        assert result["outcome"] == "success"
        assert "sources" in result
        citations = result["sources"]
        
        # 验证返回 2 条引文
        assert len(citations) == 2
        
        # 验证 Reranker 置顶了第二个文档
        assert citations[0]["snippet"] == "Global variables can be modified inside functions using global keyword."
        assert citations[0]["score"] == 0.9
        
        # 验证第一个文档排在第二位
        assert citations[1]["snippet"] == "Python variable scopes include local, global, nonlocal."
        assert citations[1]["score"] == 0.1


def test_ingest_course_material_pdf_parsing_flow() -> None:
    settings = AgentModelSettings()
    
    # Mock Parser & Chunker outputs
    mock_section = MagicMock()
    
    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(return_value=[mock_section])
    
    from agentscope.message import TextBlock
    mock_chunk1 = MagicMock()
    mock_chunk1.content = TextBlock(text="Section 1: basic python syntax")
    mock_chunk2 = MagicMock()
    mock_chunk2.content = TextBlock(text="Section 2: flow control structures")
    
    mock_chunker = MagicMock()
    mock_chunker.chunk = AsyncMock(return_value=[mock_chunk1, mock_chunk2])
    
    # Mock KnowledgeBase and Store
    mock_kb = MagicMock()
    mock_kb.insert_document = AsyncMock(return_value="doc_123")
    
    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.ApproxTokenChunker", return_value=mock_chunker),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("agent_service_v2.tools.rag.ensure_qdrant_collection_exists", new_callable=AsyncMock),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        count = asyncio.run(
            ingest_course_material(
                file_path="/fake/storage/course_catalogs/python-intro.pdf",
                course_id="c_python",
                settings=settings,
            )
        )
        
        assert count == 2
        mock_parser.parse.assert_called_once_with("/fake/storage/course_catalogs/python-intro.pdf", "python-intro.pdf")
        mock_kb.insert_document.assert_called_once()


def test_build_catalog_kg_context_reads_agentscope_qdrant_payload() -> None:
    settings = AgentModelSettings()

    point_a = MagicMock()
    point_a.payload = {
        "document_id": "doc-a",
        "chunk": {
            "content": {"type": "text", "text": "指针保存变量地址。"},
            "metadata": {"course_id": "catalog-1"},
        },
    }
    point_b = MagicMock()
    point_b.payload = {
        "document_id": "doc-b",
        "chunk": {
            "content": {"type": "text", "text": "数组是一组连续元素。"},
            "metadata": {"course_id": "catalog-1"},
        },
    }

    mock_client = MagicMock()
    mock_client.scroll = AsyncMock(return_value=([point_a, point_b], None))
    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    with patch("agent_service_v2.tools.rag.build_qdrant_store", return_value=mock_store):
        context = asyncio.run(
            build_catalog_kg_context("catalog-1", settings=settings)
        )

    assert context == "指针保存变量地址。\n---\n数组是一组连续元素。"
    scroll_filter = mock_client.scroll.await_args.kwargs["scroll_filter"]
    condition = scroll_filter.must[0]
    assert condition.key == "chunk.metadata.course_id"
    assert condition.match.value == "catalog-1"
