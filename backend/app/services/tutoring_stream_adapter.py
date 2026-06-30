"""Adapt Agent tutoring SSE events to the Client API boundary."""

import codecs
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Awaitable, Callable

from sqlalchemy import update

from app.db.session import async_session_factory
from app.models.conversation import Conversation, Message
from app.services.agent_client import AgentServiceError, agent_client

logger = logging.getLogger(__name__)

StreamSSE = Callable[[str, dict], AsyncIterator[bytes]]
PersistResult = Callable[
    [str, str, str, list, list],
    Awaitable[None],
]


@dataclass(slots=True)
class StreamState:
    conversation_id: str
    assistant_message_id: str
    chunks: list[str] = field(default_factory=list)
    diagrams: list = field(default_factory=list)
    knowledge_points: list = field(default_factory=list)
    done_sent: bool = False


async def persist_tutoring_result(
    assistant_message_id: str,
    conversation_id: str,
    content: str,
    diagrams: list,
    knowledge_points: list,
) -> None:
    """Persist the accumulated stream through a short independent session."""
    async with async_session_factory() as db:
        await db.execute(
            update(Message)
            .where(Message.id == assistant_message_id)
            .values(
                content=content,
                diagrams=diagrams or None,
                knowledge_points=knowledge_points or None,
            )
        )
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(update_time=datetime.now(timezone.utc))
        )
        await db.commit()


class TutoringStreamAdapter:
    """Buffer arbitrary byte chunks, adapt events, and persist final state."""

    def __init__(
        self,
        stream_sse: StreamSSE | None = None,
        persist_result: PersistResult | None = None,
    ):
        self._stream_sse = stream_sse or agent_client.stream_sse
        self._persist_result = persist_result or persist_tutoring_result

    @staticmethod
    def _adapt_data(data_str: str, state: StreamState) -> str | None:
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError:
            return data_str

        event_type = parsed.get("type", "")
        if event_type == "chunk":
            state.chunks.append(parsed.get("content", ""))
        elif event_type == "diagram":
            state.diagrams.append(parsed.get("data", parsed))
        elif event_type == "knowledge_points":
            candidate = (
                parsed.get("points")
                or parsed.get("knowledge_points")
                or parsed.get("data")
            )
            if isinstance(candidate, list):
                state.knowledge_points = candidate
        elif event_type == "done":
            state.done_sent = True
            knowledge_points_used = parsed.get("knowledge_points_used")
            if (
                not state.knowledge_points
                and isinstance(knowledge_points_used, list)
            ):
                state.knowledge_points = knowledge_points_used
            parsed["conversation_id"] = state.conversation_id
            parsed["message_id"] = state.assistant_message_id
            return json.dumps(parsed, ensure_ascii=False)
        elif event_type == "text_delta":
            payload = (
                parsed.get("payload")
                if isinstance(parsed.get("payload"), dict)
                else {}
            )
            content = payload.get("delta", "")
            state.chunks.append(content)
            return json.dumps(
                {"type": "chunk", "content": content},
                ensure_ascii=False,
            )
        elif event_type == "workflow_completed":
            state.done_sent = True
            return json.dumps(
                {
                    "type": "done",
                    "conversation_id": state.conversation_id,
                    "message_id": state.assistant_message_id,
                },
                ensure_ascii=False,
            )
        elif event_type == "workflow_failed":
            state.done_sent = True
            payload = (
                parsed.get("payload")
                if isinstance(parsed.get("payload"), dict)
                else {}
            )
            return json.dumps(
                {
                    "type": "done",
                    "conversation_id": state.conversation_id,
                    "message_id": state.assistant_message_id,
                    "error": payload.get("reason", "agent_failed"),
                },
                ensure_ascii=False,
            )
        elif event_type in {
            "workflow_started",
            "tool_started",
            "tool_completed",
            "tool_failed",
            "source_refs",
            "artifact_created",
            "critic_completed",
        }:
            return None
        return data_str

    @classmethod
    def _adapt_line(cls, line: str, state: StreamState) -> dict | None:
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            return None
        data_str = stripped[5:].strip()
        if not data_str:
            return None
        adapted = cls._adapt_data(data_str, state)
        if adapted is None:
            return None
        return {
            "event": "message",
            "data": adapted,
        }

    @staticmethod
    def _build_workbench_payload(payload: dict) -> dict:
        return {
            "user_id": payload.get("user_id") or "",
            "scope": payload.get("scope") or "global",
            "course_id": payload.get("course_id"),
            "conversation_id": payload.get("conversation_id"),
            "message": payload.get("message") or "",
            "context": payload,
        }

    async def stream(
        self,
        *,
        payload: dict,
        conversation_id: str,
        assistant_message_id: str,
    ) -> AsyncIterator[dict]:
        state = StreamState(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
        )
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        text_buffer = ""

        try:
            async for raw_bytes in self._stream_sse(
                "/agent/v2/workbench/chat",
                self._build_workbench_payload(payload),
            ):
                text_buffer += decoder.decode(raw_bytes)
                while "\n" in text_buffer:
                    line, text_buffer = text_buffer.split("\n", 1)
                    event = self._adapt_line(line.rstrip("\r"), state)
                    if event is not None:
                        yield event

            text_buffer += decoder.decode(b"", final=True)
            if text_buffer:
                event = self._adapt_line(text_buffer.rstrip("\r"), state)
                if event is not None:
                    yield event
        except AgentServiceError:
            if not state.done_sent:
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "type": "done",
                            "conversation_id": conversation_id,
                            "message_id": assistant_message_id,
                            "error": "Agent 服务暂时不可用",
                        },
                        ensure_ascii=False,
                    ),
                }
        finally:
            try:
                await self._persist_result(
                    assistant_message_id,
                    conversation_id,
                    "".join(state.chunks),
                    state.diagrams,
                    state.knowledge_points,
                )
            except Exception:
                logger.exception(
                    "Failed to persist tutoring stream result",
                    extra={
                        "conversation_id": conversation_id,
                        "message_id": assistant_message_id,
                    },
                )
