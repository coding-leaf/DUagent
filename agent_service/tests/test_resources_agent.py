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


# ── generate_resources_with_llm tests ──────────────────────────────


class FakeChatProvider:
    def __init__(self, outputs: list[str] | None = None, should_raise: bool = False) -> None:
        self._outputs = outputs or []
        self._should_raise = should_raise
        self._index = 0
        self.calls: list[list] = []

    async def complete(self, messages):
        self.calls.append(messages)
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        if self._index >= len(self._outputs):
            return "{}"
        result = self._outputs[self._index]
        self._index += 1
        return result


_V1_TYPES = ["document", "mindmap", "reading", "code"]


class GenerateResourcesWithLLMTests(unittest.IsolatedAsyncioTestCase):
    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-1", user_id="u1", course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数", knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    async def test_llm_generates_two_resource_types_with_correct_shape(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        provider = FakeChatProvider(
            outputs=[
                '{"title":"一次函数讲解","description":"基础概念","content":"一次函数是..."}',
                '{"title":"一次函数导图","description":"思维导图","content":"- 定义\\n- 性质"}',
            ]
        )
        result = await generate_resources_with_llm(
            self._request(resource_types=["document", "mindmap"]), provider
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "document")
        self.assertEqual(result[0]["title"], "一次函数讲解")
        self.assertEqual(result[0]["content"], "一次函数是...")
        self.assertEqual(result[0]["chapter"], "函数")
        self.assertEqual(result[0]["knowledge_point"], "一次函数")
        self.assertIn("tags", result[0])
        self.assertEqual(result[1]["type"], "mindmap")

    async def test_llm_returns_none_when_one_resource_fails(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        provider = FakeChatProvider(should_raise=True)
        result = await generate_resources_with_llm(
            self._request(resource_types=["document", "code"]), provider
        )
        self.assertIsNone(result)

    async def test_llm_returns_none_on_invalid_json(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        provider = FakeChatProvider(outputs=["not valid json at all"])
        result = await generate_resources_with_llm(
            self._request(resource_types=["document"]), provider
        )
        self.assertIsNone(result)

    async def test_llm_returns_none_when_provider_is_none(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        result = await generate_resources_with_llm(
            self._request(resource_types=["document"]), None
        )
        self.assertIsNone(result)

    async def test_llm_returns_none_for_video_resource_type(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        provider = FakeChatProvider(outputs=['{"title":"video","content":"x"}'])
        result = await generate_resources_with_llm(
            self._request(resource_types=["document", "video"]), provider
        )
        self.assertIsNone(result)

    async def test_llm_covers_all_requested_types_in_parallel(self) -> None:
        from agent_service.agents.resources import generate_resources_with_llm

        provider = FakeChatProvider(
            outputs=[
                '{"title":"doc","content":"d"}',
                '{"title":"map","content":"m"}',
                '{"title":"read","content":"r"}',
                '{"title":"code","content":"c"}',
            ]
        )
        result = await generate_resources_with_llm(
            self._request(),  # default: all 4 v1 types
            provider,
        )

        self.assertIsNotNone(result)
        types = [r["type"] for r in result]
        self.assertEqual(set(types), set(_V1_TYPES))

    async def test_run_task_uses_llm_resources_and_preserves_webhook_shape(self) -> None:
        from unittest.mock import patch

        from agent_service.agents.resources import run_resource_generation_task

        request = self._request(resource_types=["document"])
        calls = []

        async def fake_sender(webhook_url, payload):
            calls.append(payload)

        class FakeProviders:
            chat = FakeChatProvider(
                outputs=['{"title":"LLM Doc","description":"d","content":"LLM content"}']
            )

        with patch(
            "agent_service.agents.resources.get_ai_providers",
            return_value=FakeProviders(),
        ):
            await run_resource_generation_task(request, send_webhook=fake_sender)

        self.assertEqual(len(calls), 1)
        payload = calls[0]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["task_id"], "task-1")
        resource = payload["result"]["resources"][0]
        self.assertEqual(resource["title"], "LLM Doc")
        self.assertEqual(resource["content"], "LLM content")

    async def test_run_task_falls_back_when_llm_returns_none(self) -> None:
        from unittest.mock import patch

        from agent_service.agents.resources import run_resource_generation_task

        request = self._request(resource_types=["document"])
        calls = []

        async def fake_sender(webhook_url, payload):
            calls.append(payload)

        class FakeProviders:
            chat = FakeChatProvider(should_raise=True)

        with patch(
            "agent_service.agents.resources.get_ai_providers",
            return_value=FakeProviders(),
        ):
            await run_resource_generation_task(request, send_webhook=fake_sender)

        self.assertEqual(len(calls), 1)
        payload = calls[0]
        self.assertEqual(payload["status"], "completed")
        self.assertIn("规则版资源占位内容", payload["result"]["resources"][0]["content"])


class ResourceRAGTests(unittest.IsolatedAsyncioTestCase):
    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-rag-1", user_id="u1", course_id="data-structures",
            webhook_url="https://example.com/webhook",
            chapter="线性表", knowledge_point="顺序存储结构",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    def _fake_embedding_provider(self):
        class FakeEmbedding:
            def __init__(self) -> None:
                self.calls: list[list] = []

            async def embed_texts(self, texts):
                self.calls.append(list(texts))
                return [[0.1, 0.2, 0.3] for _ in texts]

        return FakeEmbedding()

    async def test_build_course_knowledge_context_returns_joined_chunks(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import _build_course_knowledge_context

        embedding = self._fake_embedding_provider()
        chunks = ["线性表是相同类型数据元素的有限序列。", "顺序存储用一组连续地址存放元素。"]

        class FakeVectorStore:
            async def search_course_knowledge(self, course_id, vector, limit=5):
                return [
                    type("_R", (), {"text": t})()
                    for t in chunks
                ]

        with patch(
            "agent_service.memory.vector_store.QdrantVectorStore",
            return_value=FakeVectorStore(),
        ):
            context = await _build_course_knowledge_context(
                self._request(), embedding, limit=5
            )

        self.assertIn("线性表", context)
        self.assertIn("---", context)
        self.assertIn("顺序存储", context)

    async def test_build_course_knowledge_context_returns_empty_when_embedding_is_none(self) -> None:
        from agent_service.agents.resources import _build_course_knowledge_context

        context = await _build_course_knowledge_context(self._request(), None)
        self.assertEqual(context, "")

    async def test_build_course_knowledge_context_returns_empty_on_retrieval_failure(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import _build_course_knowledge_context

        embedding = self._fake_embedding_provider()

        class FailingVectorStore:
            async def search_course_knowledge(self, course_id, vector, limit=5):
                raise RuntimeError("Qdrant unavailable")

        with patch(
            "agent_service.memory.vector_store.QdrantVectorStore",
            return_value=FailingVectorStore(),
        ):
            context = await _build_course_knowledge_context(
                self._request(), embedding, limit=5
            )

        self.assertEqual(context, "")

    async def test_build_course_knowledge_context_returns_empty_with_no_results(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import _build_course_knowledge_context

        embedding = self._fake_embedding_provider()

        class EmptyVectorStore:
            async def search_course_knowledge(self, course_id, vector, limit=5):
                return []

        with patch(
            "agent_service.memory.vector_store.QdrantVectorStore",
            return_value=EmptyVectorStore(),
        ):
            context = await _build_course_knowledge_context(
                self._request(), embedding, limit=5
            )

        self.assertEqual(context, "")

    async def test_run_task_injects_rag_context_into_llm_user_message(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import run_resource_generation_task

        request = self._request(resource_types=["document"])
        calls = []
        chat_calls: list[list] = []

        async def fake_sender(webhook_url, payload):
            calls.append(payload)

        _embedding = self._fake_embedding_provider()

        class FakeVectorStore:
            async def search_course_knowledge(self, course_id, vector, limit=5):
                return [type("_R", (), {"text": "顺序存储的关键是地址连续。"})()]

        class FakeChatProvider:
            def __init__(self) -> None:
                self.calls = []

            async def complete(self, messages):
                chat_calls.extend(messages)
                self.calls.append(messages)
                return '{"title":"LLM Doc","description":"RAG生成","content":"基于顺序存储的内容。"}'

        class FakeProviders:
            chat = FakeChatProvider()
            embedding = _embedding

        with (
            patch("agent_service.agents.resources.get_ai_providers", return_value=FakeProviders()),
            patch("agent_service.memory.vector_store.QdrantVectorStore", return_value=FakeVectorStore()),
        ):
            await run_resource_generation_task(request, send_webhook=fake_sender)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["status"], "completed")
        user_msg = str(chat_calls[1])
        self.assertIn("顺序存储的关键是地址连续。", user_msg)


if __name__ == "__main__":
    unittest.main()
