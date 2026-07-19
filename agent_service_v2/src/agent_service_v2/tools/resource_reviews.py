from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)

ALLOWED_HARD_FAILURES = {
    "privacy_leak",
    "unsafe_content",
    "grounding_missing",
    "deterministic_validation_failed",
    "goal_mismatch",
}


def build_resource_review_tools(client: BackendLearningClient) -> list[FunctionTool]:
    async def review_personalized_resource(
        generation_id: str,
        user_id: str,
        course_id: str,
        hard_failures: list[str],
        warnings: list[str],
        summary: str,
    ) -> dict:
        accepted_failures = [
            failure for failure in hard_failures if failure in ALLOWED_HARD_FAILURES
        ]
        demoted_advice = [
            failure for failure in hard_failures if failure not in ALLOWED_HARD_FAILURES
        ]
        warnings = [*warnings, *demoted_advice]
        decision = (
            "rejected"
            if accepted_failures
            else "approved_with_advice"
            if warnings
            else "approved"
        )
        data = await _post(
            client,
            f"/internal/personalized-resources/{generation_id}/review",
            {
                "user_id": user_id,
                "course_id": course_id,
                "decision": decision,
                "hard_failures": accepted_failures,
                "warnings": warnings,
                "summary": summary,
            },
        )
        return {**data, "decision": decision}

    async def publish_personalized_resource(
        generation_id: str,
        user_id: str,
        course_id: str,
        resource_kind: str = "resource",
    ) -> dict:
        return await _post(
            client,
            f"/internal/personalized-resources/{generation_id}/publish",
            {
                "user_id": user_id,
                "course_id": course_id,
                "resource_kind": resource_kind,
            },
        )

    return [
        FunctionTool(
            review_personalized_resource,
            name="review_personalized_resource",
            description="Record a permissive independent review; warnings never cause rejection.",
            is_read_only=False,
        ),
        FunctionTool(
            publish_personalized_resource,
            name="publish_personalized_resource",
            description="Publish a validated and independently approved personalized resource.",
            is_read_only=False,
        ),
    ]


async def _post(client: BackendLearningClient, path: str, payload: dict) -> dict:
    try:
        return await client.post_json(path, payload)
    except BackendLearningClientError as exc:
        return {"status": "failed", "reason": exc.detail_reason or exc.reason}
