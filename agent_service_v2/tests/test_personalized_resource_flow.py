from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from agent_service_v2.schemas.personalized_resources import (
    PersonalizedResourceGenerationRequest,
)
from agent_service_v2.generators import personalized_resource_flow as flow
from agent_service_v2.generators.personalized_resource_flow import (
    PersonalizedResourceGenerationRunner,
    PersonalizedResourceUnavailable,
    resolve_resource_types,
)
from agent_service_v2.runtime.edu_events import EduEventType


class FakeBackendClient:
    """Stand-in for `BackendLearningClient` with deterministic generation ids."""

    def __init__(self, *, fail_endpoint: str | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_endpoint = fail_endpoint
        self._drafts = 0

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, payload))
        if self.fail_endpoint and path.endswith(self.fail_endpoint):
            from agent_service_v2.tools.backend_learning_client import (
                BackendLearningClientError,
            )

            raise BackendLearningClientError("backend_server_error")
        if path.endswith("/drafts"):
            self._drafts += 1
            return {"generation_id": f"g{self._drafts}", "status": "drafted"}
        if path.endswith("/validation"):
            return {"generation_id": payload.get("generation_id"), "status": "validated"}
        if path.endswith("/review"):
            return {
                "generation_id": payload.get("generation_id"),
                "status": payload["decision"],
            }
        if path.endswith("/publish"):
            return {"resource_id": "r1", "resource_type": "diagram", "status": "published"}
        if path.endswith("/fail"):
            return {"task_id": payload.get("task_id"), "status": "failed"}
        raise AssertionError(f"unexpected backend path: {path}")


class FakeWriter:
    def __init__(self, contents: list[str] | None = None) -> None:
        self.hints: list[str] = []
        self.course_ids: list[str] = []
        self._contents = contents or ["flowchart TD\nA-->B"]
        self._index = 0

    async def write(
        self,
        resource_type: str,
        *,
        goal: str,
        chapter: str,
        knowledge_point: str,
        course_id: str,
        course_title: str | None,
        difficulty: str | None,
        repair_hint: str,
    ) -> dict[str, Any]:
        assert resource_type in {"diagram", "personal_lesson", "practice", "reading"}
        self.course_ids.append(course_id)
        self.hints.append(repair_hint)
        content = self._contents[min(self._index, len(self._contents) - 1)]
        self._index += 1
        return {
            "title": "指针结构图",
            "content": content,
            "description": "围绕指针的知识结构图",
            "tags": ["mindmap"],
        }


def _request(**overrides: Any) -> PersonalizedResourceGenerationRequest:
    payload = {
        "task_id": "task-1",
        "user_id": "student-1",
        "course_id": "course-1",
        "course_title": "C语言",
        "goal": "复习指针",
        "knowledge_point": "指针",
        "resource_preferences": ["chart_logic"],
    }
    payload.update(overrides)
    return PersonalizedResourceGenerationRequest(**payload)


def _run(runner: PersonalizedResourceGenerationRunner, request: PersonalizedResourceGenerationRequest):
    events: list[tuple[EduEventType, dict[str, Any]]] = []

    def emit(event_type: EduEventType, payload: dict[str, Any]) -> None:
        events.append((event_type, payload))

    result = asyncio.run(runner.run(request, emit))
    return result, events


