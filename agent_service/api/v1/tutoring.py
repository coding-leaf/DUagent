import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service.schemas.tutoring import DoneEvent, TutoringChatRequest


router = APIRouter(prefix="/tutoring")


async def tutoring_event_stream() -> AsyncIterator[str]:
    done_event = DoneEvent(message_id="stub-message-id")
    yield f"data: {json.dumps(done_event.model_dump(), ensure_ascii=False)}\n\n"


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
async def tutoring_chat(_: TutoringChatRequest) -> StreamingResponse:
    return StreamingResponse(tutoring_event_stream(), media_type="text/event-stream")
