from __future__ import annotations

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)


def build_resource_draft_tools(client: BackendLearningClient) -> list[FunctionTool]:
    async def create_personalized_resource_draft(
        user_id: str,
        course_id: str,
        source_type: str,
        goal: str,
        resource_type: str,
        title: str,
        content: str,
        description: str = "",
        chapter: str = "",
        knowledge_point: str = "",
        tags: list[str] | None = None,
        conversation_id: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "source_type": source_type,
            "goal": goal,
            "resource_type": resource_type,
            "draft": {
                "title": title,
                "content": content,
                "description": description,
                "chapter": chapter,
                "knowledge_point": knowledge_point,
                "tags": tags or [],
            },
            "conversation_id": conversation_id,
            "run_id": run_id,
        }
        return await _post(client, "/internal/personalized-resources/drafts", payload)

    async def record_personalized_validation(
        generation_id: str,
        user_id: str,
        course_id: str,
        resource_type: str,
        content: str,
    ) -> dict:
        report = validate_typed_resource(resource_type, content)
        data = await _post(
            client,
            f"/internal/personalized-resources/{generation_id}/validation",
            {"user_id": user_id, "course_id": course_id, "report": report},
        )
        return {**data, "report": report}

    async def validate_personal_code_problem_draft(
        user_id: str,
        course_id: str,
        conversation_id: str,
        run_id: str,
        title: str,
        statement: str,
        language: str,
        starter_code: str,
        reference_solution: str,
        public_inputs: list[str],
        hidden_inputs: list[str],
    ) -> dict:
        return await _post(
            client,
            "/internal/ai-chat/code-problem-validations",
            {
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
            },
        )

    return [
        FunctionTool(
            create_personalized_resource_draft,
            name="create_personalized_resource_draft",
            description="Persist a typed personalized-resource draft; this never publishes it.",
            is_read_only=False,
        ),
        FunctionTool(
            record_personalized_validation,
            name="record_personalized_validation",
            description="Run deterministic format validation and attach its report to a draft.",
            is_read_only=False,
        ),
        FunctionTool(
            validate_personal_code_problem_draft,
            name="validate_personal_code_problem_draft",
            description="Ask Backend OJ to validate a private code-problem draft without publishing it.",
            is_read_only=False,
        ),
    ]


def validate_typed_resource(resource_type: str, content: str) -> dict:
    hard_failures: list[str] = []
    warnings: list[str] = []
    stripped = content.strip()
    if not stripped:
        hard_failures.append("empty_content")
    if resource_type == "diagram" and stripped:
        diagram_prefixes = ("flowchart", "graph", "mindmap", "sequenceDiagram", "classDiagram", "stateDiagram")
        if not stripped.startswith(diagram_prefixes):
            hard_failures.append("invalid_mermaid_source")
    if resource_type in {"personal_lesson", "practice", "reading"} and stripped:
        if len(stripped) < 40:
            warnings.append("content_is_brief")
    if resource_type not in {
        "personal_lesson",
        "diagram",
        "practice",
        "reading",
    }:
        hard_failures.append("unsupported_resource_type")
    return {
        "status": "failed" if hard_failures else "passed",
        "validator": "typed_resource_validator",
        "hard_failures": hard_failures,
        "warnings": warnings,
    }


async def _post(client: BackendLearningClient, path: str, payload: dict) -> dict:
    try:
        return await client.post_json(path, payload)
    except BackendLearningClientError as exc:
        return {"status": "failed", "reason": exc.detail_reason or exc.reason}