def test_runner_drafts_validates_reviews_and_publishes_without_loopback():
    client = FakeBackendClient()
    writer = FakeWriter()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    result, events = _run(runner, _request())

    assert result == {
        "status": "completed",
        "items": [
            {
                "generation_id": "g1",
                "resource_id": "r1",
                "title": "指针结构图",
                "resource_type": "diagram",
            }
        ],
    }
    assert [path for path, _ in client.calls] == [
        "/internal/personalized-resources/drafts",
        "/internal/personalized-resources/g1/validation",
        "/internal/personalized-resources/g1/review",
        "/internal/personalized-resources/g1/publish",
    ]
    draft_payload = client.calls[0][1]
    assert draft_payload["run_id"] == "task-1"
    assert draft_payload["resource_type"] == "diagram"
    assert draft_payload["draft"]["knowledge_point"] == "指针"
    assert draft_payload["draft"]["content"] == "flowchart TD\nA-->B"

    types = [event_type for event_type, _ in events]
    assert types[0] is EduEventType.WORKFLOW_STARTED
    assert types[-1] is EduEventType.WORKFLOW_COMPLETED
    assert EduEventType.THOUGHT in types
    started_tools = [
        payload["tool_name"]
        for event_type, payload in events
        if event_type is EduEventType.TOOL_STARTED
    ]
    assert started_tools == [
        "create_personalized_resource_draft",
        "record_personalized_validation",
        "review_personalized_resource",
        "publish_personalized_resource",
    ]
    completed_tools = [
        payload["tool_name"]
        for event_type, payload in events
        if event_type is EduEventType.TOOL_COMPLETED
    ]
    assert completed_tools == started_tools


def test_runner_retries_once_when_deterministic_validation_fails():
    client = FakeBackendClient()
    writer = FakeWriter(contents=["", "flowchart TD\nA-->B"])
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    result, events = _run(runner, _request())

    assert result["status"] == "completed"
    assert writer.hints[0] == ""
    assert "未通过确定性校验" in writer.hints[1]
    assert [path for path, _ in client.calls] == [
        "/internal/personalized-resources/drafts",
        "/internal/personalized-resources/g1/validation",
        "/internal/personalized-resources/drafts",
        "/internal/personalized-resources/g2/validation",
        "/internal/personalized-resources/g2/review",
        "/internal/personalized-resources/g2/publish",
    ]
    assert any(
        event_type is EduEventType.THOUGHT and "返修" in payload["delta"]
        for event_type, payload in events
    )


def test_runner_reports_workflow_failed_after_exhausting_retries():
    client = FakeBackendClient()
    writer = FakeWriter(contents=["", ""])
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    result, events = _run(runner, _request())

    assert result == {"status": "failed", "reason": "not_published"}
    assert events[-1][0] is EduEventType.WORKFLOW_FAILED
    assert events[-1][1]["reason"] == "validation_failed"
    assert not any(
        event_type is EduEventType.WORKFLOW_COMPLETED for event_type, _ in events
    )


def test_runner_reports_lifecycle_tool_results_as_successful():
    """Draft/validate/review are successful steps, not tool failures.

    The frontend `chatStreamEvents.js` reducer downgrades a tool card to
    `error` when `outcome === "failure"` or `state === "error"`, so every
    non-failing pipeline step must report `success`.
    """
    runner = PersonalizedResourceGenerationRunner(
        client=FakeBackendClient(),
        writer=FakeWriter(),
    )

    _, events = _run(runner, _request())

    completed = [
        payload for event_type, payload in events
        if event_type is EduEventType.TOOL_COMPLETED
    ]
    assert [item["status"] for item in completed] == [
        "drafted",
        "validated",
        "approved",
        "published",
    ]
    assert all(item["outcome"] == "success" for item in completed)
    assert all(item["state"] == "success" for item in completed)
    assert all(item["output_summary"] for item in completed)


def test_runner_stops_before_publish_when_backend_review_fails():
    client = FakeBackendClient(fail_endpoint="/review")
    runner = PersonalizedResourceGenerationRunner(client=client, writer=FakeWriter())

    result, events = _run(runner, _request())

    assert result == {"status": "failed", "reason": "not_published"}
    assert events[-1][0] is EduEventType.WORKFLOW_FAILED
    assert not any(path.endswith("/publish") for path, _ in client.calls)


def test_runner_never_raises_when_a_tool_fails():
    class ExplodingClient(FakeBackendClient):
        async def post_json(self, path: str, payload: dict[str, Any]):
            raise RuntimeError("backend exploded")

    runner = PersonalizedResourceGenerationRunner(
        client=ExplodingClient(),
        writer=FakeWriter(),
    )

    result, events = _run(runner, _request())

    assert result == {"status": "failed", "reason": "not_published"}
    assert events[-1][0] is EduEventType.WORKFLOW_FAILED
    assert any(
        event_type is EduEventType.TOOL_COMPLETED and payload["outcome"] == "failure"
        for event_type, payload in events
    )


