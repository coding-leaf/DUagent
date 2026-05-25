import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service.agents.tutoring import (
    TutoringModelResponse,
    build_tutoring_generation_result,
    generate_tutoring_model_response,
)
from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
from agent_service.core.ai import get_ai_providers
from agent_service.core.logging import get_logger
from agent_service.memory.vector_store import QdrantVectorStore

logger = get_logger(__name__)
from agent_service.memory.tutoring_retrieval import (
    TutoringRetrievalContext,
    build_tutoring_retrieval_context,
    build_tutoring_retrieval_context_with_ai,
)
from agent_service.schemas.tutoring import (
    DoneEvent,
    KnowledgePointsEvent,
    SuggestionEvent,
    TutoringChatRequest,
)


router = APIRouter(prefix="/tutoring")


async def tutoring_event_stream(request: TutoringChatRequest) -> AsyncIterator[str]:
    fallback_result = build_tutoring_generation_result(request)
    yield f"data: {json.dumps({'type': 'chunk', 'content': fallback_result.chunk_text}, ensure_ascii=False)}\n\n"

    providers = get_ai_providers()
    embedding = getattr(providers, "embedding", None)
    vector_store = _build_shared_vector_store(embedding)
    retrieval_context = await _build_runtime_retrieval_context(
        request, providers, vector_store=vector_store
    )
    model_response = await _build_model_response(
        request, retrieval_context, providers, vector_store=vector_store
    )
    runtime_result = build_tutoring_generation_result(
        request,
        retrieval_context=retrieval_context,
        model_response=model_response,
    )
    if model_response and model_response.model_text:
        yield f"data: {json.dumps({'type': 'chunk', 'content': runtime_result.chunk_text}, ensure_ascii=False)}\n\n"

    for event in _build_runtime_events(request, runtime_result):
        yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"


async def _build_runtime_retrieval_context(request, providers, *, vector_store=None) -> TutoringRetrievalContext:
    reranker_provider = getattr(providers, "reranker", None)
    try:
        if reranker_provider is None:
            return await build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=providers.embedding,
                vector_store=vector_store,
            )
        return await build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=providers.embedding,
            reranker_provider=reranker_provider,
            vector_store=vector_store,
        )
    except Exception:
        logger.warning("Tutoring retrieval failed, using fallback context", exc_info=True)
        return build_tutoring_retrieval_context(request)


async def _build_model_response(request, retrieval_context, providers, *, vector_store=None) -> TutoringModelResponse | None:
    chat_provider = getattr(providers, "chat", None)
    embedding = getattr(providers, "embedding", None)
    react_response = await generate_tutoring_react_response(
        request, retrieval_context, chat_provider,
        embedding_provider=embedding,
        vector_store=vector_store,
    )
    if react_response is not None:
        return react_response
    return await generate_tutoring_model_response(request, retrieval_context, chat_provider)


def _build_shared_vector_store(embedding_provider) -> QdrantVectorStore | None:
    """请求生命周期内创建一次 QdrantVectorStore，避免多次 new 导致文件锁冲突。"""
    if embedding_provider is None:
        return None
    try:
        return QdrantVectorStore()
    except Exception:
        logger.warning("Failed to create shared QdrantVectorStore", exc_info=True)
        return None


def _build_runtime_events(request: TutoringChatRequest, result):
    return [
        KnowledgePointsEvent(knowledge_points=result.knowledge_points),
        SuggestionEvent(
            suggestion=result.suggestion_text,
            suggested_exercises=result.suggested_exercises,
        ),
        DoneEvent(
            message_id=f"msg_{request.user_id}_{request.conversation_id or 'new'}",
            knowledge_points_used=result.knowledge_points,
            suggested_exercises=result.suggested_exercises,
        ),
    ]


@router.post(
    "/chat",
    tags=["Tutoring"],
    summary="智能辅导对话",
    responses={
        200: {
            "description": "SSE 事件流",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "description": "事件类型: chunk / diagram / knowledge_points / suggestion / done",
                    }
                }
            },
        }
    },
)
async def tutoring_chat(request: TutoringChatRequest) -> StreamingResponse:
    return StreamingResponse(tutoring_event_stream(request), media_type="text/event-stream")
