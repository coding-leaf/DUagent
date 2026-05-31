"""Phase 0 tests: dataclass & interface definitions for multi-agent resources workflow.

Tests in this module are organized by Phase marker in class names
(TestPhase0_*, TestPhase1_*, ...) so -k "TestPhaseX" selects exactly the
right set.
"""

import json
import unittest

from agent_service.agents.resources_plan import (
    ResourcePlan,
    ResourceTaskSpec,
    build_rule_based_plan,
)
from agent_service.agents.resources_agents import (
    ResourceResult,
    _build_skeleton_result,
)
from agent_service.schemas.resources import ResourceGenerateRequest


class TestPhase0_ResourcePlan(unittest.TestCase):
    """T0.1-T0.5: ResourceTaskSpec / ResourcePlan dataclass and build_rule_based_plan."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p0-1",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    # ── T0.1 ──────────────────────────────────────────────────────
    def test_resource_task_spec_construction(self) -> None:
        spec = ResourceTaskSpec(
            resource_type="document",
            focus_points=["定义", "性质"],
            suggested_structure="概念定义 → 公式 → 例题",
            output_format_hint="markdown",
        )
        self.assertEqual(spec.resource_type, "document")
        self.assertEqual(spec.focus_points, ["定义", "性质"])
        self.assertEqual(spec.suggested_structure, "概念定义 → 公式 → 例题")
        self.assertEqual(spec.output_format_hint, "markdown")

    # ── T0.2 ──────────────────────────────────────────────────────
    def test_resource_plan_construction(self) -> None:
        task = ResourceTaskSpec(
            resource_type="document",
            focus_points=["一次函数"],
            suggested_structure="概念 → 例题",
            output_format_hint="markdown",
        )
        plan = ResourcePlan(
            overview="一次函数教学资源",
            tasks=[task],
            knowledge_summary="一次函数的基本概念和应用",
        )
        self.assertEqual(plan.overview, "一次函数教学资源")
        self.assertEqual(len(plan.tasks), 1)
        self.assertEqual(plan.tasks[0].resource_type, "document")
        self.assertIsInstance(plan.knowledge_summary, str)
        self.assertTrue(len(plan.knowledge_summary) > 0)

    # ── T0.3 ──────────────────────────────────────────────────────
    def test_build_rule_based_plan_all_four_types(self) -> None:
        plan = build_rule_based_plan(self._request())  # default: all 4 v1 types
        self.assertEqual(len(plan.tasks), 4)
        types = {t.resource_type for t in plan.tasks}
        self.assertEqual(types, {"document", "mindmap", "reading", "code"})

    # ── T0.4 ──────────────────────────────────────────────────────
    def test_build_rule_based_plan_specified_types(self) -> None:
        request = self._request(resource_types=["document", "code"])
        plan = build_rule_based_plan(request)
        self.assertEqual(len(plan.tasks), 2)
        types = {t.resource_type for t in plan.tasks}
        self.assertEqual(types, {"document", "code"})

    # ── T0.5 ──────────────────────────────────────────────────────
    def test_build_rule_based_plan_filters_video(self) -> None:
        """video is a reserved type — it must NOT appear in the rule-based plan."""
        request = self._request(resource_types=["document", "video", "mindmap"])
        plan = build_rule_based_plan(request)
        types = {t.resource_type for t in plan.tasks}
        self.assertNotIn("video", types)
        self.assertIn("document", types)
        self.assertIn("mindmap", types)


class TestPhase0_ResourceResult(unittest.TestCase):
    """T0.6-T0.9: ResourceResult dataclass, to_payload_dict, skeleton result."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p0-2",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    # ── T0.6 ──────────────────────────────────────────────────────
    def test_to_payload_dict_keys_match_skeleton_payload(self) -> None:
        """The webhook payload dict must have the same keys as _build_resource_payload."""
        from agent_service.agents.resources import _build_resource_payload

        request = self._request(resource_types=["document"])
        skeleton_dict = _build_resource_payload(request, "document")

        result = ResourceResult(
            title="测试标题",
            type="document",
            description="测试描述",
            content="测试内容",
            chapter="函数",
            knowledge_point="一次函数",
            tags=["函数", "一次函数", "document"],
            generated_by="llm",
            fallback_reason=None,
            is_skeleton=False,
        )
        payload = result.to_payload_dict()
        self.assertEqual(set(payload.keys()), set(skeleton_dict.keys()))
        expected_keys = {"title", "type", "description", "content", "chapter", "knowledge_point", "tags"}
        self.assertEqual(set(payload.keys()), expected_keys)

    # ── T0.7 ──────────────────────────────────────────────────────
    def test_build_skeleton_result_is_skeleton_true(self) -> None:
        result = _build_skeleton_result(
            self._request(), "document", fallback_reason="agent_failed"
        )
        self.assertTrue(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback")
        self.assertEqual(result.fallback_reason, "agent_failed")
        self.assertEqual(result.type, "document")
        self.assertIn("规则版", result.content)

    # ── T0.8 ──────────────────────────────────────────────────────
    def test_fallback_mermaid_is_not_skeleton(self) -> None:
        """Mermaid fallback producing a valid markdown tree is NOT a skeleton failure."""
        result = ResourceResult(
            title="一次函数导图",
            type="mindmap",
            description="Mermaid 无效，降级为 markdown 树",
            content="- 一次函数\n  - 定义\n  - 性质",
            chapter="函数",
            knowledge_point="一次函数",
            tags=["函数", "一次函数", "mindmap"],
            generated_by="fallback_mermaid",
            fallback_reason="mermaid_invalid",
            is_skeleton=False,
        )
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback_mermaid")
        self.assertNotEqual(result.generated_by, "fallback")

    # ── T0.9 ──────────────────────────────────────────────────────
    def test_to_payload_dict_does_not_leak_internal_fields(self) -> None:
        """Webhook payload must never expose generated_by / fallback_reason / is_skeleton."""
        result = ResourceResult(
            title="测试",
            type="document",
            description="desc",
            content="content",
            chapter="函数",
            knowledge_point="一次函数",
            tags=["tag"],
            generated_by="llm",
            fallback_reason=None,
            is_skeleton=False,
        )
        payload = result.to_payload_dict()
        self.assertNotIn("generated_by", payload)
        self.assertNotIn("fallback_reason", payload)
        self.assertNotIn("is_skeleton", payload)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Planner — LLM + Rule-Based Fallback
# ═══════════════════════════════════════════════════════════════════════════════


class FakeChatProvider:
    """Fake chat provider returning canned LLM responses or raising on demand.

    Accepts **kwargs for compatibility with AgentScopeChatProvider.complete()
    which passes structured_model=... as an optional kwarg.
    """

    def __init__(self, outputs: list[str] | None = None, should_raise: bool = False) -> None:
        self._outputs = outputs or []
        self._should_raise = should_raise
        self._index = 0

    async def complete(self, messages, **kwargs) -> str:
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        if self._index >= len(self._outputs):
            return "{}"
        result = self._outputs[self._index]
        self._index += 1
        return result


_VALID_PLAN_JSON = """```json
{
    "overview": "讲解一次函数的基本概念、图像性质和应用",
    "knowledge_summary": "一次函数 y=kx+b 是中学代数的基础，核心是理解斜率和截距的含义。",
    "tasks": [
        {
            "resource_type": "document",
            "focus_points": ["一次函数定义", "斜率与截距"],
            "suggested_structure": "概念定义 → 公式推导 → 图像性质 → 例题",
            "output_format_hint": "markdown 格式的长文讲解"
        },
        {
            "resource_type": "mindmap",
            "focus_points": ["一次函数知识体系"],
            "suggested_structure": "一次函数 → 定义/性质/图像/应用",
            "output_format_hint": "Mermaid mindmap 语法"
        }
    ]
}
```"""


class TestPhase1_Planner(unittest.IsolatedAsyncioTestCase):
    """T1.1-T1.6: generate_plan_with_llm() — LLM Planner with None-on-failure."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p1-1",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
            resource_types=["document", "mindmap"],
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    # ── T1.1 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_returns_resource_plan(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        provider = FakeChatProvider(outputs=[_VALID_PLAN_JSON])
        plan = await generate_plan_with_llm(
            self._request(), provider, course_knowledge_context="一次函数是..."
        )
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, ResourcePlan)
        self.assertEqual(len(plan.tasks), 2)
        task_types = {t.resource_type for t in plan.tasks}
        self.assertEqual(task_types, {"document", "mindmap"})

    # ── T1.2 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_task_spec_fields_non_empty(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        provider = FakeChatProvider(outputs=[_VALID_PLAN_JSON])
        plan = await generate_plan_with_llm(
            self._request(), provider, course_knowledge_context=""
        )
        for task in plan.tasks:
            self.assertTrue(len(task.focus_points) > 0,
                            f"focus_points empty for {task.resource_type}")
            self.assertTrue(len(task.suggested_structure) > 0,
                            f"suggested_structure empty for {task.resource_type}")
            self.assertTrue(len(task.output_format_hint) > 0,
                            f"output_format_hint empty for {task.resource_type}")

    # ── T1.3 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_returns_none_on_invalid_json(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        provider = FakeChatProvider(outputs=["not valid json at all {][}"])
        result = await generate_plan_with_llm(
            self._request(), provider, course_knowledge_context=""
        )
        self.assertIsNone(result)

    # ── T1.4 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_returns_none_when_provider_is_none(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        result = await generate_plan_with_llm(
            self._request(), None, course_knowledge_context=""
        )
        self.assertIsNone(result)

    # ── T1.5 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_returns_none_when_llm_raises(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        provider = FakeChatProvider(should_raise=True)
        result = await generate_plan_with_llm(
            self._request(), provider, course_knowledge_context=""
        )
        self.assertIsNone(result)

    # ── T1.6 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_only_generates_requested_types(self) -> None:
        from agent_service.agents.resources_plan import generate_plan_with_llm

        provider = FakeChatProvider(outputs=[_VALID_PLAN_JSON])
        plan = await generate_plan_with_llm(
            self._request(resource_types=["document", "mindmap"]),
            provider,
            course_knowledge_context="",
        )
        task_types = {t.resource_type for t in plan.tasks}
        self.assertEqual(task_types, {"document", "mindmap"})

    # ── T1.7 ──────────────────────────────────────────────────────
    async def test_generate_plan_with_llm_backfills_missing_types(self) -> None:
        """LLM only returns 2 of 3 requested types — plan must cover all 3."""
        from agent_service.agents.resources_plan import generate_plan_with_llm

        # Valid JSON but only covers document + mindmap (missing code)
        partial_json = """```json
{
    "overview": "部分覆盖",
    "knowledge_summary": "",
    "tasks": [
        {"resource_type": "document", "focus_points": ["定义"], "suggested_structure": "概念 → 例题", "output_format_hint": "markdown"},
        {"resource_type": "mindmap", "focus_points": [], "suggested_structure": "主题 → 分支", "output_format_hint": "Mermaid mindmap"}
    ]
}
```"""
        provider = FakeChatProvider(outputs=[partial_json])
        plan = await generate_plan_with_llm(
            self._request(resource_types=["document", "mindmap", "code"]),
            provider,
            course_knowledge_context="",
        )

        self.assertIsNotNone(plan)
        task_types = {t.resource_type for t in plan.tasks}
        self.assertEqual(task_types, {"document", "mindmap", "code"},
                         "Missing requested type should be backfilled")

        # The mindmap task had empty focus_points — verify backfill
        mindmap_task = next(t for t in plan.tasks if t.resource_type == "mindmap")
        self.assertTrue(len(mindmap_task.focus_points) > 0,
                        "Empty focus_points should be backfilled")
        self.assertEqual(mindmap_task.focus_points, ["一次函数"])


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: DocumentAgent + CodeAgent
# ═══════════════════════════════════════════════════════════════════════════════

_DOC_LLM_OUTPUT = """```json
{
    "title": "一次函数概念讲解",
    "description": "介绍一次函数的定义、图像性质与例题",
    "content": "## 一次函数\\n\\n### 定义\\n形如 y = kx + b（k, b 为常数，k ≠ 0）的函数称为一次函数。\\n\\n### 性质\\n- k > 0 时，y 随 x 增大而增大\\n- k < 0 时，y 随 x 增大而减小\\n\\n### 例题\\n已知一次函数经过 (0, 3) 和 (2, 7)，求解析式。"
}
```"""

_CODE_LLM_OUTPUT = json.dumps({
    "title": "一次函数计算示例",
    "description": "实现一次函数求值",
    "content": (
        "## 问题\n计算一次函数 y = 2x + 3 在 x = 5 时的值。\n\n"
        "## 算法思路\n直接代入公式计算。\n\n"
        "## 代码\n"
        "#include <stdio.h>\n"
        "int main() {\n"
        "    double k = 2.0, b = 3.0, x = 5.0;\n"
        "    double y = k * x + b;\n"
        "    printf(\"y = %.2f\", y);\n"
        "    return 0;\n"
        "}\n\n"
        "## 复杂度\n时间 O(1)，空间 O(1)。"
    ),
}, ensure_ascii=False)
_CODE_LLM_OUTPUT = "```json\n" + _CODE_LLM_OUTPUT + "\n```"


class TestPhase2_Agents(unittest.IsolatedAsyncioTestCase):
    """T2.1-T2.9: DocumentAgent and CodeAgent — independent LLM calls."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p2-1",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    def _task_spec(self, **kwargs) -> ResourceTaskSpec:
        defaults = dict(
            resource_type="document",
            focus_points=["一次函数定义", "图像性质"],
            suggested_structure="概念定义 → 公式推导 → 例题",
            output_format_hint="markdown 格式的长文讲解",
        )
        defaults.update(kwargs)
        return ResourceTaskSpec(**defaults)

    # ── T2.1 ──────────────────────────────────────────────────────
    async def test_document_agent_generate_returns_result(self) -> None:
        from agent_service.agents.resources_agents import DocumentAgent

        agent = DocumentAgent()
        provider = FakeChatProvider(outputs=[_DOC_LLM_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="document"),
            course_knowledge_context="一次函数 y=kx+b...",
            chat_provider=provider,
        )
        self.assertIsNotNone(result)
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "llm")
        self.assertEqual(result.type, "document")
        self.assertTrue(len(result.content) > 0)

    # ── T2.2 ──────────────────────────────────────────────────────
    async def test_document_agent_content_has_markdown_structure(self) -> None:
        from agent_service.agents.resources_agents import DocumentAgent

        agent = DocumentAgent()
        provider = FakeChatProvider(outputs=[_DOC_LLM_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="document"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        # Content should have markdown headings or paragraphs
        self.assertIn("##", result.content)

    # ── T2.3 ──────────────────────────────────────────────────────
    async def test_code_agent_generate_returns_result(self) -> None:
        from agent_service.agents.resources_agents import CodeAgent

        agent = CodeAgent()
        provider = FakeChatProvider(outputs=[_CODE_LLM_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="code"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertIsNotNone(result)
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "llm")
        self.assertEqual(result.type, "code")
        self.assertIsInstance(result.content, str)

    # ── T2.4 ──────────────────────────────────────────────────────
    async def test_code_agent_content_has_c_code(self) -> None:
        """CodeAgent content must contain recognizable C code structure."""
        from agent_service.agents.resources_agents import CodeAgent

        agent = CodeAgent()
        provider = FakeChatProvider(outputs=[_CODE_LLM_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="code"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertIn("#include", result.content)

    # ── T2.5 ──────────────────────────────────────────────────────
    async def test_document_agent_fallback_on_llm_error(self) -> None:
        from agent_service.agents.resources_agents import DocumentAgent

        agent = DocumentAgent()
        provider = FakeChatProvider(should_raise=True)
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="document"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertTrue(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback")
        self.assertEqual(result.fallback_reason, "agent_failed")
        self.assertEqual(result.type, "document")
        self.assertIn("规则版", result.content)

    # ── T2.6 ──────────────────────────────────────────────────────
    async def test_code_agent_fallback_on_llm_error(self) -> None:
        from agent_service.agents.resources_agents import CodeAgent

        agent = CodeAgent()
        provider = FakeChatProvider(should_raise=True)
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="code"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertTrue(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback")
        self.assertEqual(result.fallback_reason, "agent_failed")

    # ── T2.7 ──────────────────────────────────────────────────────
    def test_document_agent_resource_type(self) -> None:
        from agent_service.agents.resources_agents import DocumentAgent

        agent = DocumentAgent()
        self.assertEqual(agent.resource_type, "document")

    # ── T2.8 ──────────────────────────────────────────────────────
    def test_code_agent_resource_type(self) -> None:
        from agent_service.agents.resources_agents import CodeAgent

        agent = CodeAgent()
        self.assertEqual(agent.resource_type, "code")

    # ── T2.9 ──────────────────────────────────────────────────────
    async def test_skeleton_fallback_to_payload_dict_is_valid(self) -> None:
        """Skeleton ResourceResult payload dict must have complete keys and non-empty content."""
        from agent_service.agents.resources_agents import DocumentAgent

        agent = DocumentAgent()
        provider = FakeChatProvider(should_raise=True)
        result = await agent.generate(
            self._request(),
            self._task_spec(),
            course_knowledge_context="",
            chat_provider=provider,
        )
        payload = result.to_payload_dict()
        expected_keys = {"title", "type", "description", "content", "chapter", "knowledge_point", "tags"}
        self.assertEqual(set(payload.keys()), expected_keys)
        self.assertTrue(len(payload["content"]) > 0)
        self.assertTrue(len(payload["title"]) > 0)
        self.assertTrue(len(payload["description"]) > 0)

    # ── T2.10 ─────────────────────────────────────────────────────
    async def test_code_agent_handles_nested_fences_in_content(self) -> None:
        """CodeAgent must parse JSON whose content field contains ``` fences.

        This simulates real LLM output where the code resource's content
        includes markdown code blocks. The parser must use the outer
        ```json fence, not the inner ```c fence.
        """
        from agent_service.agents.resources_agents import CodeAgent

        # Build a JSON payload whose content field contains ``` fences —
        # exactly what a real LLM would produce for a code resource.
        nested_json = json.dumps({
            "title": "一次函数代码",
            "description": "C 语言实现",
            "content": "## 代码\n```c\n#include <stdio.h>\nint main() {\n  return 0;\n}\n```",
        }, ensure_ascii=False)
        nested_output = "```json\n" + nested_json + "\n```"

        agent = CodeAgent()
        provider = FakeChatProvider(outputs=[nested_output])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="code"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertFalse(result.is_skeleton,
                          "CodeAgent fell back to skeleton — nested fence parse failed")
        self.assertEqual(result.generated_by, "llm")
        self.assertIn("#include", result.content)

    # ── T2.11 ─────────────────────────────────────────────────────
    def test_parse_resource_json_repairs_unescaped_content_newlines(self) -> None:
        from agent_service.agents.resources_agents import _parse_resource_json

        raw = '''{
  "title": "一次函数讲义",
  "description": "测试",
  "content": "第一行
第二行
第三行",
  "tags": ["函数", "一次函数"]
}'''

        data = _parse_resource_json(raw)

        self.assertEqual(data["title"], "一次函数讲义")
        self.assertIn("第二行", data["content"])


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: ReadingAgent + MindmapAgent
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_MERMAID = """mindmap
  root((一次函数))
    定义
      形如 y = kx + b
    性质
      图像是一条直线
"""

_VALID_MERMAID_OUTPUT = json.dumps({
    "title": "一次函数知识导图",
    "description": "一次函数核心概念导图",
    "content": _VALID_MERMAID,
}, ensure_ascii=False)
_VALID_MERMAID_OUTPUT = "```json\n" + _VALID_MERMAID_OUTPUT + "\n```"

_INVALID_MERMAID_OUTPUT = json.dumps({
    "title": "一次函数知识导图",
    "description": "一次函数核心概念导图",
    "content": "这是普通文本，不是 Mermaid mindmap。",
}, ensure_ascii=False)
_INVALID_MERMAID_OUTPUT = "```json\n" + _INVALID_MERMAID_OUTPUT + "\n```"

_MARKDOWN_TREE_OUTPUT = json.dumps({
    "title": "一次函数知识导图",
    "description": "一次函数 markdown 树",
    "content": "- 一次函数\n  - 定义\n    - 形如 y = kx + b\n  - 性质\n    - 图像是一条直线",
}, ensure_ascii=False)
_MARKDOWN_TREE_OUTPUT = "```json\n" + _MARKDOWN_TREE_OUTPUT + "\n```"

_READING_LLM_OUTPUT = json.dumps({
    "title": "一次函数拓展阅读",
    "description": "从线性模型理解一次函数",
    "content": "## 拓展阅读\n\n一次函数可以看作最基础的线性模型，在物理和数据分析中都有应用。\n\n## 思考题\n为什么斜率能描述变化率？",
}, ensure_ascii=False)
_READING_LLM_OUTPUT = "```json\n" + _READING_LLM_OUTPUT + "\n```"


class TestPhase3_MermaidAndAgents(unittest.IsolatedAsyncioTestCase):
    """T3.1-T3.8: ReadingAgent and MindmapAgent with Mermaid fallback."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p3-1",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    def _task_spec(self, **kwargs) -> ResourceTaskSpec:
        defaults = dict(
            resource_type="mindmap",
            focus_points=["一次函数定义", "图像性质"],
            suggested_structure="核心主题 → 定义/性质/应用",
            output_format_hint="Mermaid mindmap 语法",
        )
        defaults.update(kwargs)
        return ResourceTaskSpec(**defaults)

    # ── T3.1 ──────────────────────────────────────────────────────
    def test_validate_mermaid_mindmap_accepts_valid_mindmap(self) -> None:
        from agent_service.agents.resources_mermaid import validate_mermaid_mindmap

        self.assertTrue(validate_mermaid_mindmap(_VALID_MERMAID))

    # ── T3.2 ──────────────────────────────────────────────────────
    def test_validate_mermaid_mindmap_rejects_invalid_inputs(self) -> None:
        from agent_service.agents.resources_mermaid import validate_mermaid_mindmap

        self.assertFalse(validate_mermaid_mindmap(""))
        self.assertFalse(validate_mermaid_mindmap("graph TD\n  A --> B"))
        self.assertFalse(validate_mermaid_mindmap("说明文字\nmindmap\n  root((一次函数))\n    定义"))
        self.assertFalse(validate_mermaid_mindmap("mindmap\n  root((一次函数))"))
        self.assertFalse(validate_mermaid_mindmap("mindmap\n  一次函数\n    定义"))

    # ── T3.3 ──────────────────────────────────────────────────────
    async def test_mindmap_agent_generate_returns_valid_mermaid(self) -> None:
        from agent_service.agents.resources_agents import MindmapAgent

        agent = MindmapAgent()
        provider = FakeChatProvider(outputs=[_VALID_MERMAID_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="mindmap"),
            course_knowledge_context="一次函数 y=kx+b...",
            chat_provider=provider,
        )
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "llm")
        self.assertEqual(result.type, "mindmap")
        self.assertIn("mindmap", result.content)

    # ── T3.4 ──────────────────────────────────────────────────────
    async def test_mindmap_agent_falls_back_to_markdown_tree_when_mermaid_invalid(self) -> None:
        from agent_service.agents.resources_agents import MindmapAgent

        agent = MindmapAgent()
        provider = FakeChatProvider(outputs=[_INVALID_MERMAID_OUTPUT, _MARKDOWN_TREE_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="mindmap"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback_mermaid")
        self.assertEqual(result.fallback_reason, "mermaid_invalid")
        self.assertTrue(result.content.startswith("- "))

    # ── T3.5 ──────────────────────────────────────────────────────
    async def test_mindmap_agent_falls_back_to_skeleton_when_mermaid_and_markdown_fail(self) -> None:
        from agent_service.agents.resources_agents import MindmapAgent

        agent = MindmapAgent()
        provider = FakeChatProvider(outputs=[_INVALID_MERMAID_OUTPUT, "not json"])
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="mindmap"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertTrue(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback")
        self.assertIn("mermaid_and_markdown", result.fallback_reason)

    # ── T3.6 ──────────────────────────────────────────────────────
    async def test_reading_agent_generate_returns_result(self) -> None:
        from agent_service.agents.resources_agents import ReadingAgent

        agent = ReadingAgent()
        provider = FakeChatProvider(outputs=[_READING_LLM_OUTPUT])
        result = await agent.generate(
            self._request(),
            self._task_spec(
                resource_type="reading",
                suggested_structure="背景知识 → 应用 → 思考题",
                output_format_hint="markdown 格式的拓展阅读",
            ),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertFalse(result.is_skeleton)
        self.assertEqual(result.generated_by, "llm")
        self.assertEqual(result.type, "reading")
        self.assertIn("拓展阅读", result.content)

    # ── T3.7 ──────────────────────────────────────────────────────
    async def test_reading_agent_fallback_on_llm_error(self) -> None:
        from agent_service.agents.resources_agents import ReadingAgent

        agent = ReadingAgent()
        provider = FakeChatProvider(should_raise=True)
        result = await agent.generate(
            self._request(),
            self._task_spec(resource_type="reading"),
            course_knowledge_context="",
            chat_provider=provider,
        )
        self.assertTrue(result.is_skeleton)
        self.assertEqual(result.generated_by, "fallback")
        self.assertEqual(result.fallback_reason, "agent_failed")

    # ── T3.8 ──────────────────────────────────────────────────────
    def test_mindmap_agent_resource_type(self) -> None:
        from agent_service.agents.resources_agents import MindmapAgent

        agent = MindmapAgent()
        self.assertEqual(agent.resource_type, "mindmap")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4: Aggregator
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase4_Aggregator(unittest.TestCase):
    """T4.1-T4.9: aggregate_resource_results() — merge + validate + payload."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        d = dict(task_id="t4", user_id="u1", course_id="c1",
                 webhook_url="https://x.com/hook",
                 chapter="函数", knowledge_point="一次函数")
        d.update(kwargs)
        return ResourceGenerateRequest(**d)

    def _result(self, **kwargs) -> ResourceResult:
        """Build a test ResourceResult with sensible defaults."""
        d = dict(title="T", type="document", description="D", content="C",
                 chapter="函数", knowledge_point="一次函数",
                 tags=["函数", "一次函数", "document"],
                 generated_by="llm", fallback_reason=None, is_skeleton=False)
        d.update(kwargs)
        return ResourceResult(**d)

    def _plan(self, **kwargs) -> ResourcePlan:
        d = dict(overview="plan", knowledge_summary="ks",
                 tasks=[ResourceTaskSpec("document", ["一次函数"], "结构", "markdown")])
        d.update(kwargs)
        return ResourcePlan(**d)

    # ── T4.1 ──────────────────────────────────────────────────────
    def test_all_llm_returns_completed_payload(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [
            self._result(type="document", generated_by="llm", is_skeleton=False),
            self._result(type="code", generated_by="llm", is_skeleton=False),
        ]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(payload["result"]["resources"]), 2)

    # ── T4.2 ──────────────────────────────────────────────────────
    def test_mixed_llm_and_fallback_mermaid_returns_completed(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [
            self._result(type="document", generated_by="llm", is_skeleton=False),
            self._result(type="code", generated_by="llm", is_skeleton=False),
            self._result(type="mindmap", generated_by="fallback_mermaid",
                         fallback_reason="mermaid_invalid", is_skeleton=False,
                         content="- 主题\n  - 分支"),
        ]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["result"]["resources"]), 3,
                         "fallback_mermaid must not be excluded")

    # ── T4.3 ──────────────────────────────────────────────────────
    def test_all_skeleton_returns_none(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [
            self._result(type="document", generated_by="fallback", is_skeleton=True),
            self._result(type="code", generated_by="fallback", is_skeleton=True),
        ]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNone(payload)

    # ── T4.4 ──────────────────────────────────────────────────────
    def test_single_mindmap_mermaid_fallback_not_all_failed(self) -> None:
        """Only mindmap requested; Mermaid invalid but markdown tree succeeded."""
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [
            self._result(type="mindmap", generated_by="fallback_mermaid",
                         fallback_reason="mermaid_invalid", is_skeleton=False,
                         content="- 一次函数\n  - 定义\n  - 性质"),
        ]
        payload = aggregate_resource_results(
            self._request(resource_types=["mindmap"]), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNotNone(payload,
                             "Single mindmap with valid fallback_mermaid must NOT be treated as all-failed")
        self.assertEqual(len(payload["result"]["resources"]), 1)

    # ── T4.5 ──────────────────────────────────────────────────────
    def test_empty_results_returns_none(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        payload = aggregate_resource_results(
            self._request(), self._plan(),
            [],  # type: ignore[arg-type]
        )
        self.assertIsNone(payload)

    # ── T4.6 ──────────────────────────────────────────────────────
    def test_empty_content_is_backfilled(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [self._result(type="document", content="", generated_by="llm",
                                is_skeleton=False)]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNotNone(payload)
        r = payload["result"]["resources"][0]
        self.assertTrue(len(r["content"]) > 0, "Empty content must be backfilled")

    # ── T4.7 ──────────────────────────────────────────────────────
    def test_empty_title_description_backfilled(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [self._result(type="document", title="", description="",
                                generated_by="llm", is_skeleton=False)]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertIsNotNone(payload)
        r = payload["result"]["resources"][0]
        self.assertTrue(len(r["title"]) > 0)
        self.assertTrue(len(r["description"]) > 0)

    # ── T4.8 ──────────────────────────────────────────────────────
    def test_payload_resources_have_no_internal_fields(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [self._result(type="document", generated_by="llm", is_skeleton=False)]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        r = payload["result"]["resources"][0]
        self.assertNotIn("generated_by", r)
        self.assertNotIn("fallback_reason", r)
        self.assertNotIn("is_skeleton", r)

    # ── T4.9 ──────────────────────────────────────────────────────
    def test_payload_outer_fields_complete(self) -> None:
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [self._result()]
        payload = aggregate_resource_results(
            self._request(), self._plan(),
            results,  # type: ignore[arg-type]
        )
        self.assertEqual(payload["task_id"], "t4")
        self.assertEqual(payload["task_type"], "resource_generation")
        self.assertEqual(payload["status"], "completed")
        self.assertIn("result", payload)
        self.assertIn("resources", payload["result"])

    # ── T4.10 ─────────────────────────────────────────────────────
    def test_aggregator_normalizes_dirty_tags(self) -> None:
        """Aggregator must overwrite dirty/empty tags with normalized values."""
        from agent_service.agents.resources_aggregator import aggregate_resource_results

        results = [
            self._result(type="document", tags=["", "", "document"],
                         generated_by="llm", is_skeleton=False),
        ]
        payload = aggregate_resource_results(
            self._request(chapter="函数", knowledge_point="一次函数"),
            self._plan(),
            results,  # type: ignore[arg-type]
        )
        tags = payload["result"]["resources"][0]["tags"]
        self.assertEqual(len(tags), 3)
        self.assertNotIn("", tags)
        self.assertEqual(tags, ["函数", "一次函数", "document"])


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5: Workflow Orchestrator Integration
# ═══════════════════════════════════════════════════════════════════════════════

def _json_output(title: str, description: str, content: str) -> str:
    return "```json\n" + json.dumps({
        "title": title,
        "description": description,
        "content": content,
    }, ensure_ascii=False) + "\n```"


def _plan_output(resource_types: list[str] | None = None) -> str:
    resource_types = resource_types or ["document", "mindmap", "reading", "code"]
    tasks = [
        {
            "resource_type": rt,
            "focus_points": ["一次函数"],
            "suggested_structure": f"{rt} structure",
            "output_format_hint": "Mermaid mindmap 语法" if rt == "mindmap" else "markdown",
        }
        for rt in resource_types
    ]
    return "```json\n" + json.dumps({
        "overview": "一次函数资源生成计划",
        "knowledge_summary": "一次函数 y=kx+b",
        "tasks": tasks,
    }, ensure_ascii=False) + "\n```"


_MA_DOCUMENT_OUTPUT = _json_output("一次函数讲解", "讲解", "## 知识讲解\n一次函数是线性函数。")
_MA_MINDMAP_OUTPUT = _json_output(
    "一次函数导图",
    "导图",
    "mindmap\n  root((一次函数))\n    定义\n      y = kx + b",
)
_MA_INVALID_MINDMAP_OUTPUT = _json_output("坏导图", "坏导图", "不是 Mermaid")
_MA_MARKDOWN_TREE_OUTPUT = _json_output("一次函数树", "树", "- 一次函数\n  - 定义\n  - 性质")
_MA_READING_OUTPUT = _json_output("一次函数拓展阅读", "阅读", "## 拓展阅读\n线性模型应用。")
_MA_CODE_OUTPUT = _json_output("一次函数代码", "代码", "## 代码\n```c\nint main(){return 0;}\n```")


class _FakeProviders:
    def __init__(self, chat=None, embedding=None) -> None:
        self.chat = chat
        self.embedding = embedding


class TestPhase5_Workflow(unittest.IsolatedAsyncioTestCase):
    """T5.1-T5.13: multi-agent workflow orchestration and integration."""

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        defaults = dict(
            task_id="task-p5-1",
            user_id="u1",
            course_id="c1",
            webhook_url="https://example.com/webhook",
            chapter="函数",
            knowledge_point="一次函数",
        )
        defaults.update(kwargs)
        return ResourceGenerateRequest(**defaults)

    def _success_provider(self) -> FakeChatProvider:
        return FakeChatProvider(outputs=[
            _plan_output(),
            _MA_DOCUMENT_OUTPUT,
            _MA_MINDMAP_OUTPUT,
            _MA_READING_OUTPUT,
            _MA_CODE_OUTPUT,
        ])

    # ── T5.1 ──────────────────────────────────────────────────────
    async def test_workflow_all_success_returns_completed_payload(self) -> None:
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        payload = await run_multi_agent_resource_workflow(
            self._request(), self._success_provider(), embedding_provider=None
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(payload["result"]["resources"]), 4)
        self.assertEqual(
            {r["type"] for r in payload["result"]["resources"]},
            {"document", "mindmap", "reading", "code"},
        )

    # ── T5.2 ──────────────────────────────────────────────────────
    async def test_workflow_single_resource_failure_uses_local_skeleton(self) -> None:
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        provider = FakeChatProvider(outputs=[
            _plan_output(),
            _MA_DOCUMENT_OUTPUT,
            "not json",  # mindmap Mermaid call fails
            "also not json",  # mindmap markdown fallback fails
            _MA_READING_OUTPUT,
            _MA_CODE_OUTPUT,
        ])
        payload = await run_multi_agent_resource_workflow(
            self._request(), provider, embedding_provider=None
        )
        resources = payload["result"]["resources"]
        self.assertEqual(len(resources), 4)
        mindmap = next(r for r in resources if r["type"] == "mindmap")
        self.assertIn("规则版资源占位内容", mindmap["content"])

    # ── T5.3 ──────────────────────────────────────────────────────
    async def test_workflow_planner_failure_uses_rule_based_plan(self) -> None:
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        provider = FakeChatProvider(outputs=[
            "not json",
            _MA_DOCUMENT_OUTPUT,
            _MA_MINDMAP_OUTPUT,
            _MA_READING_OUTPUT,
            _MA_CODE_OUTPUT,
        ])
        payload = await run_multi_agent_resource_workflow(
            self._request(), provider, embedding_provider=None
        )
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["result"]["resources"]), 4)

    # ── T5.4 ──────────────────────────────────────────────────────
    async def test_workflow_mermaid_invalid_uses_markdown_tree(self) -> None:
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        provider = FakeChatProvider(outputs=[
            _plan_output(),
            _MA_DOCUMENT_OUTPUT,
            _MA_INVALID_MINDMAP_OUTPUT,
            _MA_MARKDOWN_TREE_OUTPUT,
            _MA_READING_OUTPUT,
            _MA_CODE_OUTPUT,
        ])
        payload = await run_multi_agent_resource_workflow(
            self._request(), provider, embedding_provider=None
        )
        mindmap = next(r for r in payload["result"]["resources"] if r["type"] == "mindmap")
        self.assertTrue(mindmap["content"].startswith("- "))

    # ── T5.5 ──────────────────────────────────────────────────────
    async def test_run_task_all_multi_agent_failed_then_old_llm_then_skeleton(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import run_resource_generation_task

        calls = []
        request = self._request(resource_types=["document"])

        async def fake_sender(url, payload):
            calls.append(payload)

        with (
            patch("agent_service.agents.resources.get_ai_providers",
                  return_value=_FakeProviders(chat=FakeChatProvider(should_raise=True), embedding=None)),
        ):
            await run_resource_generation_task(request, send_webhook=fake_sender)

        self.assertEqual(calls[0]["status"], "completed")
        self.assertIn("规则版资源占位内容", calls[0]["result"]["resources"][0]["content"])

    # ── T5.6 ──────────────────────────────────────────────────────
    async def test_workflow_payload_shape_matches_skeleton_payload(self) -> None:
        from agent_service.agents.resources import build_resource_generation_result
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        request = self._request(resource_types=["document"])
        payload = await run_multi_agent_resource_workflow(
            request,
            FakeChatProvider(outputs=[_plan_output(["document"]), _MA_DOCUMENT_OUTPUT]),
            embedding_provider=None,
        )
        skeleton = build_resource_generation_result(request)
        self.assertEqual(set(payload.keys()), set(skeleton.keys()))
        self.assertEqual(
            set(payload["result"]["resources"][0].keys()),
            set(skeleton["result"]["resources"][0].keys()),
        )
        self.assertNotIn("generated_by", payload["result"]["resources"][0])

    # ── T5.7 ──────────────────────────────────────────────────────
    async def test_run_task_chat_provider_none_uses_existing_fallback_chain(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import run_resource_generation_task

        calls = []

        async def fake_sender(url, payload):
            calls.append(payload)

        with patch("agent_service.agents.resources.get_ai_providers",
                   return_value=_FakeProviders(chat=None, embedding=None)):
            await run_resource_generation_task(
                self._request(resource_types=["document"]), send_webhook=fake_sender
            )
        self.assertEqual(calls[0]["status"], "completed")
        self.assertIn("规则版资源占位内容", calls[0]["result"]["resources"][0]["content"])

    # ── T5.8 ──────────────────────────────────────────────────────
    async def test_try_multi_agent_workflow_catches_workflow_exception(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import _try_multi_agent_workflow

        async def boom(*args, **kwargs):
            raise RuntimeError("workflow exploded")

        with patch("agent_service.agents.resources_workflow.run_multi_agent_resource_workflow", boom):
            result = await _try_multi_agent_workflow(self._request(), object(), None)
        self.assertIsNone(result)

    # ── T5.9 ──────────────────────────────────────────────────────
    async def test_request_containing_video_skips_multi_agent_and_uses_skeleton(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources import run_resource_generation_task

        calls = []

        async def fake_sender(url, payload):
            calls.append(payload)

        with patch("agent_service.agents.resources.get_ai_providers",
                   return_value=_FakeProviders(chat=self._success_provider(), embedding=None)):
            await run_resource_generation_task(
                self._request(resource_types=["document", "video"]), send_webhook=fake_sender
            )
        types = [r["type"] for r in calls[0]["result"]["resources"]]
        self.assertEqual(types, ["document", "video"])
        self.assertIn("规则版资源占位内容", calls[0]["result"]["resources"][1]["content"])

    # ── T5.10 ─────────────────────────────────────────────────────
    async def test_rag_failure_does_not_block_workflow(self) -> None:
        from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

        class BadEmbedding:
            async def embed_texts(self, texts):
                raise RuntimeError("embedding unavailable")

        payload = await run_multi_agent_resource_workflow(
            self._request(), self._success_provider(), embedding_provider=BadEmbedding()
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "completed")

    # ── T5.11 ─────────────────────────────────────────────────────
    async def test_run_planner_with_fallback_returns_llm_plan(self) -> None:
        from agent_service.agents.resources_workflow import _run_planner_with_fallback

        plan = await _run_planner_with_fallback(
            self._request(resource_types=["document"]),
            FakeChatProvider(outputs=[_plan_output(["document"])]),
            "",
        )
        self.assertEqual([t.resource_type for t in plan.tasks], ["document"])

    # ── T5.12 ─────────────────────────────────────────────────────
    async def test_run_planner_with_fallback_uses_rule_based_when_llm_invalid(self) -> None:
        from agent_service.agents.resources_workflow import _run_planner_with_fallback

        plan = await _run_planner_with_fallback(
            self._request(resource_types=["document", "code"]),
            FakeChatProvider(outputs=["not json"]),
            "",
        )
        self.assertEqual({t.resource_type for t in plan.tasks}, {"document", "code"})

    # ── T5.13 ─────────────────────────────────────────────────────
    async def test_run_planner_with_fallback_uses_rule_based_when_chat_none(self) -> None:
        from agent_service.agents.resources_workflow import _run_planner_with_fallback

        plan = await _run_planner_with_fallback(
            self._request(resource_types=["reading"]), None, ""
        )
        self.assertEqual([t.resource_type for t in plan.tasks], ["reading"])

    # ── T5.14 ─────────────────────────────────────────────────────
    async def test_resource_agents_parallel_uses_agentscope_fanout_pipeline(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.resources_workflow import _run_resource_agents_parallel

        calls = {"fanout": 0}

        async def fake_fanout_pipeline(agents, msg=None, enable_gather=True, **kwargs):
            calls["fanout"] += 1
            self.assertTrue(enable_gather)
            return [await agent(msg, **kwargs) for agent in agents]

        plan = ResourcePlan(
            overview="plan",
            knowledge_summary="",
            tasks=[ResourceTaskSpec("document", ["一次函数"], "结构", "markdown")],
        )
        with patch("agentscope.pipeline.fanout_pipeline", fake_fanout_pipeline):
            results = await _run_resource_agents_parallel(
                self._request(resource_types=["document"]),
                plan,
                "",
                FakeChatProvider(outputs=[_MA_DOCUMENT_OUTPUT]),
            )
        self.assertEqual(calls["fanout"], 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].type, "document")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6: Observability — Structured Logging
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase6_Observability(unittest.IsolatedAsyncioTestCase):
    """T6.1-T6.4: verify key log events fire at the expected levels.

    Phase 6 adds INFO logs for workflow entry / planner success / agent
    success / aggregator summary, and a WARNING for workflow overall failure.
    Agent-failure and Mermaid-failure WARNINGs already exist from Phase 2-3.
    """

    def _request(self, **kwargs) -> ResourceGenerateRequest:
        return ResourceGenerateRequest(
            task_id=kwargs.pop("task_id", "t6"), user_id="u1", course_id="c1",
            webhook_url="https://x.com/hook", chapter="函数", knowledge_point="一次函数",
            **kwargs,
        )

    # ── T6.1 ──────────────────────────────────────────────────────
    async def test_workflow_all_success_logs_info(self) -> None:
        from agent_service.agents.resources_workflow import (
            run_multi_agent_resource_workflow,
        )

        plan_output = json.dumps({
            "overview": "p", "knowledge_summary": "",
            "tasks": [{"resource_type": "document",
                       "focus_points": ["定义"], "suggested_structure": "S",
                       "output_format_hint": "markdown"}],
        })
        doc_output = json.dumps({"title": "T", "description": "D", "content": "C"})
        fake = FakeChatProvider(outputs=[plan_output, doc_output])

        with self.assertLogs("agent_service.agents.resources_workflow", level="INFO") as logs:
            payload = await run_multi_agent_resource_workflow(
                self._request(resource_types=["document"]), fake, None,
            )
        self.assertIsNotNone(payload)
        combined = "\n".join(logs.output)
        self.assertIn("workflow", combined.lower())

    # ── T6.2 ──────────────────────────────────────────────────────
    async def test_planner_failure_logs_warning(self) -> None:
        """Planner failure WARNING already exists on resources_plan module."""
        from agent_service.agents.resources_workflow import (
            run_multi_agent_resource_workflow,
        )

        fake = FakeChatProvider(should_raise=True)
        with self.assertLogs("agent_service.agents.resources_plan", level="WARNING") as logs:
            payload = await run_multi_agent_resource_workflow(
                self._request(resource_types=["document"]), fake, None,
            )
        # All agents fall back → workflow returns None (skeleton everywhere)
        self.assertIsNone(payload)
        combined = "\n".join(logs.output)
        self.assertIn("Planner", combined)

    # ── T6.3 ──────────────────────────────────────────────────────
    async def test_agent_fallback_logs_warning(self) -> None:
        """Agent-failure WARNING already exists on resources_agents module."""
        from agent_service.agents.resources_workflow import (
            run_multi_agent_resource_workflow,
        )

        plan_json = json.dumps({
            "overview": "p", "knowledge_summary": "",
            "tasks": [{"resource_type": "document",
                       "focus_points": ["d"], "suggested_structure": "S",
                       "output_format_hint": "h"}],
        })
        fake = FakeChatProvider(outputs=[plan_json, "not valid json"])

        with self.assertLogs("agent_service.agents.resources_agents", level="WARNING") as logs:
            payload = await run_multi_agent_resource_workflow(
                self._request(resource_types=["document"]), fake, None,
            )
        # Single agent failed → skeleton → aggregator returns None
        combined = "\n".join(logs.output)
        self.assertIn("failed", combined.lower())

    # ── T6.4 ──────────────────────────────────────────────────────
    async def test_workflow_overall_failure_logs_warning(self) -> None:
        from agent_service.agents.resources import _try_multi_agent_workflow

        fake = FakeChatProvider(should_raise=True)
        with self.assertLogs("agent_service.agents.resources", level="WARNING") as logs:
            payload = await _try_multi_agent_workflow(
                self._request(), fake, None,
            )
        self.assertIsNone(payload)
        combined = "\n".join(logs.output)
        self.assertIn("Multi-agent workflow returned None", combined)


if __name__ == "__main__":
    unittest.main()
