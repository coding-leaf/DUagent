from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from typing import Any, Protocol
from uuid import uuid4

from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_chat_model_from_settings,
)
from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.schemas.personalized_resources import (
    PersonalizedResourceGenerationRequest,
)
from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    build_backend_learning_client_from_settings,
)
from agent_service_v2.tools.contracts import outcome_for_status
from agent_service_v2.tools.resource_drafts import build_resource_draft_tools
from agent_service_v2.tools.resource_reviews import build_resource_review_tools


logger = logging.getLogger(__name__)

DEFAULT_RESOURCE_TYPE = "personal_lesson"
MAX_ATTEMPTS = 2
PUBLISHED_DECISIONS = {"approved", "approved_with_advice"}
SUPPORTED_RESOURCE_TYPES = {"personal_lesson", "diagram", "practice", "reading"}

# Backend `personalized_resources` preferences -> Backend resource kinds.
PREFERENCE_TO_RESOURCE_TYPE: dict[str, str] = {
    "text_reading": "reading",
    "reading": "reading",
    "personal_lesson": "personal_lesson",
    "lesson": "personal_lesson",
    "document": "personal_lesson",
    "chart_logic": "diagram",
    "diagram": "diagram",
    "mindmap": "diagram",
    "code_practice": "practice",
    "practice_reinforcement": "practice",
    "practice": "practice",
}

TOOL_METADATA: dict[str, tuple[str, str, bool]] = {
    "create_personalized_resource_draft": ("创建个性化资源草案", "personalized_resource", False),
    "record_personalized_validation": ("校验资源格式", "personalized_resource", False),
    "review_personalized_resource": ("独立审核学习资源", "personalized_resource", False),
    "publish_personalized_resource": ("发布个性化学习资源", "personalized_resource", False),
}

# Learner-facing summaries for lifecycle statuses that carry no failure reason.
TOOL_SUMMARY: dict[str, str] = {
    "drafted": "草案已保存，等待校验",
    "validated": "格式校验通过",
    "approved": "审核通过",
    "approved_with_advice": "审核通过（含改进建议）",
    "published": "资源已发布",
    "rejected": "审核未通过",
    "failed": "执行失败",
    "error": "执行失败",
}

EmitEvent = Callable[[EduEventType, dict[str, Any]], Any]


class PersonalizedResourceUnavailable(RuntimeError):
    """Raised when the generation pipeline cannot run in this deployment."""


class ResourceContentWriter(Protocol):
    async def write(
        self,
        resource_type: str,
        *,
        goal: str,
        chapter: str,
        knowledge_point: str,
        course_id: str,
        course_title: str | None,
        difficulty: str | None,
        repair_hint: str,
    ) -> dict[str, Any]: ...


class ModelResourceContentWriter:
    """Generates typed resource bodies with the configured chat model.

    Course grounding (RAG) stays inside the worker call, which binds the
    request `course_id` to the course knowledge base and degrades to an empty
    context when the collection is missing.
    """

    def __init__(self, settings: AgentModelSettings | None = None) -> None:
        self._settings = settings or AgentModelSettings()

    async def write(
        self,
        resource_type: str,
        *,
        goal: str,
        chapter: str,
        knowledge_point: str,
        course_id: str,
        course_title: str | None,
        difficulty: str | None = None,
        repair_hint: str = "",
    ) -> dict[str, Any]:
        from agent_service_v2.agents.leader_team import ResourceWorkerAgent

        worker = ResourceWorkerAgent(self._settings)
        topic = knowledge_point or goal
        common = {
            "course_id": course_id,
            "course_title": course_title,
            "difficulty": difficulty,
            "repair_hint": repair_hint,
        }
        if resource_type == "diagram":
            data = await worker.generate_asset("mindmap", chapter, topic, **common)
            return _typed(
                title=data.get("title") or topic,
                content=data.get("mermaid_code") or "",
                description=f"围绕“{topic}”的知识结构图",
                tags=["mindmap"],
            )
        if resource_type == "practice":
            data = await worker.generate_asset(
                "quiz",
                chapter,
                topic,
                count=5,
                question_types=["single_choice", "multi_choice"],
                **common,
            )
            questions = data.get("questions") or []
            return _typed(
                title=f"{topic}·巩固练习",
                content=json.dumps({"questions": questions}, ensure_ascii=False),
                description=f"围绕“{topic}”的 {len(questions)} 道选择题",
                tags=["practice"],
            )
        if resource_type == "personal_lesson":
            data = await worker.generate_asset("document", chapter, topic, **common)
            return _typed(
                title=data.get("title") or topic,
                content=data.get("html_content") or "",
                description=f"围绕“{topic}”的互动课件",
                tags=["lesson"],
            )
        data = await worker.generate_asset("reading", chapter, topic, **common)
        return _typed(
            title=data.get("title") or topic,
            content=data.get("markdown_content") or "",
            description=f"围绕“{topic}”的拓展阅读",
            tags=["reading"],
        )


