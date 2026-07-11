from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)


def _bounded_recent_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return 10
    return max(1, min(parsed, 10))


def _bounded_node_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return 50
    return max(1, min(parsed, 100))


def _error_result(reason: str, status_code: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unavailable", "reason": reason}
    if status_code is not None:
        result["status_code"] = status_code
    return result


def build_learning_progress_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
) -> list[FunctionTool]:
    async def read_learning_progress(limit_nodes: int = 50, **_ignored: Any) -> dict[str, Any]:
        """Read the current student's course progress before giving next-step advice.

        Args:
            limit_nodes: Maximum progress nodes to return, from 1 through 100.
        """
        if client is None:
            return _error_result("backend_learning_client_not_configured")
        if not course_id:
            return _error_result("course_context_missing")
        try:
            return await client.post_json(
                "/internal/ai-chat/learning-progress",
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "limit_nodes": _bounded_node_limit(limit_nodes),
                },
            )
        except BackendLearningClientError as exc:
            return _error_result(exc.reason, exc.status_code)

    async def read_recent_answers(
        node_id: str | None = None,
        knowledge_point: str | None = None,
        limit: int = 10,
        only_wrong: bool = True,
        **_ignored: Any,
    ) -> dict[str, Any]:
        """Read recent answer evidence for one node or knowledge-point name.

        Args:
            node_id: Exact node identifier returned by read_learning_progress.
            knowledge_point: Exact knowledge-point name when no node_id is available.
            limit: Maximum records to return, from 1 through 10.
            only_wrong: Whether to return only incorrect answers.
        """
        if client is None:
            return _error_result("backend_learning_client_not_configured")
        if not course_id:
            return _error_result("course_context_missing")
        try:
            return await client.post_json(
                "/internal/ai-chat/recent-answers",
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "node_id": node_id,
                    "knowledge_point": knowledge_point,
                    "limit": _bounded_recent_limit(limit),
                    "only_wrong": bool(only_wrong),
                },
            )
        except BackendLearningClientError as exc:
            return _error_result(exc.reason, exc.status_code)

    return [
        FunctionTool(
            read_learning_progress,
            name="read_learning_progress",
            description="Read the current learner's course progress overview before giving next-step learning advice.",
            is_read_only=True,
        ),
        FunctionTool(
            read_recent_answers,
            name="read_recent_answers",
            description="Read up to 10 recent answer records for a node or knowledge point before explaining mistakes.",
            is_read_only=True,
        ),
    ]
