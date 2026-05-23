import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service.agents.tutoring import generate_tutoring_events
from agent_service.schemas.tutoring import TutoringChatRequest


router = APIRouter(prefix="/tutoring")


async def tutoring_event_stream(request: TutoringChatRequest) -> AsyncIterator[str]:
    for event in generate_tutoring_events(request):
        yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"


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
