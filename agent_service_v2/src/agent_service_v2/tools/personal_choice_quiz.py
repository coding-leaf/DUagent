from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import BackendLearningClient
from agent_service_v2.tools.contracts import edu_tool_result
from agent_service_v2.tools.input_models import PersonalChoiceQuizInput
from agent_service_v2.tools.personal_practice_delivery import publish_prepared_practice


def build_personal_choice_quiz_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
    conversation_id: str | None,
    run_id: str,
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
            "practice_type": "choice_quiz",
            "choice_quiz": request.model_dump(),
        }
        return await publish_prepared_practice(client=client, prepare_payload=payload)

    tools = [
        FunctionTool(
            publish_personal_choice_quiz,
            name="publish_personal_choice_quiz",
            description="Publish one private choice-practice set through Backend.",
            is_read_only=False,
        )
    ]
    tools[0].input_schema = PersonalChoiceQuizInput.tool_schema()
    return tools
