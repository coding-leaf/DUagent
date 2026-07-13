from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.contracts import edu_tool_result, normalize_tool_result
from agent_service_v2.tools.input_models import ResumePracticeDeliveryInput


_RETRYABLE_DELIVERY_REASONS = {
    "backend_timeout",
    "backend_unavailable",
    "connection_refused",
    "connection_error",
}


async def publish_prepared_practice(
    *,
    client: BackendLearningClient,
    prepare_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        prepared = await client.post_json(
            "/internal/ai-chat/personal-practices/prepare",
            prepare_payload,
        )
    except BackendLearningClientError as exc:
        return _client_failure(exc)

    generation_id = prepared.get("generation_id")
    if not isinstance(generation_id, str) or not generation_id:
        return edu_tool_result(status="delivery_incomplete", reason="generation_id_missing")
    delivery_payload = {
        "generation_id": generation_id,
        "user_id": prepare_payload["user_id"],
        "course_id": prepare_payload["course_id"],
    }
    for attempt in range(2):
        try:
            data = await client.post_json(
                "/internal/ai-chat/personal-practices/finalize",
                delivery_payload,
            )
            return normalize_tool_result(data, default_status="published")
        except BackendLearningClientError as exc:
            if attempt == 0 and exc.reason in _RETRYABLE_DELIVERY_REASONS:
                continue
            result = _client_failure(exc, generation_id=generation_id)
            if exc.reason in _RETRYABLE_DELIVERY_REASONS:
                result["status"] = "delivery_incomplete"
                result["outcome"] = "failure"
            return result
    return edu_tool_result(
        status="delivery_incomplete",
        reason="delivery_retry_exhausted",
        retryable=True,
        data={"generation_id": generation_id},
    )


def build_resume_personal_practice_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
) -> list[FunctionTool]:
    async def resume_personal_practice_delivery(
        generation_id: str,
        **_ignored: Any,
    ) -> dict[str, Any]:
        """Resume one previously prepared interactive practice delivery.

        Args:
            generation_id: Generation identifier returned by a failed publishing tool.
        """
        if client is None or not course_id:
            return edu_tool_result(status="unavailable", reason="ai_chat_context_not_configured")
        try:
            data = await client.post_json(
                "/internal/ai-chat/personal-practices/resume",
                {
                    "generation_id": generation_id,
                    "user_id": user_id,
                    "course_id": course_id,
                },
            )
        except BackendLearningClientError as exc:
            return _client_failure(exc, generation_id=generation_id)
        return normalize_tool_result(data, default_status="published")

    tools = [FunctionTool(
        resume_personal_practice_delivery,
        name="resume_personal_practice_delivery",
        description="Resume a failed Backend delivery by generation identifier.",
        is_read_only=False,
    )]
    tools[0].input_schema = ResumePracticeDeliveryInput.tool_schema()
    return tools


def _client_failure(
    exc: BackendLearningClientError,
    *,
    generation_id: str | None = None,
) -> dict[str, Any]:
    rejected = exc.reason in {"backend_validation_error", "backend_rejected"}
    status = "rejected" if rejected else "unavailable"
    return edu_tool_result(
        status=status,
        reason=exc.detail_reason or exc.reason,
        retryable=not rejected,
        data={"generation_id": generation_id} if generation_id else {},
    )