def _typed(
    *,
    title: str,
    content: str,
    description: str,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "title": str(title),
        "content": str(content),
        "description": description,
        "tags": tags,
    }


def resolve_resource_types(
    preferences: list[str] | None,
    resource_types: list[str] | None = None,
) -> list[str]:
    """Resolve the requested resource kinds for one generation task.

    Explicit `resource_types` are Backend resource kinds already, so they take
    precedence; `resource_preferences` are learner-profile preferences and get
    mapped onto resource kinds.
    """
    resolved: list[str] = []
    for explicit in resource_types or []:
        candidate = str(explicit).strip().lower()
        if candidate in SUPPORTED_RESOURCE_TYPES and candidate not in resolved:
            resolved.append(candidate)
    for preference in preferences or []:
        resource_type = PREFERENCE_TO_RESOURCE_TYPE.get(str(preference).strip().lower())
        if resource_type and resource_type not in resolved:
            resolved.append(resource_type)
    return resolved or [DEFAULT_RESOURCE_TYPE]


class PersonalizedResourceGenerationRunner:
    """Runs draft -> validate -> review -> publish entirely in-process.

    Every step calls the same Backend tool functions the workbench agent uses,
    so no internal HTTP loopback or ASGI sub-application is involved. Events
    are pushed to the caller's broadcaster for SSE streaming.
    """

    def __init__(
        self,
        *,
        settings: AgentModelSettings | None = None,
        client: BackendLearningClient | None = None,
        writer: ResourceContentWriter | None = None,
    ) -> None:
        self._settings = settings or AgentModelSettings()
        self._client = client
        self._writer = writer

    def preflight(self) -> None:
        """Validate optional configuration before a background run starts."""
        if build_chat_model_from_settings(self._settings, stream=False) is None:
            raise PersonalizedResourceUnavailable("model_not_configured")
        if self._client_of() is None:
            raise PersonalizedResourceUnavailable("backend_not_configured")

    async def run(self, request: PersonalizedResourceGenerationRequest, emit: EmitEvent) -> dict[str, Any]:
        try:
            client = self._client_of()
            if client is None:
                emit(EduEventType.WORKFLOW_FAILED, {"reason": "backend_not_configured"})
                return {"status": "failed", "reason": "backend_not_configured"}
            writer = self._writer or ModelResourceContentWriter(self._settings)
            draft_tools = {tool.name: tool for tool in build_resource_draft_tools(client)}
            review_tools = {tool.name: tool for tool in build_resource_review_tools(client)}
            resource_types = resolve_resource_types(
                request.resource_preferences, request.resource_types
            )
            knowledge_point = request.knowledge_point or request.goal

            emit(
                EduEventType.WORKFLOW_STARTED,
                {
                    "task_id": request.task_id,
                    "conversation_id": request.conversation_id,
                    "resource_types": resource_types,
                },
            )
            emit(
                EduEventType.THOUGHT,
                {
                    "delta": (
                        f"为“{request.goal}”准备 {len(resource_types)} 份学习资源"
                        f"（{', '.join(resource_types)}）：先起草，再确定性校验，"
                        "随后独立审核，通过后发布。"
                    )
                },
            )

            published: list[dict[str, Any]] = []
            for resource_type in resource_types:
                item = await self._produce_one(
                    request=request,
                    resource_type=resource_type,
                    knowledge_point=knowledge_point,
                    writer=writer,
                    draft_tools=draft_tools,
                    review_tools=review_tools,
                    emit=emit,
                )
                if item is None:
                    return {"status": "failed", "reason": "not_published"}
                published.append(item)
        except asyncio.CancelledError:
            emit(EduEventType.WORKFLOW_FAILED, {"reason": "cancelled"})
            raise
        except Exception as exc:  # noqa: BLE001 - never break the SSE stream
            logger.exception(
                "Personalized resource generation failed: task_id=%s", request.task_id
            )
            emit(
                EduEventType.WORKFLOW_FAILED,
                {"reason": exc.__class__.__name__, "message": str(exc)[:500]},
            )
            return {"status": "failed", "reason": exc.__class__.__name__}

        emit(
            EduEventType.TEXT_DELTA,
            {
                "delta": f"已完成 {len(published)} 份学习资源："
                + "、".join(item["title"] for item in published)
            },
        )
        emit(
            EduEventType.WORKFLOW_COMPLETED,
            {
                "task_id": request.task_id,
                "status": "completed",
                "generation_ids": [item["generation_id"] for item in published],
                "published_resource_ids": [
                    item["resource_id"] for item in published if item.get("resource_id")
                ],
            },
        )
        return {"status": "completed", "items": published}

    async def _produce_one(
        self,
        *,
        request: PersonalizedResourceGenerationRequest,
        resource_type: str,
        knowledge_point: str,
        writer: ResourceContentWriter,
        draft_tools: dict[str, Any],
        review_tools: dict[str, Any],
        emit: EmitEvent,
    ) -> dict[str, Any] | None:
        repair_hint = ""
        last_reason = "not_published"
        for attempt in range(MAX_ATTEMPTS):
            content = await writer.write(
                resource_type,
                goal=request.goal,
                chapter=request.chapter or "",
                knowledge_point=knowledge_point,
                course_id=request.course_id,
                course_title=request.course_title,
                difficulty=request.difficulty,
                repair_hint=repair_hint,
            )
            draft = await _invoke_tool(
                draft_tools["create_personalized_resource_draft"],
                emit,
                user_id=request.user_id,
                course_id=request.course_id,
                source_type=request.source_type,
                goal=request.goal,
                resource_type=resource_type,
                title=content.get("title") or knowledge_point,
                content=content.get("content") or "",
                description=content.get("description") or "",
                chapter=request.chapter or "",
                knowledge_point=knowledge_point,
                tags=content.get("tags") or [],
                conversation_id=request.conversation_id,
                run_id=request.task_id,
            )
            generation_id = str(draft.get("generation_id") or "")
            if not generation_id:
                last_reason = str(draft.get("reason") or "draft_failed")
                break

            validation = await _invoke_tool(
                draft_tools["record_personalized_validation"],
                emit,
                generation_id=generation_id,
                user_id=request.user_id,
                course_id=request.course_id,
                resource_type=resource_type,
                content=content.get("content") or "",
            )
            report = validation.get("report") if isinstance(validation.get("report"), dict) else {}
            warnings = [str(item) for item in report.get("warnings") or []]
            if "generation_id" not in validation:
                # `_post` swallows transport errors into a bare status payload;
                # a persisted report always echoes the generation id back.
                last_reason = str(validation.get("reason") or "validation_unavailable")
                emit(
                    EduEventType.WORKFLOW_FAILED,
                    {"reason": last_reason, "generation_id": generation_id},
                )
                return None
            if report.get("status") != "passed":
                # Backend already moved the draft to `failed`; retrying means
                # drafting a fresh generation instead of re-validating this one.
                last_reason = "validation_failed"
                hard_failures = [str(item) for item in report.get("hard_failures") or []]
                if attempt + 1 >= MAX_ATTEMPTS:
                    emit(
                        EduEventType.WORKFLOW_FAILED,
                        {
                            "reason": "validation_failed",
                            "generation_id": generation_id,
                            "hard_failures": hard_failures,
                        },
                    )
                    return None
                repair_hint = (
                    "\n\n上一版未通过确定性校验（"
                    + (", ".join(hard_failures) or "unknown")
                    + "），请据此修正。"
                )
                emit(
                    EduEventType.THOUGHT,
                    {"delta": f"“{resource_type}”草案未通过确定性校验，正在按反馈返修一次。"},
                )
                continue

            review = await _invoke_tool(
                review_tools["review_personalized_resource"],
                emit,
                generation_id=generation_id,
                user_id=request.user_id,
                course_id=request.course_id,
                hard_failures=[],
                warnings=warnings,
                summary=f"结构化校验通过，资源类型 {resource_type}，目标：{request.goal[:120]}",
            )
            decision = str(review.get("decision") or "")
            review_unavailable = "generation_id" not in review
            if review_unavailable or decision not in PUBLISHED_DECISIONS:
                last_reason = "review_rejected"
                if attempt + 1 >= MAX_ATTEMPTS:
                    emit(
                        EduEventType.WORKFLOW_FAILED,
                        {"reason": "review_rejected", "generation_id": generation_id},
                    )
                    return None
                repair_hint = "\n\n上一版审核未通过，请重新生成更贴合课程资料与目标的内容。"
                emit(
                    EduEventType.THOUGHT,
                    {"delta": f"“{resource_type}”审核未通过，正在返修一次。"},
                )
                continue

            publish = await _invoke_tool(
                review_tools["publish_personalized_resource"],
                emit,
                generation_id=generation_id,
                user_id=request.user_id,
                course_id=request.course_id,
                resource_kind="resource",
            )
            if str(publish.get("status") or "") != "published":
                emit(
                    EduEventType.WORKFLOW_FAILED,
                    {
                        "reason": "publish_failed",
                        "generation_id": generation_id,
                        "message": publish.get("reason") or "",
                    },
                )
                return None
            return {
                "generation_id": generation_id,
                "resource_id": publish.get("resource_id"),
                "title": content.get("title") or knowledge_point,
                "resource_type": resource_type,
            }

        emit(EduEventType.WORKFLOW_FAILED, {"reason": last_reason})
        return None

    def _client_of(self) -> BackendLearningClient | None:
        if self._client is None:
            self._client = build_backend_learning_client_from_settings(self._settings)
        return self._client


