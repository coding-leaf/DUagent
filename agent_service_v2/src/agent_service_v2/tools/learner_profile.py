from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.contracts import edu_tool_result, normalize_tool_result
from agent_service_v2.tools.input_models import DialogueProfileUpdateInput


def _unavailable(reason: str) -> dict[str, Any]:
    return edu_tool_result(status="unavailable", reason=reason, retryable=True)


def build_learner_profile_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
    conversation_id: str | None,
    run_id: str,
) -> list[FunctionTool]:
    async def read_learner_profile(**_ignored: Any) -> dict[str, Any]:
        """Read the learner's six-dimensional profile for the current course."""
        if client is None:
            return _unavailable("backend_learning_client_not_configured")
        if not course_id:
            return _unavailable("course_context_missing")
        try:
            return normalize_tool_result(await client.post_json(
                "/internal/ai-chat/learner-profile/read",
                {"user_id": user_id, "course_id": course_id},
            ))
        except BackendLearningClientError as exc:
            return _unavailable(exc.reason)

    async def update_learner_profile_from_dialogue(
        learning_goal: str | None = None,
        resource_preferences: list[str] | None = None,
        guidance_level: str | None = None,
        custom_instruction: str | None = None,
        learning_habits: dict[str, str] | None = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        """Persist only explicit and stable learner facts stated in the current dialogue."""
        request = DialogueProfileUpdateInput(
            learning_goal=learning_goal,
            resource_preferences=resource_preferences,
            guidance_level=guidance_level,
            custom_instruction=custom_instruction,
            learning_habits=learning_habits,
        )
        if client is None:
            return _unavailable("backend_learning_client_not_configured")
        if not course_id or not conversation_id:
            return _unavailable("dialogue_context_missing")
        payload = request.model_dump(exclude_none=True)
        payload.update({
            "user_id": user_id,
            "course_id": course_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
        })
        try:
            return normalize_tool_result(await client.post_json(
                "/internal/ai-chat/learner-profile/update", payload
            ))
        except BackendLearningClientError as exc:
            return _unavailable(exc.reason)

    read_tool = FunctionTool(
        read_learner_profile,
        name="read_learner_profile",
        description="Read the current course's six-dimensional learner profile.",
        is_read_only=True,
    )
    update_tool = FunctionTool(
        update_learner_profile_from_dialogue,
        name="update_learner_profile_from_dialogue",
        description="Update explicit stable learner goals, preferences, guidance, instructions, or habits from dialogue.",
    )
    read_tool.input_schema = {"type": "object", "properties": {}}
    update_tool.input_schema = DialogueProfileUpdateInput.tool_schema()
    return [read_tool, update_tool]
