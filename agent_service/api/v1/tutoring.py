from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service.agents.tutoring import generate_tutoring_sse_events
from agent_service.schemas.tutoring import TutoringChatRequest
from agent_service.core.ai import get_ai_providers
from agent_service.memory.tutoring_retrieval import (
    build_tutoring_retrieval_context_with_ai,
    TutoringRetrievalContext,
)
from agent_service.memory.vector_store import QdrantVectorStore
from agent_service.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tutoring")


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
    return StreamingResponse(generate_tutoring_sse_events(request), media_type="text/event-stream")


@router.post(
    "/retrieval_probe",
    tags=["Tutoring", "Probe"],
    summary="检索上下文探针 (Probe)",
    response_model=TutoringRetrievalContext,
)
async def retrieval_probe(request: TutoringChatRequest) -> TutoringRetrievalContext:
    providers = get_ai_providers()
    vector_store = None
    if getattr(providers, "embedding", None):
        try:
            vector_store = QdrantVectorStore()
        except Exception:
            logger.warning("Failed to create QdrantVectorStore in probe", exc_info=True)

    retrieval_context = await build_tutoring_retrieval_context_with_ai(
        request,
        embedding_provider=providers.embedding,
        reranker_provider=getattr(providers, "reranker", None),
        vector_store=vector_store,
    )
    return retrieval_context
