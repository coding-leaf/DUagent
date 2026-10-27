from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator
from uuid import uuid4

from agentscope.agent import Agent
from agentscope.event import (
    RequireExternalExecutionEvent,
    TextBlockDeltaEvent,
    ThinkingBlockDeltaEvent,
)
from agentscope.message import Msg, TextBlock, ToolCallBlock, UserMsg
from agentscope.tool import Toolkit
from agentscope.types import ReplyFinishedReason

from agent_service_v2.agents.curriculum_planner import (
    CourseCurriculumPlanner,
    collect_model_text as _collect_model_text,
)
from agent_service_v2.agents.model_provider import AgentModelSettings, build_chat_model_from_settings


logger = logging.getLogger(__name__)


class CoursePlannerAgent(CourseCurriculumPlanner):
    """Backward-compatible alias of :class:`CourseCurriculumPlanner`.

    The old leader implementation hardcoded a single-discipline curriculum prompt.
    The generic planner now infers the discipline from ``course_title`` and the
    supplied material, so this class only keeps the historic name (and the
    historic ``plan_curriculum(context)`` call signature) alive.
    """

    def __init__(self, settings: AgentModelSettings):
        # Build through this module's symbol so existing patches of
        # `agent_service_v2.agents.leader_team.build_chat_model_from_settings`
        # keep working.
        super().__init__(
            settings,
            model=build_chat_model_from_settings(settings, stream=False),
        )


