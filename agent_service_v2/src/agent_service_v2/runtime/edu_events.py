from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EduEventType(StrEnum):
    WORKFLOW_STARTED = "workflow_started"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    SOURCE_REFS = "source_refs"
    ARTIFACT_CREATED = "artifact_created"
    CRITIC_COMPLETED = "critic_completed"
    TEXT_DELTA = "text_delta"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


@dataclass(frozen=True)
class EduEvent:
    type: EduEventType
    run_id: str
    conversation_id: str | None
    seq: int
    timestamp: str
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "run_id": self.run_id,
            "conversation_id": self.conversation_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "payload": self.payload,
        }


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
