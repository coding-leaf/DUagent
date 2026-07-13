from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.contracts import edu_tool_result, normalize_tool_result
from agent_service_v2.tools.input_models import PersonalCodeProblemInput


def _failure_status(reason: str) -> str:
    if reason in {"backend_validation_error", "backend_rejected"}:
        return "rejected"
    if reason in {"backend_timeout", "backend_unavailable"}:
        return "unavailable"
    return "degraded"


def build_personal_code_problem_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
    conversation_id: str | None,
    run_id: str,
    workspace: LocalWorkspace | None = None,
) -> list[FunctionTool]:
    async def publish_personal_code_problem(
        title: str,
        statement: str,
        language: str,
        starter_code: str,
        reference_solution: str,
        public_inputs: list[str],
        hidden_inputs: list[str],
        **_ignored: Any,
    ) -> dict[str, Any]:
        """Validate and publish one private fixed-case problem for the current student.

        Args:
            title: A concise problem title.
            statement: A complete Markdown problem statement without the reference solution.
            language: One of c, cpp, python, java, go, or javascript.
            starter_code: Safe starter code shown to the student; an empty string is allowed.
            reference_solution: A complete solution used only by Backend OJ validation.
            public_inputs: Complete stdin values visible to the student; at least one is required.
            hidden_inputs: Complete stdin values hidden from the student; at least one is required.

        Returns:
            A published result with generation_id and problem_id, or a rejected/unavailable result.
        """
        request = PersonalCodeProblemInput(
            title=title,
            statement=statement,
            language=language,
            starter_code=starter_code,
            reference_solution=reference_solution,
            public_inputs=public_inputs,
            hidden_inputs=hidden_inputs,
        )
        if client is None or not course_id or not conversation_id:
            return edu_tool_result(status="unavailable", reason="ai_chat_context_not_configured")
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "draft": {
                "title": request.title,
                "statement": request.statement,
                "language": request.language,
                "starter_code": request.starter_code,
                "reference_solution": request.reference_solution,
                "test_inputs": [
                    *({"stdin": value, "is_public": True} for value in request.public_inputs),
                    *({"stdin": value, "is_public": False} for value in request.hidden_inputs),
                ],
            },
        }
        try:
            data = await client.post_json(
                "/internal/ai-chat/code-problem-validations", payload
            )
        except BackendLearningClientError as exc:
            status = _failure_status(exc.reason)
            return edu_tool_result(
                status=status,
                reason=exc.detail_reason or exc.reason,
                retryable=status == "unavailable",
            )
        return normalize_tool_result(data, default_status="published")

    tools = [
        FunctionTool(
            publish_personal_code_problem,
            name="publish_personal_code_problem",
            description=(
                "Validate and immediately publish one private fixed-test-case programming problem for the current student. "
                "Supported canonical languages are c, cpp, python, java, go, and javascript. "
                "Provide at least one public input and one hidden input. "
                "Success is only status published with a non-empty problem_id and artifact_status created. "
                "Never expose the reference solution or hidden inputs in chat or artifacts."
            ),
            is_read_only=False,
        )
    ]
    tools[0].input_schema = PersonalCodeProblemInput.tool_schema()
    return tools
