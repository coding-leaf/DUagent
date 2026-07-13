from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import BackendLearningClient, BackendLearningClientError
from agent_service_v2.tools.contracts import edu_tool_result
from agent_service_v2.tools.input_models import PersonalizedResourceGenerateInput, PersonalizedResourceRecommendInput


def build_personalized_resource_tools(
    *, client: BackendLearningClient | None, user_id: str, course_id: str | None,
    conversation_id: str | None, run_id: str,
) -> list[FunctionTool]:
    started_artifact: dict[str, Any] | None = None

    async def recommend_personalized_resources(
        target: str, knowledge_point: str | None = None, limit: int = 3, **_ignored: Any,
    ) -> dict[str, Any]:
        request = PersonalizedResourceRecommendInput(
            target=target, knowledge_point=knowledge_point, limit=limit
        )
        if client is None or not course_id:
            return edu_tool_result(status="unavailable", reason="course_or_backend_missing", retryable=True)
        try:
            data = await client.post_json("/internal/ai-chat/personalized-resources/recommend", {
                "user_id": user_id, "course_id": course_id, **request.model_dump(exclude_none=True),
            })
        except BackendLearningClientError as exc:
            return edu_tool_result(status="unavailable", reason=exc.reason, retryable=True)
        items = data.get("items") if isinstance(data.get("items"), list) else []
        artifact = None
        if items:
            artifact = {
                "id": f"personalized-recommendations-{run_id}",
                "type": "PersonalizedResourceCard",
                "title": "为你推荐",
                "props": {"course_id": course_id, "resources": items},
            }
        return edu_tool_result(
            status="available" if items else "empty",
            summary={"returned_count": len(items)},
            data={"items": items}, artifact=artifact,
        )

    async def generate_personalized_resource(
        goal: str, resource_type: str, **_ignored: Any,
    ) -> dict[str, Any]:
        nonlocal started_artifact
        request = PersonalizedResourceGenerateInput(goal=goal, resource_type=resource_type)
        if started_artifact is not None:
            return edu_tool_result(
                status="success", summary="本轮已启动一个资源任务",
                data={"task_status": "processing"}, artifact=started_artifact,
            )
        if client is None or not course_id or not conversation_id:
            return edu_tool_result(status="unavailable", reason="dialogue_or_backend_missing", retryable=True)
        try:
            data = await client.post_json("/internal/ai-chat/personalized-resources/generate", {
                "user_id": user_id, "course_id": course_id, "conversation_id": conversation_id,
                "run_id": run_id, **request.model_dump(),
            })
        except BackendLearningClientError as exc:
            return edu_tool_result(status="unavailable", reason=exc.reason, retryable=True)
        task_status = str(data.get("status") or "failed")
        artifact = {
            "id": f"personalized-generation-{data.get('task_id')}",
            "type": "PersonalizedResourceCard",
            "title": "个性化资源生成",
            "props": {
                "task_id": data.get("task_id"), "course_id": course_id,
                "resource_type": request.resource_type, "goal": request.goal,
            },
        }
        if task_status == "failed":
            return edu_tool_result(
                status="error", reason=data.get("error_message") or "generation_start_failed",
                data={"task_id": data.get("task_id")}, artifact=artifact,
            )
        started_artifact = artifact
        return edu_tool_result(
            status="success", summary="资源任务已启动，尚未发布",
            data={"task_id": data.get("task_id"), "task_status": task_status}, artifact=artifact,
        )

    recommend_tool = FunctionTool(recommend_personalized_resources, name="recommend_personalized_resources", is_read_only=True)
    generate_tool = FunctionTool(generate_personalized_resource, name="generate_personalized_resource")
    recommend_tool.input_schema = PersonalizedResourceRecommendInput.tool_schema()
    generate_tool.input_schema = PersonalizedResourceGenerateInput.tool_schema()
    return [recommend_tool, generate_tool]
