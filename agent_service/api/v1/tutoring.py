from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service.agents.tutoring import generate_tutoring_sse_events
from agent_service.schemas.tutoring import TutoringChatRequest


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
async def tutoring_chat(request: TutoringChatRequest, _providers=None) -> StreamingResponse:
    return StreamingResponse(generate_tutoring_sse_events(request, providers=_providers), media_type="text/event-stream")