def test_preflight_rejects_missing_model_or_backend(monkeypatch):
    monkeypatch.setattr(flow, "build_chat_model_from_settings", lambda *_, **__: None)
    with pytest.raises(PersonalizedResourceUnavailable, match="model_not_configured"):
        PersonalizedResourceGenerationRunner(client=FakeBackendClient()).preflight()

    monkeypatch.setattr(flow, "build_chat_model_from_settings", lambda *_, **__: object())
    monkeypatch.setattr(
        flow, "build_backend_learning_client_from_settings", lambda *_, **__: None
    )
    with pytest.raises(PersonalizedResourceUnavailable, match="backend_not_configured"):
        PersonalizedResourceGenerationRunner().preflight()


def test_resolve_resource_types_maps_backend_preferences():
    assert resolve_resource_types(None) == ["personal_lesson"]
    assert resolve_resource_types([]) == ["personal_lesson"]
    assert resolve_resource_types(["chart_logic"]) == ["diagram"]
    assert resolve_resource_types(["text_reading", "code_practice"]) == [
        "reading",
        "practice",
    ]
    assert resolve_resource_types(["unknown"]) == ["personal_lesson"]


def test_every_emitted_payload_is_json_serializable():
    client = FakeBackendClient()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=FakeWriter())

    _, events = _run(runner, _request())

    for _, payload in events:
        json.dumps(payload, ensure_ascii=False)


def test_runner_uses_catalog_id_for_rag_writer_and_course_id_for_draft_persistence():
    client = FakeBackendClient()
    writer = FakeWriter()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    req = _request(catalog_id="catalog-42", course_id="class-course-101")
    result, _events = _run(runner, req)

    assert result["status"] == "completed"
    # writer.write 应当收到 catalog_id（用于向 Qdrant 检索课程目录教材切片）
    assert writer.course_ids == ["catalog-42"]

    # Backend 工具调用（草稿、校验、审核、发布）应当收到真实的教学班 course_id
    assert [path for path, _ in client.calls] == [
        "/internal/personalized-resources/drafts",
        "/internal/personalized-resources/g1/validation",
        "/internal/personalized-resources/g1/review",
        "/internal/personalized-resources/g1/publish",
    ]
    for _path, payload in client.calls:
        assert payload["course_id"] == "class-course-101"


def test_runner_concurrent_multi_resource_generation_via_teampipeline():
    client = FakeBackendClient()
    writer = FakeWriter()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    req = _request(
        resource_types=["diagram", "personal_lesson"],
        resource_preferences=[],
    )
    result, events = _run(runner, req)

    assert result["status"] == "completed"
    assert len(result["items"]) == 2
    types = [item["resource_type"] for item in result["items"]]
    assert "diagram" in types
    assert "personal_lesson" in types
    assert any(
        event_type is EduEventType.WORKFLOW_COMPLETED and len(payload["generation_ids"]) == 2
        for event_type, payload in events
    )


def test_runner_notifies_backend_task_fail_on_generation_failure():
    client = FakeBackendClient(fail_endpoint="/review")
    writer = FakeWriter()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    result, events = _run(runner, _request())

    assert result["status"] == "failed"
    assert any(
        path.endswith("/tasks/task-1/fail") and payload.get("error_code") == "generation_failed"
        for path, payload in client.calls
    )


def test_runner_notifies_backend_task_fail_on_unhandled_exception():
    class ThrowingWriter(FakeWriter):
        async def write(self, *args, **kwargs):
            raise RuntimeError("unexpected llm engine crash")

    client = FakeBackendClient()
    writer = ThrowingWriter()
    runner = PersonalizedResourceGenerationRunner(client=client, writer=writer)

    result, events = _run(runner, _request())

    assert result["status"] == "failed"
    assert any(
        path.endswith("/tasks/task-1/fail") and "unexpected llm engine crash" in payload.get("error_message", "")
        for path, payload in client.calls
    )

