from __future__ import annotations

import json
import re
from typing import Any

from agentscope.tool import FunctionTool
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.artifact_files import build_write_artifact_file


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
    artifact_writer = (
        build_write_artifact_file(workspace=workspace, run_id=run_id)
        if workspace is not None
        else None
    )

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
            return {
                "status": _failure_status(exc.reason),
                "reason": exc.detail_reason or exc.reason,
            }
        result = {"status": "created", **data}
        if artifact_writer is not None and data.get("problem_id") and data.get("language"):
            artifact = artifact_writer(
                filename=_artifact_filename(str(data["problem_id"])),
                content=json.dumps(
                    {
                        "type": "CodeSandboxCard",
                        "title": title,
                        "props": {
                            "problem_id": data["problem_id"],
                            "language": data["language"],
                        },
                    },
                    ensure_ascii=False,
                ),
                artifact_type="CodeSandboxCard",
                title=title,
            )
            result["artifact"] = {
                "filename": artifact["filename"],
                "status": artifact["status"],
            }
        return result

    return [
        FunctionTool(
            create_validated_personal_code_problem,
            name="create_validated_personal_code_problem",
            description=(
                "Validate and save one private fixed-test-case programming problem for the current student. "
                "Supported canonical languages are c, cpp, python, java, go, and javascript. "
                "Provide at least one public input and one hidden input. "
                "The reference solution and all inputs are validated by Backend and never returned."
            ),
            is_read_only=False,
        )
    ]


def _artifact_filename(problem_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", problem_id).strip("_") or "code_problem"
    return f"{slug}_card.json"