class _ToolCallEmitter:
    """Publishes `tool_started` and the matching `tool_completed` event."""

    def __init__(self, emit: EmitEvent, tool_name: str) -> None:
        self._emit = emit
        self.tool_name = tool_name
        self.call_id = f"tool_{uuid4().hex}"

    def start(self) -> None:
        title, category, read_only = TOOL_METADATA.get(
            self.tool_name, (self.tool_name, "other", False)
        )
        self._emit(
            EduEventType.TOOL_STARTED,
            {
                "tool_call_id": self.call_id,
                "tool_name": self.tool_name,
                "tool_title": title,
                "tool_category": category,
                "read_only": read_only,
            },
        )

    def complete(self, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "success")
        outcome = outcome_for_status(status)
        failed = outcome == "failure"
        reason = payload.get("reason")
        summary = reason if isinstance(reason, str) and reason else TOOL_SUMMARY.get(
            status,
            status,
        )
        self._emit(
            EduEventType.TOOL_COMPLETED,
            {
                "tool_call_id": self.call_id,
                "tool_name": self.tool_name,
                "state": "error" if failed else "success",
                "status": status,
                "outcome": outcome,
                "output_summary": summary,
                **({"reason": reason} if isinstance(reason, str) and reason else {}),
            },
        )


async def _invoke_tool(tool: Any, emit: EmitEvent, **kwargs: Any) -> dict[str, Any]:
    """Call one `FunctionTool` and normalize its JSON payload into a dict."""
    emitter = _ToolCallEmitter(emit, tool.name)
    emitter.start()
    try:
        chunk = tool.call(**kwargs)
        if inspect.isawaitable(chunk):
            chunk = await chunk
        if hasattr(chunk, "__aiter__"):
            last = None
            async for item in chunk:
                last = item
            chunk = last
        text = _chunk_text(chunk)
        payload = json.loads(text) if text else {}
        if not isinstance(payload, dict):
            payload = {"value": payload}
    except Exception as exc:  # noqa: BLE001 - tool failures must not break SSE
        logger.exception("Personalized resource tool raised: tool=%s", tool.name)
        payload = {"status": "error", "reason": exc.__class__.__name__}
    emitter.complete(payload)
    return payload


def _chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""
