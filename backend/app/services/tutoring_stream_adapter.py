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
TOOL_EVENT_TYPES = {"tool_started", "tool_completed", "tool_failed"}
TOOL_EVENT_PAYLOAD_FIELDS = {
    "tool_call_id",
    "tool_name",
    "state",
    "status",
    "reason",
    "message",
    "output_summary",
    "summary",
}

StreamSSE = Callable[[str, dict], AsyncIterator[bytes]]
PersistResult = Callable[
    [str, str, str, list, list, dict],
    Awaitable[None],
]


@dataclass(frozen=True, slots=True)
class AgentLogRecord:
    endpoint: str
    latency_ms: int
    tokens_used: int
    status: str
    error_message: str | None


RecordAgentLog = Callable[[AgentLogRecord], Awaitable[None]]


@dataclass(slots=True)
class StreamState:
    conversation_id: str
    assistant_message_id: str
    chunks: list[str] = field(default_factory=list)
    diagrams: list = field(default_factory=list)
    knowledge_points: list = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    done_sent: bool = False
    persisted: bool = False


async def persist_tutoring_result(
    assistant_message_id: str,
    conversation_id: str,
    content: str,
    diagrams: list,
    knowledge_points: list,
    meta: dict,
) -> None:
    """Persist the accumulated stream through a short independent session."""
    async with async_session_factory() as db:
        existing = await db.get(Message, assistant_message_id)
        existing_meta = existing.meta_json if existing and isinstance(existing.meta_json, dict) else {}
        await db.execute(
            update(Message)
            .where(Message.id == assistant_message_id)
            .values(
                content=content,
                diagrams=diagrams or None,
                knowledge_points=knowledge_points or None,
                meta_json={**existing_meta, **(meta or {})},
            )
        )
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(update_time=datetime.now(timezone.utc))
        )
        await db.commit()


async def persist_agent_log(record: AgentLogRecord) -> None:
    from app.models.others import AgentLog

    async with async_session_factory() as db:
        db.add(
            AgentLog(
                agent_type="edu_ai",
                endpoint=record.endpoint,
                latency_ms=record.latency_ms,
                tokens_used=record.tokens_used,
                status=record.status,
                error_message=record.error_message,
            )
        )
        await db.commit()


class TutoringStreamAdapter:
    """Buffer arbitrary byte chunks, adapt events, and persist final state."""

    def __init__(
        self,
        stream_sse: StreamSSE | None = None,
        persist_result: PersistResult | None = None,
        record_agent_log: RecordAgentLog | None = None,
    ):
        self._stream_sse = stream_sse or agent_client.stream_sse
        self._persist_result = persist_result or persist_tutoring_result
        self._record_agent_log = record_agent_log or persist_agent_log

    @staticmethod
    def _adapt_data(data_str: str, state: StreamState) -> str | None:
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError:
            return data_str

        event_type = parsed.get("type", "")
        payload = (
            parsed.get("payload")
            if isinstance(parsed.get("payload"), dict)
            else {}
        )

        if event_type == "text_delta":
            content = payload.get("delta", "")
            state.chunks.append(content)
        elif event_type == "workflow_completed":
            state.done_sent = True
        elif event_type == "workflow_failed":
            state.done_sent = True
        elif event_type == "content_safety_reviewed":
            state.meta["content_safety_review"] = payload
        elif event_type in TOOL_EVENT_TYPES:
            tool_payload = {
                key: value
                for key, value in payload.items()
                if key in TOOL_EVENT_PAYLOAD_FIELDS
            }
            state.meta.setdefault("tool_events", []).append(
                {"type": event_type, "payload": tool_payload}
            )
        elif event_type == "artifact_created":
            artifact = payload.get("artifact")
            if isinstance(artifact, dict):
                artifact_id = artifact.get("id")
                if artifact_id:
                    existing_idx = next((i for i, a in enumerate(state.artifacts) if a.get("id") == artifact_id), None)
                    if existing_idx is not None:
                        state.artifacts[existing_idx] = artifact
                    else:
                        state.artifacts.append(artifact)
                else:
                    state.artifacts.append(artifact)
                state.meta["artifacts"] = state.artifacts

        parsed["conversation_id"] = state.conversation_id
        parsed["message_id"] = state.assistant_message_id
        return json.dumps(parsed, ensure_ascii=False)

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
    def _is_terminal_event(event: dict) -> bool:
        try:
            event_type = json.loads(event.get("data", "")).get("type")
        except (json.JSONDecodeError, AttributeError):
            return False
        return event_type in {"workflow_completed", "workflow_failed"}

    async def _persist_state(
        self,
        state: StreamState,
    ) -> bool:
        try:
            await self._persist_result(
                state.assistant_message_id,
                state.conversation_id,
                "".join(state.chunks),
                state.diagrams,
                state.knowledge_points,
                state.meta,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to persist tutoring stream result",
                extra={
                    "conversation_id": state.conversation_id,
                    "message_id": state.assistant_message_id,
                },
            )
            return False

    @staticmethod
    def _build_workbench_payload(payload: dict) -> dict:
        scope = payload.get("scope") or "global"
        return {
            "user_id": payload.get("user_id") or "",
            "scope": scope,
            "course_id": payload.get("course_id"),
            "catalog_id": payload.get("catalog_id") if scope == "course" else None,
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

        start_time = datetime.now(timezone.utc)
        status_val = "success"
        error_message = None

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
                        if self._is_terminal_event(event):
                            state.persisted = await self._persist_state(state)
                        yield event

            text_buffer += decoder.decode(b"", final=True)
            if text_buffer:
                event = self._adapt_line(text_buffer.rstrip("\r"), state)
                if event is not None:
                    if self._is_terminal_event(event):
                        state.persisted = await self._persist_state(state)
                    yield event
        except AgentServiceError as e:
            status_val = "error"
            error_message = "AgentServiceError: Agent 服务不可用"
            if not state.done_sent:
                failed_event = {
                    "event": "message",
                    "data": json.dumps(
                        {
                            "type": "workflow_failed",
                            "run_id": None,
                            "conversation_id": conversation_id,
                            "message_id": assistant_message_id,
                            "seq": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "backend_proxy",
                            "payload": {
                                "reason": "agent_service_unavailable",
                                "message": "Agent 服务暂时不可用",
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
                state.persisted = await self._persist_state(state)
                yield failed_event
        except Exception as e:
            status_val = "error"
            error_message = f"UnexpectedError: {str(e)}"
            raise e
        finally:
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            full_text = "".join(state.chunks)
            if not full_text and not state.artifacts and status_val == "success":
                status_val = "error"
                error_message = "No output generated"

            if not state.persisted:
                state.persisted = await self._persist_state(state)

            try:
                await self._record_agent_log(
                    AgentLogRecord(
                        endpoint="/agent/v2/workbench/chat",
                        latency_ms=latency_ms,
                        tokens_used=0,
                        status=status_val,
                        error_message=error_message,
                    )
                )
            except Exception:
                logger.exception("Failed to save real AgentLog in DB")