class ResourceWorkerAgent:
    """Worker Agent: Specialized in generating high-quality learning assets (Mindmaps, Coding Quizzes)."""

    def __init__(self, settings: AgentModelSettings):
        self.settings = settings
        self.model = build_chat_model_from_settings(settings, stream=False)

    async def generate_asset(
        self,
        resource_type: str,
        chapter: str,
        knowledge_point: str,
        *,
        course_id: str | None = None,
        course_title: str | None = None,
        count: int = 3,
        question_types: list[str] | None = None,
        difficulty: str | None = None,
        personalized: bool = False,
        personalization_context: dict[str, Any] | None = None,
        repair_hint: str = "",
    ) -> dict[str, Any]:
        # 🚀 1. 根据 course_id 与 knowledge_point 触发 RAG 检索
        rag_context = ""
        if course_id and knowledge_point:
            try:
                from agent_service_v2.tools.rag import retrieve_course_context

                rag_res = await retrieve_course_context(
                    query=knowledge_point,
                    course_id=course_id,
                    limit=4,
                    settings=self.settings,
                )
                rag_context = rag_res.get("context_text", "")
            except Exception as e:
                logger.warning("RAG retrieval failed inside Worker Agent for node %s: %s", knowledge_point, e)

        course_reference_section = ""
        if rag_context:
            course_reference_section = f"\n=== COURSE REFERENCE MATERIAL CHUNKS (RAG) ===\n{rag_context}\n"

        resolved_title = (course_title or "").strip()
        # 不写死任何学科：缺少课程标题时只声明“由材料推断”。
        course_info = (
            f"Course Title: {resolved_title}"
            if resolved_title
            else "Course Title: not provided (infer the subject from the chapter, topic and material)"
        )

        if resource_type == "quiz":
            requested_types = question_types or ["single_choice", "multi_choice"]
            if any(item not in {"single_choice", "multi_choice"} for item in requested_types):
                raise ValueError("ordinary quiz only supports single_choice and multi_choice")
            q_types_str = ", ".join(requested_types)
            diff_str = difficulty or "medium"

            personalization_prompt = ""
            if personalized and personalization_context:
                personalization_prompt = "\n=== STUDENT PERSONALIZATION CONTEXT ===\n"
                eval_data = personalization_context.get("evaluation")
                if eval_data and eval_data.get("summary"):
                    personalization_prompt += f"Student Evaluation Summary: {eval_data['summary']}\n"
                profile_data = personalization_context.get("profile")
                if profile_data:
                    personalization_prompt += f"Guidance Level: {profile_data.get('guidance_level')}\n"
                    personalization_prompt += f"Cognitive Blindspots: {profile_data.get('blindspots')}\n"
                wrong_pts = personalization_context.get("wrong_points")
                if wrong_pts:
                    wrong_pts_str = ", ".join(pt.get("name") if isinstance(pt, dict) else str(pt) for pt in wrong_pts)
                    personalization_prompt += f"Recent Wrong Topics: {wrong_pts_str}\n"
                curr_node = personalization_context.get("current_path_node")
                if curr_node:
                    personalization_prompt += f"Current Learning Node: {curr_node.get('name')}\n"

                personalization_prompt += (
                    "Please adapt the questions to specifically target the student's cognitive blindspots, "
                    "remedy their recent errors, and match their guidance level. "
                    "Make the explanations highly encouraging, educational, and scaffolded.\n"
                )

            prompt = f"""You are an assessment specialist for {resolved_title or "the course under study"}.
Please generate exactly {count} high-quality questions for the topic:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}
Target Difficulty: {diff_str}
Allowed Question Types: {q_types_str}
{personalization_prompt}
{course_reference_section}
Ensure the questions are precise and cover critical syllabus concepts.

{course_info}
If the course title specifies a particular language or technology (e.g. a programming language), all terminology, options and explanations must match that exact course language.

Your output MUST be a strict JSON object with this structure:
{{
  "questions": [
     // Each question must match one of the allowed types (single_choice, multi_choice)
     // Example single_choice:
     {{
       "title": "A single-choice question title or statement in Simplified Chinese (简体中文)",
       "content": "A single-choice question title or statement in Simplified Chinese (简体中文)",
       "type": "single_choice",
       "options": [
         {{"key": "A", "text": "Option A text in Simplified Chinese"}},
         {{"key": "B", "text": "Option B text in Simplified Chinese"}},
         {{"key": "C", "text": "Option C text in Simplified Chinese"}},
         {{"key": "D", "text": "Option D text in Simplified Chinese"}}
       ],
       "answer": "A",
       "explanation": "Why Option A is correct, written in Simplified Chinese",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }},
     // Example multi_choice:
     {{
       "title": "A multiple choice question statement in Simplified Chinese (简体中文)",
       "content": "A multiple choice question statement in Simplified Chinese (简体中文)",
       "type": "multi_choice",
       "options": [
         {{"key": "A", "text": "Option A text in Simplified Chinese"}},
         {{"key": "B", "text": "Option B text in Simplified Chinese"}},
         {{"key": "C", "text": "Option C text in Simplified Chinese"}},
         {{"key": "D", "text": "Option D text in Simplified Chinese"}}
       ],
       "answer": ["A", "C"],
       "explanation": "Why Option A & C are correct, written in Simplified Chinese",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }}
  ]
}}

Language & Technology Requirements:
1. ALL descriptive textual fields (including: "title", "content", options' "text", "explanation", "description") MUST be generated in Simplified Chinese (简体中文).
2. Do not generate programming challenges, free-response questions, starter code or test cases in the ordinary quiz flow.
"""
        elif resource_type in {"document", "personal_lesson"}:
            prompt = f"""You are a senior lecturer for {resolved_title or "the course under study"}.
Please generate a comprehensive, structured Markdown lecture tutorial (rich teaching notes) for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

{course_info}
{course_reference_section}
Structure the notes pedagogically:
1. Core Concepts & Theoretical Intuition
2. Key Mechanisms & Syntax Comparisons (use Markdown tables)
3. Concrete, runnable code examples (when technical) with line-by-line explanations
4. Common Pitfalls & Anti-patterns analysis
5. Student Self-check Summary & Checklist

All code examples, structural analysis, and concepts must stay inside the subject of this course; never default to an unrelated language or discipline.
Output format MUST be a strict JSON:
{{
  "title": "Lecture Title in Simplified Chinese",
  "markdown_content": "# {knowledge_point or "General"}\\n\\n## 1. 核心概念与原理\\n..."
}}

Language & Format Requirements:
1. "title" and the inner Markdown tutorial "markdown_content" (including headers, explanations, tables, code blocks) MUST be fully generated in Simplified Chinese (简体中文).
2. Use standard Markdown formatting only. Absolutely DO NOT generate HTML slides, <script>, or inline DOM event handlers.
"""
        elif resource_type == "mindmap":
            prompt = f"""You are a knowledge-mapping assistant for {resolved_title or "the course under study"}.
Generate a structured Mermaid.js mindmap source string for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

{course_info}
{course_reference_section}
Ensure all mindmap nodes and concepts match the course topic and its exact subject terminology.
Output format MUST be a strict JSON:
{{
  "title": "Mindmap title in Simplified Chinese",
  "mermaid_code": "mindmap\\n  root(({knowledge_point or "General"}))\\n    Concept\\n      Subconcept"
}}

Language Requirements:
1. "title" and all node texts / concepts inside "mermaid_code" MUST be fully generated in Simplified Chinese (简体中文) (e.g. root((指针基础)) -> Concept[指针概念] -> Subconcept[指针定义]).
2. CRITICAL SYNTATIC RULE: Never use unquoted brackets `[` or `]` or double-quotes inside node text/labels in `mermaid_code`. If a label contains special characters, spaces, brackets, or code snippets (e.g. `arr[i]`), you MUST wrap the entire label in double quotes (e.g., ID["text with arr['i']"]) and convert any nested double-quotes to single quotes `'` to prevent Mermaid syntax parsing errors.
"""
        else:
            # Fallback reading
            prompt = f"""Generate rich, deep reading notes for {knowledge_point or "General"} inside {chapter or "General"} for {resolved_title or "the course under study"}.

{course_info}
{course_reference_section}
Ensure all descriptions, tutorial chapters, examples and explanations are written in the exact subject language of the course; never default to an unrelated language or discipline.
Output MUST be JSON:
{{
  "title": "Extra Reading in Simplified Chinese",
  "markdown_content": "### Introduction to {knowledge_point or "General"}\\n..."
}}

Language Requirements:
1. "title" and the entire markdown tutorial "markdown_content" (including headers, explanations, text paragraphs) MUST be fully generated in Simplified Chinese (简体中文).
"""
        if not self.model:
            raise RuntimeError("LLM Model not configured in agent_service_v2")

        prompt = f"{prompt}\n{repair_hint}" if repair_hint else prompt

        response = await self.model([UserMsg(name="resource_worker", content=prompt)])
        content = await _collect_model_text(response)

        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data = json.loads(content)

        # Robust post-processing and schema normalization loop
        if isinstance(data, dict) and "questions" in data:
            for q in data["questions"]:
                # 1. Normalize title / content
                if "title" in q and "content" not in q:
                    q["content"] = q["title"]
                elif "content" in q and "title" not in q:
                    q["title"] = q["content"]

                if q.get("type") not in {"single_choice", "multi_choice"}:
                    raise ValueError("model returned unsupported ordinary quiz type")

                # 2. Handle correct answer options format if LLM returns a simple string list
                raw_options = q.get("options", [])
                if isinstance(raw_options, list) and len(raw_options) > 0:
                    if isinstance(raw_options[0], str):
                        # Convert flat string options ["Opt A", "Opt B", ...] to standard dict structure
                        keys = ["A", "B", "C", "D", "E", "F"]
                        q["options"] = [
                            {"key": keys[idx], "text": text} for idx, text in enumerate(raw_options[: len(keys)])
                        ]

        return data


