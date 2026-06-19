"""Pure Client API DTO conversion for tutoring conversations."""

from app.models.conversation import Conversation, Message


def message_item(message: Message) -> dict:
    return {
        "role": message.role,
        "content": message.content or "",
        "diagrams": message.diagrams or [],
        "knowledge_points": message.knowledge_points or [],
        "meta": message.meta_json or {},
        "timestamp": message.create_time.isoformat() if message.create_time else "",
    }


def conversation_item(
    conversation: Conversation,
    message_count: int,
    last_message: Message | None,
) -> dict:
    return {
        "id": conversation.id,
        "scope": conversation.scope,
        "course_id": conversation.course_id,
        "title": conversation.title,
        "last_message": (
            last_message.content[:50]
            if last_message and last_message.content
            else ""
        ),
        "message_count": message_count,
        "updated_at": (
            conversation.update_time.isoformat()
            if conversation.update_time
            else ""
        ),
    }


def conversation_detail(
    conversation: Conversation,
    messages: list[Message],
) -> dict:
    return {
        "id": conversation.id,
        "scope": conversation.scope,
        "course_id": conversation.course_id,
        "title": conversation.title,
        "messages": [message_item(message) for message in messages],
        "created_at": (
            conversation.create_time.isoformat()
            if conversation.create_time
            else ""
        ),
        "updated_at": (
            conversation.update_time.isoformat()
            if conversation.update_time
            else ""
        ),
    }
