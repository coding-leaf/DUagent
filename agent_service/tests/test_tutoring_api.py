import asyncio
import json

from agent_service.api.v1.tutoring import tutoring_chat
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def test_tutoring_chat_returns_rule_based_sse_events() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="导数怎么理解？",
        user_profile=TutoringUserProfile(
            guidance_level="L1",
            knowledge_mastered=["函数"],
            knowledge_weak=["导数"],
        ),
    )

    response = asyncio.run(tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))

    assert response.media_type == "text/event-stream"
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert events[-1]["message_id"] == "msg_user-1_new"


async def _consume_response_body(body_iterator) -> str:
    chunks = []
    async for chunk in body_iterator:
        chunks.append(chunk)
    return "".join(chunks)
