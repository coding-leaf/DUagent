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

    retrieval_context = await _build_runtime_retrieval_context(request)
    model_response = await _build_model_response(request, retrieval_context)
    runtime_result = build_tutoring_generation_result(
        request,
        retrieval_context=retrieval_context,
        model_response=model_response,
    )
    if model_response and model_response.model_text:
        yield f"data: {json.dumps({'type': 'chunk', 'content': runtime_result.chunk_text}, ensure_ascii=False)}\n\n"

    for event in _build_runtime_events(request, runtime_result):
        yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"


async def _build_runtime_retrieval_context(request: TutoringChatRequest) -> TutoringRetrievalContext:
    providers = get_ai_providers()
    reranker_provider = getattr(providers, "reranker", None)
    try:
        if reranker_provider is None:
            return await build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=providers.embedding,
            )
        return await build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=providers.embedding,
            reranker_provider=reranker_provider,
        )
    except Exception:
        logger.warning("Tutoring retrieval failed, using fallback context", exc_info=True)
        return build_tutoring_retrieval_context(request)


async def _build_model_response(request: TutoringChatRequest, retrieval_context: TutoringRetrievalContext) -> TutoringModelResponse | None:
    providers = get_ai_providers()
    chat_provider = getattr(providers, "chat", None)
    react_response = await generate_tutoring_react_response(request, retrieval_context, chat_provider)
    if react_response is not None:
        return react_response
    return await generate_tutoring_model_response(request, retrieval_context, chat_provider)


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
