import unittest

from agent_service.agents.resources import accept_resource_generation, normalize_resource_types
from agent_service.schemas.resources import ResourceGenerateRequest


class ResourceAgentTests(unittest.TestCase):
    def test_accept_resource_generation_preserves_backend_task_id(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-1",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
            resource_types=["document", "code"],
        )

        result = accept_resource_generation(request)

        self.assertEqual(result.task_id, "task-resource-1")
        self.assertEqual(result.estimated_duration, 60)

    def test_normalize_resource_types_uses_v1_default_without_video(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-2",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
        )

        resource_types = normalize_resource_types(request)

        self.assertEqual(resource_types, ["document", "mindmap", "reading", "code"])

    def test_accept_resource_generation_estimates_duration_from_requested_types(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-3",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
        )

        result = accept_resource_generation(request)

        self.assertEqual(result.estimated_duration, 120)


if __name__ == "__main__":
    unittest.main()
