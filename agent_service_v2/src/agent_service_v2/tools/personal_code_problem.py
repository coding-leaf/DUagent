from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)


def build_personal_code_problem_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
    conversation_id: str | None,
    run_id: str,
) -> list[FunctionTool]:
    async def create_validated_personal_code_problem(
        title: str,
        statement: str,
        language: str,
        starter_code: str,
        reference_solution: str,
        public_inputs: list[str],
        hidden_inputs: list[str],
        **_ignored: Any,
    ) -> dict[str, Any]:
        if client is None or not course_id or not conversation_id:
            return {
                "status": "unavailable",
                "reason": "ai_chat_context_not_configured",
            }
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "draft": {
                "title": title,
                "statement": statement,
                "language": language,
                "starter_code": starter_code,
                "reference_solution": reference_solution,
                "test_inputs": [
                    *({"stdin": value, "is_public": True} for value in public_inputs),
                    *({"stdin": value, "is_public": False} for value in hidden_inputs),
                ],
            },
        }
        try:
            data = await client.post_json("/internal/ai-chat/code-problems", payload)
        except BackendLearningClientError as exc:
            return {"status": "degraded", "reason": exc.reason}
        return {"status": "created", **data}

    return [
        FunctionTool(
            create_validated_personal_code_problem,
            name="create_validated_personal_code_problem",
            description=(
                "Validate and save one private fixed-test-case programming problem for the current student. "
                "Provide at least one public input and one hidden input. "
                "The reference solution and all inputs are validated by Backend and never returned."
            ),
            is_read_only=False,
        )
    ]
