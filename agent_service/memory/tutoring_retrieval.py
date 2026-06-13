from typing import Any

from pydantic import BaseModel, Field, field_validator

from agent_service.core.ai import EmbeddingProvider, RerankerProvider
from agent_service.core.logging import get_logger
from agent_service.memory.vector_store import QdrantVectorStore
from agent_service.schemas.tutoring import KnowledgePoint, TutoringChatRequest

logger = get_logger(__name__)


class TutoringRetrievalContext(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str | None = Field(None, description="课程 ID")
    query_text: str = Field(..., description="用于检索长期记忆和课程知识的查询文本")
    include_course_knowledge: bool = Field(..., description="是否检索课程知识库")
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list, description="检索或画像命中的知识点")
    user_memory_facts: list[str] = Field(default_factory=list, description="用户长期记忆事实")
    course_knowledge_chunks: list[str] = Field(default_factory=list, description="课程知识库切片")
    matched_kg_nodes: list[dict] = Field(default_factory=list, description="匹配的 KG 节点列表")
    retrieval_debug: dict | None = Field(None, description="仅供 probe/debug 使用，不保证前端展示，绝不暴露至 Client API/SSE 响应流中")

    @field_validator("knowledge_points", mode="before")
    @classmethod
    def normalize_knowledge_points(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        return [KnowledgePoint(name=item) if isinstance(item, str) else item for item in value]


def build_tutoring_retrieval_context(request: TutoringChatRequest) -> TutoringRetrievalContext:
    """构建智能辅导检索上下文，输入对话请求，输出可被 Agent 编排层消费的上下文。"""
    include_course_knowledge = request.scope == "course"
    return TutoringRetrievalContext(
        user_id=request.user_id,
        course_id=request.course_id if include_course_knowledge else None,
        query_text=request.message,
        include_course_knowledge=include_course_knowledge,
        knowledge_points=_profile_knowledge_points(request),
        user_memory_facts=[],
        course_knowledge_chunks=[],
        matched_kg_nodes=[],
    )


async def build_tutoring_retrieval_context_with_ai(
    request: TutoringChatRequest,
    embedding_provider: EmbeddingProvider,
    reranker_provider: RerankerProvider | None = None,
    vector_store: QdrantVectorStore | None = None,
    limit: int = 3,
) -> TutoringRetrievalContext:
    """使用 embedding 和 Qdrant 构建 tutoring 检索上下文，失败时返回规则版空检索上下文。"""
    context = build_tutoring_retrieval_context(request)
    try:
        vectors = await embedding_provider.embed_texts([request.message])
        query_vector = vectors[0] if vectors else []
        store = vector_store or QdrantVectorStore()
        user_results = await store.search_user_memory(request.user_id, query_vector, limit=limit)
    except Exception as exc:
        logger.warning("Tutoring retrieval failed: user_id=%s error=%s", request.user_id, exc)
        return context

    course_results = []
    if context.include_course_knowledge and context.course_id:
        try:
            course_results = await store.search_course_knowledge(context.course_id, query_vector, limit=limit)
        except Exception as exc:
            logger.warning(
                "Tutoring course knowledge retrieval failed: user_id=%s course_id=%s error=%s",
                request.user_id,
                context.course_id,
                exc,
            )

    user_texts = [result.text for result in user_results if result.text]
    course_texts = [result.text for result in course_results if result.text]

    matched_nodes = []
    if request.active_kg_nodes:
        matched_nodes = await _rerank_kg_nodes(
            request.message,
            request.active_kg_nodes,
            reranker_provider,
            limit=limit,
        )

    try:
        user_texts = await _rerank_texts(request.message, user_texts, reranker_provider)
        course_texts = await _rerank_texts(request.message, course_texts, reranker_provider)
    except Exception as exc:
        logger.warning("Tutoring rerank failed: user_id=%s error=%s", request.user_id, exc)

    return context.model_copy(
        update={
            "user_memory_facts": user_texts,
            "course_knowledge_chunks": course_texts,
            "matched_kg_nodes": matched_nodes,
        }
    )


def _profile_knowledge_points(request: TutoringChatRequest) -> list[KnowledgePoint]:
    weak_points = request.user_profile.knowledge_weak
    mastered_points = request.user_profile.knowledge_mastered
    names = weak_points or mastered_points or []
    mastery = 40.0 if weak_points else 70.0 if mastered_points else None
    return [
        KnowledgePoint(
            name=name,
            chapter=request.course_id if request.scope == "course" else None,
            mastery=mastery,
        )
        for name in names[:3]
        if name
    ]


async def _rerank_texts(
    query: str,
    documents: list[str],
    reranker_provider: RerankerProvider | None,
) -> list[str]:
    if reranker_provider is None or len(documents) <= 1:
        return documents
    scores = await reranker_provider.score(query, documents)
    ranked = sorted(zip(documents, scores, strict=True), key=lambda item: item[1], reverse=True)
    return [document for document, _ in ranked]


async def _rerank_kg_nodes(
    query: str,
    nodes: list[dict],
    reranker_provider: RerankerProvider | None,
    limit: int = 3,
) -> list[dict]:
    if not nodes:
        return []
    if reranker_provider is None or len(nodes) <= 1:
        return nodes[:limit]
    
    # Extract text representation for reranking
    documents = [node.get("name", "") for node in nodes]
    try:
        scores = await reranker_provider.score(query, documents)
        ranked = sorted(zip(nodes, scores, strict=True), key=lambda item: item[1], reverse=True)
        return [node for node, _ in ranked][:limit]
    except Exception as exc:
        logger.warning("Tutoring KG nodes rerank failed: error=%s", exc)
        return nodes[:limit]
