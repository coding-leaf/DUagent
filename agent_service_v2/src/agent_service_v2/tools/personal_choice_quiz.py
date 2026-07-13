from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.contracts import edu_tool_result, normalize_tool_result
from agent_service_v2.tools.input_models import PersonalChoiceQuizInput


def _failure_status(reason: str) -> str:
    if reason in {"backend_validation_error", "backend_rejected"}:
        return "rejected"
    if reason in {"backend_timeout", "backend_unavailable"}:
        return "unavailable"
    return "degraded"


def build_personal_choice_quiz_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
    conversation_id: str | None,
    run_id: str,
    workspace: LocalWorkspace | None,
) -> list[FunctionTool]:
    async def publish_personal_choice_quiz(
        title: str,
        chapter: str,
        knowledge_point: str,
        questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate and publish private single-choice or multi-choice questions.

        Args:
            title: A concise title for the practice card.
            chapter: The course chapter shared by all questions.
            knowledge_point: The precise knowledge point shared by all questions.
            questions: One to eight complete question objects. Each object must contain type,
                content, options, answer, explanation, and difficulty. Type must be
                single_choice or multi_choice. Options use key/text objects. A single-choice
                answer is one option key; a multi-choice answer is a list of option keys.

        Returns:
            A published result with question_ids and an atomically created QuizCard artifact.
        """
        request = PersonalChoiceQuizInput(
            title=title,
            chapter=chapter,
            knowledge_point=knowledge_point,
            questions=questions,
        )
        if client is None or not course_id or not conversation_id:
            return edu_tool_result(status="unavailable", reason="ai_chat_context_not_configured")
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            **request.model_dump(),
        }
        try:
            data = await client.post_json("/internal/ai-chat/choice-quizzes", payload)
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
            publish_personal_choice_quiz,
            name="publish_personal_choice_quiz",
            description=(
                "Publish one private practice set containing only single-choice and multi-choice "
                "questions, then create its persistent QuizCard. Use the programming-problem tool "
                "instead when the student must write executable code."
            ),
            is_read_only=False,
        )
    ]
    tools[0].input_schema = PersonalChoiceQuizInput.tool_schema()
    return tools
