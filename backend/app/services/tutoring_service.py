"""Tutoring conversation and message lifecycle service."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message


class ConversationNotFoundError(Exception):
    """The requested conversation is missing or not owned by the user."""


class EditConversationRequiredError(Exception):
    """Edit requires an existing conversation ID."""


class RegenerateConversationRequiredError(Exception):
    """Regenerate requires an existing conversation ID."""


class EditUserMessageRequiredError(Exception):
    """Edit requires an existing user message."""


class RegenerateUserMessageRequiredError(Exception):
    """Regenerate requires an existing user message."""


@dataclass(frozen=True, slots=True)
class PreparedTutoringTurn:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    message: str
    scope: str
    course_id: str | None


def message_order_key(message: Message):
    """Keep user before assistant when database timestamps have equal precision."""
    role_rank = 0 if message.role == "user" else 1
    return (
        message.create_time or datetime.min,
        message.update_time or datetime.min,
        role_rank,
    )


class TutoringService:
    """Manage short tutoring DB transactions without calling Agent Service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _owned_conversation(
        self,
        user_id: str,
        conversation_id: str,
        *,
        for_update: bool,
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted == False,
        )
        if for_update:
            statement = statement.with_for_update()
        conversation = (await self.db.execute(statement)).scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError
        return conversation

    async def _last_messages(
        self,
        conversation_id: str,
    ) -> tuple[Message | None, Message | None]:
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.is_deleted == False,
            )
            .order_by(Message.create_time.desc(), Message.update_time.desc())
            .limit(20)
        )
        messages = list(result.scalars().all())
        messages.sort(key=message_order_key, reverse=True)
        last_user = next((item for item in messages if item.role == "user"), None)
        last_assistant = next(
            (item for item in messages if item.role == "assistant"),
            None,
        )
        return last_user, last_assistant

    async def _empty_assistant(
        self,
        conversation_id: str,
        scope: str,
        course_id: str | None,
    ) -> Message:
        assistant = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            meta_json={"scope": scope, "course_id": course_id},
        )
        self.db.add(assistant)
        await self.db.flush()
        return assistant

    @staticmethod
    def _prepared_turn(
        conversation: Conversation,
        user_message: Message,
        assistant_message: Message,
        message: str,
        scope: str,
        course_id: str | None,
    ) -> PreparedTutoringTurn:
        return PreparedTutoringTurn(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            message=message,
            scope=scope,
            course_id=course_id,
        )

    async def prepare_chat_turn(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        message: str,
        scope: str,
        course_id: str | None,
    ) -> PreparedTutoringTurn:
        if conversation_id:
            conversation = await self._owned_conversation(
                user_id,
                conversation_id,
                for_update=True,
            )
        else:
            title = message[:50] + ("..." if len(message) > 50 else "")
            conversation = Conversation(
                user_id=user_id,
                scope=scope,
                course_id=course_id,
                title=title,
            )
            self.db.add(conversation)
            await self.db.flush()

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=message,
            meta_json={"scope": scope, "course_id": course_id},
        )
        self.db.add(user_message)
        await self.db.flush()
        assistant = await self._empty_assistant(
            conversation.id,
            scope,
            course_id,
        )
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return self._prepared_turn(
            conversation,
            user_message,
            assistant,
            message,
            scope,
            course_id,
        )

    async def prepare_edit_turn(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        message: str,
        scope: str,
        course_id: str | None,
    ) -> PreparedTutoringTurn:
        if not conversation_id:
            raise EditConversationRequiredError
        conversation = await self._owned_conversation(
            user_id,
            conversation_id,
            for_update=True,
        )
        last_user, last_assistant = await self._last_messages(conversation.id)
        if last_user is None:
            raise EditUserMessageRequiredError

        last_user.content = message
        if last_assistant is None:
            last_assistant = await self._empty_assistant(
                conversation.id,
                scope,
                course_id,
            )
        else:
            last_assistant.content = ""
            last_assistant.diagrams = None
            last_assistant.knowledge_points = None
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return self._prepared_turn(
            conversation,
            last_user,
            last_assistant,
            message,
            scope,
            course_id,
        )

    async def prepare_regenerate_turn(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        message: str,
        scope: str,
        course_id: str | None,
    ) -> PreparedTutoringTurn:
        if not conversation_id:
            raise RegenerateConversationRequiredError
        conversation = await self._owned_conversation(
            user_id,
            conversation_id,
            for_update=True,
        )
        last_user, last_assistant = await self._last_messages(conversation.id)
        if last_user is None:
            raise RegenerateUserMessageRequiredError

        if last_assistant is None:
            last_assistant = await self._empty_assistant(
                conversation.id,
                scope,
                course_id,
            )
        else:
            last_assistant.content = ""
            last_assistant.diagrams = None
            last_assistant.knowledge_points = None
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return self._prepared_turn(
            conversation,
            last_user,
            last_assistant,
            message,
            scope,
            course_id,
        )