async def run_leader_team_kg_generation(
    settings: AgentModelSettings,
    context_text: str,
    *,
    course_title: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point for the generic curriculum planner."""
    planner = CourseCurriculumPlanner(settings)
    return await planner.plan_curriculum(context_text, course_title=course_title)


class CurriculumLeaderAgent(Agent):
    """Leader Agent: Analyzes learner goals and coordinates member specialists via AgentScope TeamPipeline."""

    def __init__(
        self,
        name: str = "curriculum_leader",
        *,
        settings: AgentModelSettings | None = None,
        assigned_types: list[str] | None = None,
        request: Any = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        self.settings = settings or AgentModelSettings()
        self.assigned_types = assigned_types or []
        self.request = request
        resolved_model = model or build_chat_model_from_settings(self.settings, stream=False)
        system_prompt = (
            "你是课程教学规划主管 (Curriculum Leader)。"
            "你的职责是分析学生的学习目标与个性化诉求，"
            "并通过官方 TeamAssign 工具将资源生成任务并发分派给对应的领域专家智能体："
            "- lesson_worker: 课件精讲专家"
            "- diagram_worker: 思维导图专家"
            "- quiz_worker: 练习习题专家"
            "- reading_worker: 拓展阅读专家\n"
            "请在同一轮中一次性分派全部所需资源，实现高效并发调度。"
        )
        super().__init__(
            name=name,
            system_prompt=system_prompt,
            model=resolved_model,
            toolkit=toolkit or Toolkit(),
        )
        self._dispatched = False

    async def reply_stream(
        self,
        inputs: Any = None,
        structured_schema: Any = None,
        yield_final_msg: bool = False,
    ) -> AsyncGenerator[Any, None]:
        reply_id = getattr(self.state, "reply_id", None) or f"leader_{uuid4().hex[:8]}"

        if not self._dispatched and self.assigned_types:
            self._dispatched = True
            delta_msg = (
                f"正在为目标规划并分派 {len(self.assigned_types)} 份专家资源生成任务：{', '.join(self.assigned_types)}"
            )
            yield ThinkingBlockDeltaEvent(
                reply_id=reply_id,
                block_id=f"th_{uuid4().hex[:8]}",
                delta=delta_msg,
            )

            type_to_member = {
                "personal_lesson": "lesson_worker",
                "diagram": "diagram_worker",
                "practice": "quiz_worker",
                "reading": "reading_worker",
            }

            calls = []
            for r_type in self.assigned_types:
                member_name = type_to_member.get(r_type, f"{r_type}_worker")
                prompt_data = {
                    "member": member_name,
                    "prompt": json.dumps(
                        {
                            "resource_type": r_type,
                            "goal": getattr(self.request, "goal", "") if self.request else "",
                            "knowledge_point": (
                                getattr(self.request, "knowledge_point", "") or getattr(self.request, "goal", "")
                            )
                            if self.request
                            else "",
                            "chapter": getattr(self.request, "chapter", "") if self.request else "",
                            "course_id": getattr(self.request, "course_id", "") if self.request else "",
                        },
                        ensure_ascii=False,
                    ),
                }
                calls.append(
                    ToolCallBlock(
                        id=f"call_{uuid4().hex[:8]}",
                        name="TeamAssign",
                        input=json.dumps(prompt_data, ensure_ascii=False),
                    )
                )

            yield RequireExternalExecutionEvent(
                reply_id=reply_id,
                tool_calls=calls,
            )
            return

        yield TextBlockDeltaEvent(
            reply_id=reply_id,
            block_id=f"txt_{uuid4().hex[:8]}",
            delta="领域专家智能体已全部完成生成与入库。",
        )
        yield Msg(
            name=self.name,
            role="assistant",
            content=[TextBlock(text="All domain worker agents have completed their assignments.")],
            finished_reason=ReplyFinishedReason.COMPLETED,
        )


class BaseResourceWorkerAgent(Agent):
    """Specialized worker agent for generating and publishing personalized learning resources."""

    resource_type: str = "generic"
    description: str = "通用资源生成专家"

    def __init__(
        self,
        name: str,
        *,
        settings: AgentModelSettings | None = None,
        client: Any | None = None,
        writer: Any | None = None,
        description: str | None = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        self.settings = settings or AgentModelSettings()
        self.client = client
        self.writer = writer
        if description:
            self.description = description

        tools_list = []
        if client:
            try:
                from agent_service_v2.tools.resource_drafts import build_resource_draft_tools
                from agent_service_v2.tools.resource_reviews import build_resource_review_tools

                tools_list.extend(build_resource_draft_tools(client))
                tools_list.extend(build_resource_review_tools(client))
            except Exception:
                pass

        tk = toolkit or Toolkit(tools=tools_list)

        resolved_model = model or build_chat_model_from_settings(self.settings, stream=False)
        super().__init__(
            name=name,
            system_prompt=(
                f"You are {name}, a specialist domain agent for {self.resource_type} resources. {self.description}"
            ),
            model=resolved_model,
            toolkit=tk,
        )
        self.last_published_item: dict[str, Any] | None = None
        self.last_failure_reason: str | None = None
        self._current_request: Any = None
        self._current_emit: Any = None

    def set_execution_context(self, request: Any, emit: Any) -> None:
        self._current_request = request
        self._current_emit = emit

    async def reply_stream(
        self,
        inputs: Any = None,
        structured_schema: Any = None,
        yield_final_msg: bool = False,
    ) -> AsyncGenerator[Any, None]:
        if self._current_request and self._current_emit:
            from agent_service_v2.generators.personalized_resource_flow import produce_resource_item

            item = await produce_resource_item(
                worker=self,
                request=self._current_request,
                resource_type=self.resource_type,
                writer=self.writer,
                client=self.client,
                emit=self._current_emit,
            )
            self.last_published_item = item
            if item is None:
                self.last_failure_reason = getattr(self, "_last_reason", "not_published")
                yield Msg(
                    name=self.name,
                    role="assistant",
                    content=[TextBlock(text=f"{self.name} failed: {self.last_failure_reason}")],
                    finished_reason=ReplyFinishedReason.ERROR,
                )
                return

        yield Msg(
            name=self.name,
            role="assistant",
            content=[TextBlock(text=f"{self.name} completed resource generation.")],
            finished_reason=ReplyFinishedReason.COMPLETED,
        )


class LessonWorkerAgent(BaseResourceWorkerAgent):
    """Worker Agent specialized in structured lecture tutorials and courseware."""

    resource_type = "personal_lesson"
    description = "课件与精讲专家：负责基于课程教材与知识点生成结构化专业讲义教程（Markdown）"

    def __init__(
        self,
        name: str = "lesson_worker",
        *,
        settings: AgentModelSettings | None = None,
        client: Any | None = None,
        writer: Any | None = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        super().__init__(
            name=name,
            settings=settings,
            client=client,
            writer=writer,
            model=model,
            toolkit=toolkit,
        )


class MindmapWorkerAgent(BaseResourceWorkerAgent):
    """Worker Agent specialized in Mermaid knowledge graphs and mindmaps."""

    resource_type = "diagram"
    description = "思维导图专家：负责基于课程知识点生成 Mermaid 概念思维导图与知识结构图"

    def __init__(
        self,
        name: str = "diagram_worker",
        *,
        settings: AgentModelSettings | None = None,
        client: Any | None = None,
        writer: Any | None = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        super().__init__(
            name=name,
            settings=settings,
            client=client,
            writer=writer,
            model=model,
            toolkit=toolkit,
        )


class QuizWorkerAgent(BaseResourceWorkerAgent):
    """Worker Agent specialized in assessment and practice quizzes."""

    resource_type = "practice"
    description = "巩固习题专家：负责基于知识点生成单选、多选等巩固练习题及详细解析"

    def __init__(
        self,
        name: str = "quiz_worker",
        *,
        settings: AgentModelSettings | None = None,
        client: Any | None = None,
        writer: Any | None = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        super().__init__(
            name=name,
            settings=settings,
            client=client,
            writer=writer,
            model=model,
            toolkit=toolkit,
        )


class ReadingWorkerAgent(BaseResourceWorkerAgent):
    """Worker Agent specialized in tutorial reading notes and extended articles."""

    resource_type = "reading"
    description = "拓展阅读专家：负责基于知识点生成深度拓展阅读材料与延伸教程"

    def __init__(
        self,
        name: str = "reading_worker",
        *,
        settings: AgentModelSettings | None = None,
        client: Any | None = None,
        writer: Any | None = None,
        model: Any = None,
        toolkit: Toolkit | None = None,
    ) -> None:
        super().__init__(
            name=name,
            settings=settings,
            client=client,
            writer=writer,
            model=model,
            toolkit=toolkit,
        )


__all__ = [
    "CoursePlannerAgent",
    "ResourceWorkerAgent",
    "CurriculumLeaderAgent",
    "BaseResourceWorkerAgent",
    "LessonWorkerAgent",
    "MindmapWorkerAgent",
    "QuizWorkerAgent",
    "ReadingWorkerAgent",
    "run_leader_team_kg_generation",
]
