from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agentscope.rag import PDFParser, TextParser, ApproxTokenChunker, KnowledgeBase, QdrantStore, Chunk
from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_embedding_model_from_settings,
    build_reranker_model_from_settings,
)

logger = logging.getLogger(__name__)


class CatalogKnowledgeContextEmpty(ValueError):
    pass


def build_qdrant_store(settings: AgentModelSettings) -> QdrantStore:
    """实例化并返回 AgentScope QdrantStore，用于教材向量化存储。"""
    client_kwargs = {"check_compatibility": False}
    url = settings.QDRANT_URL
    path = settings.QDRANT_PATH
    api_key = getattr(settings, "QDRANT_API_KEY", None)

    return QdrantStore(
        url=url,
        path=path if not url else None,
        api_key=api_key,
        client_kwargs=client_kwargs,
    )


async def ensure_qdrant_collection_exists(store: QdrantStore, settings: AgentModelSettings) -> None:
    """确保 Qdrant collection 存在。"""
    from qdrant_client.models import Distance, VectorParams

    collection_name = settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION
    client = store.get_client()
    try:
        collections = await client.get_collections()
        names = {c.name for c in collections.collections}
        if collection_name in names:
            return
    except Exception as exc:
        logger.warning("Failed to check Qdrant collections: %s", exc)

    try:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
    except Exception as exc:
        logger.warning("Failed to create collection %s: %s", collection_name, exc)


def get_course_knowledge_base(course_id: str, settings: AgentModelSettings) -> KnowledgeBase:
    """根据 course_id 构建隔离的 KnowledgeBase 实例。"""
    embedding_model = build_embedding_model_from_settings(settings)
    vector_store = build_qdrant_store(settings)
    
    # 隔离性设计：在 KB 级别绑定 course_id 过滤
    return KnowledgeBase(
        name=f"course_kb_{course_id}",
        description=f"Knowledge base for course catalog {course_id}",
        embedding_model=embedding_model,
        vector_store=vector_store,
        collection=settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION,
        metadata_filter={"course_id": course_id},
    )


async def ingest_course_material(
    file_path: Path | str,
    course_id: str,
    settings: AgentModelSettings,
) -> int:
    """对课本教材进行高质量解析、切片，并写入对应课程的知识库。
    
    返回生成的 Chunk 数量。
    """
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Course material file not found: {path}")

    # 1. 选用对应的 Parser 进行高质量文档层级解析
    if path.suffix.lower() == ".pdf":
        parser = PDFParser()
    else:
        parser = TextParser()

    sections = await parser.parse(str(path), path.name)

    # 2. 使用语义 Token Chunker，配合 Overlap 重叠度防止上下文截断
    chunker = ApproxTokenChunker(chunk_size=512, overlap=50)
    raw_chunks = await chunker.chunk(sections)

    # 3. 构造原生 Chunk 列表并过滤空文本，在元数据中注入 course_id 以隔离多课程
    chunks: list[Chunk] = []
    for idx, raw_chunk in enumerate(raw_chunks):
        content_text = raw_chunk.content.text if hasattr(raw_chunk.content, "text") else str(raw_chunk.content)
        if not content_text.strip():
            continue
        chunks.append(
            Chunk(
                content=raw_chunk.content,
                source=path.name,
                chunk_index=idx,
                total_chunks=len(raw_chunks),
                metadata={"course_id": course_id, "filename": path.name},
            )
        )

    if not chunks:
        return 0

    # 4. 确保 Collection 存在并写入 KnowledgeBase
    kb = get_course_knowledge_base(course_id, settings)
    await ensure_qdrant_collection_exists(kb.vector_store, settings)

    # 🚀 安全分批写入逻辑：每次最多向 SiliconFlow 发送 32 个切片，防御 20015 批处理超限错误
    import uuid
    document_id = uuid.uuid4().hex
    batch_size = 32

    for i in range(0, len(chunks), batch_size):
        chunk_batch = chunks[i : i + batch_size]
        await kb.insert_document(
            chunk_batch,
            document_id=document_id,
            document_metadata={"course_id": course_id},
        )

    return len(chunks)


def _text_from_agentscope_payload(payload: dict[str, Any]) -> str:
    chunk = payload.get("chunk")
    if not isinstance(chunk, dict):
        return ""
    content = chunk.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text.strip() if isinstance(text, str) else ""


def _truncate_chunk(text: str, max_chars: int = 1200) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


async def build_catalog_kg_context(
    catalog_id: str,
    *,
    settings: AgentModelSettings | None = None,
    limit: int = 24,
    max_chars: int = 18000,
) -> str:
    """Build KG generation context from AgentScope 2.x Qdrant chunks."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    settings = settings or AgentModelSettings()
    store = build_qdrant_store(settings)
    client = store.get_client()
    records, _ = await client.scroll(
        collection_name=settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="chunk.metadata.course_id",
                    match=MatchValue(value=catalog_id),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    chunks: list[str] = []
    used_chars = 0
    for record in records:
        payload = getattr(record, "payload", None)
        if not isinstance(payload, dict):
            continue
        text = _truncate_chunk(_text_from_agentscope_payload(payload))
        if not text:
            continue
        if used_chars + len(text) > max_chars:
            remaining = max_chars - used_chars
            if remaining <= 200:
                break
            text = _truncate_chunk(text, remaining)
        chunks.append(text)
        used_chars += len(text)
        if used_chars >= max_chars:
            break

    if not chunks:
        raise CatalogKnowledgeContextEmpty(
            "No catalog knowledge chunks found for KG generation"
        )
    return "\n---\n".join(chunks)


async def retrieve_course_context(
    query: str,
    course_id: str,
    limit: int = 3,
    settings: AgentModelSettings | None = None,
) -> dict[str, Any]:
    """Agent RAG 检索工具：检索当前课程相关的课本段落，执行重排并返回引文。"""
    settings = settings or AgentModelSettings()
    kb = get_course_knowledge_base(course_id, settings)

    # 1. 使用绑定了 course_id 的 KB.search 执行向量检索
    # 限制检索上限
    raw_results = await kb.search(queries=[query], top_k=limit * 2)
    if not raw_results:
        return {"context_text": "", "citations": []}

    # 2. 提取文本，进行语义重排（Rerank）提升质量
    reranker = build_reranker_model_from_settings(settings)
    documents = [res.chunk.content.text for res in raw_results]

    if reranker and documents:
        try:
            scores = await reranker.score(query, documents)
            # 根据 Reranker 重新排序
            scored_results = sorted(
                zip(raw_results, scores, strict=True),
                key=lambda x: x[1],
                reverse=True,
            )
            # 只取前 limit 项
            filtered_results = scored_results[:limit]
        except Exception as exc:
            logger.warning("Reranking failed: %s. Falling back to vector search order.", exc)
            filtered_results = [(res, res.score or 0.0) for res in raw_results[:limit]]
    else:
        filtered_results = [(res, res.score or 0.0) for res in raw_results[:limit]]

    # 3. 组装最终检索结果和引文 citations
    context_parts: list[str] = []
    citations: list[dict[str, Any]] = []

    for idx, (res, score) in enumerate(filtered_results):
        chunk = res.chunk
        payload = chunk.metadata or {}
        filename = payload.get("filename") or chunk.source or "unknown_textbook"
        
        context_parts.append(f"[{idx+1}] File: {filename}\nContent: {chunk.content.text}\n")
        citations.append(
            {
                "citation_index": idx + 1,
                "source_file": filename,
                "content": chunk.content.text,
                "score": float(score),
            }
        )

    return {
        "context_text": "\n".join(context_parts),
        "citations": citations,
    }
