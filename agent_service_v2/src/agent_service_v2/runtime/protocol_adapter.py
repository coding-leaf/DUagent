from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from agentscope.event import (
    DataBlockDeltaEvent,
    ExceedMaxItersEvent,
    ModelCallEndEvent,
    ModelCallStartEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockEndEvent,
    TextBlockDeltaEvent,
    TextBlockStartEvent,
    ThinkingBlockEndEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultDataDeltaEvent,
    ToolResultEndEvent,
    ToolResultTextDeltaEvent,
    ToolResultStartEvent,
    UserConfirmResultEvent,
)

from agent_service_v2.artifacts.manifest import ArtifactPublisher
from agent_service_v2.runtime.edu_events import EduEvent, EduEventType, utc_now_iso


class EDUProtocolAdapter:
    def __init__(
        self,
        *,
        run_id: str,
        conversation_id: str | None,
        agent: str = "edu_ai_chat_workbench",
        artifact_publisher: ArtifactPublisher | None = None,
    ) -> None:
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.agent = agent
        self._artifact_publisher = artifact_publisher
        self._seq = 0
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}
        self._tool_result_text: dict[str, str] = {}
        self._plan_tasks: dict[str, dict[str, str]] = {}

    def adapt(self, event: Any) -> EduEvent | None:
        self._capture_event_context(event)
        mapped = self._map_event(event)
        if mapped is None:
            return None
        event_type, payload = mapped
        return self._build_event(event_type, payload)

    def adapt_many(self, event: Any) -> list[EduEvent]:
        self._capture_event_context(event)
        mapped = self._map_event(event)
        events: list[EduEvent] = []
        if mapped is not None:
            event_type, payload = mapped
            if isinstance(event, ReplyEndEvent):
                events.extend(self._build_artifact_events())
            events.append(self._build_event(event_type, payload))
        if isinstance(event, ToolResultEndEvent):
            plan_payload = self._build_plan_payload_for_tool_result(event)
            if plan_payload is not None:
                events.append(self._build_event(EduEventType.PLAN_UPDATED, plan_payload))
            if self._is_successful_artifact_tool_result(event):
                events.extend(self._build_artifact_events())
        return events

    def _build_event(self, event_type: EduEventType, payload: dict[str, Any]) -> EduEvent:
        self._seq += 1
        return EduEvent(
            type=event_type,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            seq=self._seq,
            timestamp=utc_now_iso(),
            agent=self.agent,
            payload=payload,
        )

    def _capture_event_context(self, event: Any) -> None:
        if isinstance(event, ToolCallStartEvent):
            self._tool_names[event.tool_call_id] = event.tool_call_name
            self._tool_inputs[event.tool_call_id] = ""
            self._tool_result_text[event.tool_call_id] = ""
        elif isinstance(event, ToolCallDeltaEvent):
            self._tool_inputs[event.tool_call_id] = (
                self._tool_inputs.get(event.tool_call_id, "") + event.delta
            )
        elif isinstance(event, ToolResultTextDeltaEvent):
            self._tool_result_text[event.tool_call_id] = (
                self._tool_result_text.get(event.tool_call_id, "") + event.delta
            )

    def _map_event(self, event: Any) -> tuple[EduEventType, dict[str, Any]] | None:
        if isinstance(event, ReplyStartEvent):
            return EduEventType.WORKFLOW_STARTED, {
                "reply_id": event.reply_id,
                "session_id": event.session_id,
            }
        if isinstance(event, TextBlockDeltaEvent):
            return EduEventType.TEXT_DELTA, {"delta": event.delta}
        if isinstance(event, ToolCallStartEvent):
            return EduEventType.TOOL_STARTED, {
                "tool_call_id": event.tool_call_id,
                "tool_name": event.tool_call_name,
            }
        if isinstance(event, ToolResultEndEvent):
            payload: dict[str, Any] = {
                "tool_call_id": event.tool_call_id,
                "tool_name": self._tool_names.get(event.tool_call_id),
                "state": getattr(event.state, "value", event.state),
            }
            parsed = _parse_json_object(self._tool_result_text.get(event.tool_call_id, ""))
            if parsed:
                if "status" in parsed:
                    payload["status"] = parsed["status"]
                if "reason" in parsed:
                    payload["reason"] = parsed["reason"]
                summary = parsed.get("summary") if isinstance(parsed.get("summary"), dict) else {}
                returned_count = summary.get("returned_count")
                if returned_count is not None:
                    payload["returned_count"] = returned_count
                    payload["output_summary"] = f"返回 {returned_count} 条学习记录"
                elif parsed.get("status"):
                    payload["output_summary"] = f"工具状态：{parsed['status']}"
            return EduEventType.TOOL_COMPLETED, payload
        if isinstance(event, ReplyEndEvent):
            return EduEventType.WORKFLOW_COMPLETED, {"reply_id": event.reply_id}
        if isinstance(event, ExceedMaxItersEvent):
            return EduEventType.WORKFLOW_FAILED, {
                "reply_id": event.reply_id,
                "reason": "exceed_max_iters",
            }
        if isinstance(
            event,
            (
                ModelCallStartEvent,
                ModelCallEndEvent,
                DataBlockDeltaEvent,
                TextBlockStartEvent,
                TextBlockEndEvent,
                ThinkingBlockStartEvent,
                ThinkingBlockDeltaEvent,
                ThinkingBlockEndEvent,
                ToolCallDeltaEvent,
                ToolCallEndEvent,
                ToolResultDataDeltaEvent,
                ToolResultStartEvent,
                ToolResultTextDeltaEvent,
                RequireUserConfirmEvent,
                UserConfirmResultEvent,
            ),
        ):
            return None
        return EduEventType.WORKFLOW_FAILED, {
            "reason": "unsupported_agentscope_event",
            "event_class": event.__class__.__name__,
        }

    def _build_plan_payload_for_tool_result(self, event: ToolResultEndEvent) -> dict[str, Any] | None:
        state = getattr(event.state, "value", event.state)
        if state == "error":
            return None
        tool_name = self._tool_names.get(event.tool_call_id)
        if tool_name not in {"TaskCreate", "TaskUpdate", "TaskList"}:
            return None

        tool_input = _parse_json_object(self._tool_inputs.get(event.tool_call_id, ""))
        result_text = self._tool_result_text.get(event.tool_call_id, "")
        if tool_name == "TaskCreate":
            task_id = _extract_created_task_id(result_text) or str(len(self._plan_tasks) + 1)
            self._plan_tasks[task_id] = {
                "id": task_id,
                "title": tool_input.get("subject") or f"任务 {task_id}",
                "description": tool_input.get("description") or "",
                "status": "pending",
            }
        elif tool_name == "TaskUpdate":
            task_id = str(tool_input.get("task_id") or "")
            if not task_id:
                return None
            task = self._plan_tasks.setdefault(
                task_id,
                {"id": task_id, "title": f"任务 {task_id}", "description": "", "status": "pending"},
            )
            if tool_input.get("subject"):
                task["title"] = tool_input["subject"]
            if tool_input.get("description"):
                task["description"] = tool_input["description"]
            if tool_input.get("status"):
                task["status"] = tool_input["status"]
        elif tool_name == "TaskList":
            self._merge_task_list_text(result_text)

        return {"tasks": deepcopy(list(self._plan_tasks.values()))}

    def _is_successful_artifact_tool_result(self, event: ToolResultEndEvent) -> bool:
        state = getattr(event.state, "value", event.state)
        return state != "error" and self._tool_names.get(event.tool_call_id) == "write_artifact_file"

    def _build_artifact_events(self) -> list[EduEvent]:
        if self._artifact_publisher is None:
            return []
        seq_start = self._seq + 1
        return [
            self._build_event(EduEventType.ARTIFACT_CREATED, artifact.to_event_payload())
            for artifact in self._artifact_publisher.publish_new(seq_start=seq_start)
        ]

    def _merge_task_list_text(self, result_text: str) -> None:
        for line in result_text.splitlines():
            match = re.match(r"^\s*(?P<id>\S+)\s+\[(?P<status>[^\]]+)\]\s+(?P<title>.+)$", line)
            if not match:
                continue
            task_id = match.group("id")
            task = self._plan_tasks.setdefault(
                task_id,
                {"id": task_id, "title": match.group("title"), "description": "", "status": "pending"},
            )
            task["title"] = match.group("title")
            task["status"] = match.group("status")


def _parse_json_object(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_created_task_id(result_text: str) -> str | None:
    match = re.search(r"Task \(id=(?P<id>[^)]+)\) created successfully", result_text)
    return match.group("id") if match else None
