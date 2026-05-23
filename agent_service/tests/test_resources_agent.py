import unittest

from agent_service.agents.resources import (
    accept_resource_generation,
    build_resource_generation_result,
    normalize_resource_types,
    run_resource_generation_task,
    send_webhook_with_retry,
)
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


class ResourceGenerationWorkerTests(unittest.IsolatedAsyncioTestCase):
    def test_build_resource_generation_result_uses_webhook_contract_shape(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-4",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
            chapter="函数",
            knowledge_point="一次函数",
            resource_types=["document"],
        )

        payload = build_resource_generation_result(request)

        self.assertEqual(payload["task_id"], "task-resource-4")
        self.assertEqual(payload["task_type"], "resource_generation")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(payload["result"]["resources"]), 1)
        resource = payload["result"]["resources"][0]
        self.assertEqual(resource["type"], "document")
        self.assertEqual(resource["chapter"], "函数")
        self.assertEqual(resource["knowledge_point"], "一次函数")
        self.assertIn("tags", resource)

    async def test_run_resource_generation_task_posts_completed_payload(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-5",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
            resource_types=["reading"],
        )
        calls = []

        async def fake_sender(webhook_url: str, payload: dict) -> None:
            calls.append((webhook_url, payload))

        await run_resource_generation_task(request, send_webhook=fake_sender)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], request.webhook_url)
        self.assertEqual(calls[0][1]["task_id"], "task-resource-5")
        self.assertEqual(calls[0][1]["status"], "completed")

    async def test_run_resource_generation_task_posts_failed_payload_when_generation_fails(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-6",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
        )
        calls = []

        def failing_builder(request: ResourceGenerateRequest) -> dict:
            raise RuntimeError("generation failed")

        async def fake_sender(webhook_url: str, payload: dict) -> None:
            calls.append((webhook_url, payload))

        await run_resource_generation_task(
            request,
            send_webhook=fake_sender,
            result_builder=failing_builder,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["task_id"], "task-resource-6")
        self.assertEqual(calls[0][1]["task_type"], "resource_generation")
        self.assertEqual(calls[0][1]["status"], "failed")
        self.assertEqual(calls[0][1]["error_message"], "generation failed")

    async def test_send_webhook_with_retry_retries_until_success(self) -> None:
        calls = []
        sleeps = []

        async def flaky_sender(webhook_url: str, payload: dict) -> None:
            calls.append((webhook_url, payload))
            if len(calls) < 3:
                raise RuntimeError("temporary network error")

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        await send_webhook_with_retry(
            "https://backend.example.com/api/v1/webhooks/agent",
            {"task_id": "task-resource-7", "status": "completed"},
            sender=flaky_sender,
            sleep=fake_sleep,
            max_attempts=3,
            base_delay_seconds=0.5,
        )

        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [0.5, 1.0])

    async def test_run_resource_generation_task_does_not_raise_when_webhook_send_fails(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-8",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
        )
        calls = []

        async def failing_sender(webhook_url: str, payload: dict) -> None:
            calls.append((webhook_url, payload))
            raise RuntimeError("backend unavailable")

        await run_resource_generation_task(
            request,
            send_webhook=failing_sender,
            max_webhook_attempts=2,
            webhook_base_delay_seconds=0,
        )

        self.assertEqual(len(calls), 2)

    async def test_run_resource_generation_task_logs_final_webhook_failure(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-resource-9",
            user_id="teacher-1",
            course_id="course-1",
            webhook_url="https://backend.example.com/api/v1/webhooks/agent",
        )

        async def failing_sender(webhook_url: str, payload: dict) -> None:
            raise RuntimeError("backend unavailable")

        with self.assertLogs("agent_service.agents.resources", level="WARNING") as logs:
            await run_resource_generation_task(
                request,
                send_webhook=failing_sender,
                max_webhook_attempts=1,
                webhook_base_delay_seconds=0,
            )

        self.assertIn("Resource generation webhook failed", "\n".join(logs.output))
        self.assertIn("task-resource-9", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
