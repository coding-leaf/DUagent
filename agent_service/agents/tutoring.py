import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from agent_service.core.ai import ChatProvider
from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext, build_tutoring_retrieval_context
from agent_service.prompts.tutoring import build_tutoring_messages
from agent_service.schemas.tutoring import (
    KnowledgePoint,
    SuggestedExercise,
    TutoringChatRequest,
    TutoringUserProfile,
)


class _TutoringStructuredOutput(BaseModel):
    """AgentScope structured output schema for tutoring chat JSON path.

    不暴露到 schemas/，不泄漏 AgentScope 类型到 API 层。
    """

    model_text: str | None = None
    knowledge_points: list[str] = []
    suggestion: str | None = None

_AGENT_RESULT_PATTERN = re.compile(r"<agent_result>(.*?)</agent_result>", re.DOTALL)
logger = get_logger(__name__)


@dataclass(frozen=True)
class TutoringModelResponse:
    model_text: str | None = None
    knowledge_point_names: list[str] = field(default_factory=list)
    suggestion_text: str | None = None


@dataclass(frozen=True)
class TutoringGenerationResult:
    chunk_text: str
    knowledge_points: list[KnowledgePoint]
    suggestion_text: str
    suggested_exercises: list[SuggestedExercise]
    used_rule_fallback: bool


def build_tutoring_generation_result(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext | None = None,
    model_response: TutoringModelResponse | None = None,
) -> TutoringGenerationResult:
    """整合 tutoring 运行态结果，输入请求、检索上下文和可选模型结果，输出统一内部结果对象。"""
    context = retrieval_context or build_tutoring_retrieval_context(request)
    response = model_response or TutoringModelResponse()
    knowledge_points = _build_knowledge_points(
        request,
        context,
        knowledge_point_names=response.knowledge_point_names,
    )
    suggested_exercises = _build_suggested_exercises(knowledge_points)
    focus_text = "、".join(item.name for item in knowledge_points) or "当前问题"
    chunk_text = response.model_text or _build_chunk_content(request, focus_text, context)
    suggestion = response.suggestion_text or f"建议先围绕{focus_text}复习核心概念，再完成一组相似练习。"
    return TutoringGenerationResult(
        chunk_text=chunk_text,
        knowledge_points=knowledge_points,
        suggestion_text=suggestion,
        suggested_exercises=suggested_exercises,
        used_rule_fallback=response.model_text is None,
    )


def parse_tutoring_model_response(model_output: str) -> TutoringModelResponse:
    """解析模型输出为 TutoringModelResponse，输入模型原始文本，输出结构化结果。

    解析链：json.loads 整段 JSON → <agent_result> 正则提取 → 原始文本作为 model_text。
    """
    if not model_output:
        return TutoringModelResponse()

    json_result = _try_parse_json_mode_output(model_output)
    if json_result is not None:
        return json_result

    match = _AGENT_RESULT_PATTERN.search(model_output)
    if match is None:
        return TutoringModelResponse(model_text=model_output.strip() or None)

    cleaned_text = _AGENT_RESULT_PATTERN.sub("", model_output).strip() or None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return TutoringModelResponse(model_text=cleaned_text)

    return _build_response_from_payload(cleaned_text, payload)


def _try_parse_json_mode_output(model_output: str) -> TutoringModelResponse | None:
    """尝试将整个输出解析为 JSON object，成功则提取字段，失败返回 None。"""
    stripped = model_output.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    # 不校验 JSON schema：prompt 约定字段后，仅提取已知 key，未知 key 静默忽略
    model_text = payload.get("model_text")
    return _build_response_from_payload(
        model_text.strip() if isinstance(model_text, str) and model_text.strip() else None,
        payload,
    )


def _build_response_from_payload(model_text: str | None, payload: dict) -> TutoringModelResponse:
    """从已解析的 payload dict 提取 knowledge_points 和 suggestion。"""
    knowledge_point_names = payload.get("knowledge_points")
    suggestion_text = payload.get("suggestion")
    parsed_names = (
        [item.strip() for item in knowledge_point_names if isinstance(item, str) and item.strip()][:3]
        if isinstance(knowledge_point_names, list)
        else []
    )
    parsed_suggestion = suggestion_text.strip() if isinstance(suggestion_text, str) and suggestion_text.strip() else None
    return TutoringModelResponse(
        model_text=model_text,
        knowledge_point_names=parsed_names,
        suggestion_text=parsed_suggestion,
    )


async def generate_tutoring_model_response(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    chat_provider: ChatProvider | None,
) -> TutoringModelResponse | None:
    """调用 tutoring 模型编排，输入请求和检索上下文，输出可合并进 SSE 的内部模型结果。

    降级链：structured output → text JSON parse → None（上层 fallback 规则版）。
    """
    if chat_provider is None:
        return None
    messages = build_tutoring_messages(request, retrieval_context)
    try:
        raw = await _try_structured_output(messages, chat_provider)
        if raw is not None:
            return parse_tutoring_model_response(raw)
        raw = await chat_provider.complete(messages)
        return parse_tutoring_model_response(raw)
    except Exception as exc:
        logger.warning("Tutoring chat generation failed: user_id=%s error=%s", request.user_id, exc)
        return None


async def _try_structured_output(messages, chat_provider) -> str | None:
    """尝试用 AgentScope structured_model 生成输出，成功返回 JSON 文本，失败返回 None。"""
    try:
        raw = await chat_provider.complete(messages, structured_model=_TutoringStructuredOutput)
        if raw and raw.strip():
            return raw.strip()
    except Exception:
        pass
    return None


def _build_knowledge_points(
    request: TutoringChatRequest,
    context: TutoringRetrievalContext,
    knowledge_point_names: list[str] | None = None,
) -> list[KnowledgePoint]:
    if knowledge_point_names:
        return [
            KnowledgePoint(
                name=name,
                chapter=request.course_id if request.scope == "course" else None,
            )
            for name in knowledge_point_names[:3]
            if name
        ]
    if context.knowledge_points:
        return context.knowledge_points
    weak_points = request.user_profile.knowledge_weak
    mastered_points = request.user_profile.knowledge_mastered
    names = weak_points or mastered_points or [request.message[:20] or "当前问题"]
    mastery = 40.0 if weak_points else 70.0 if mastered_points else None
    return [
        KnowledgePoint(
            name=name,
            chapter=request.course_id if request.scope == "course" else None,
            mastery=mastery,
        )
        for name in names[:3]
        if name
    ]


def _build_suggested_exercises(knowledge_points: list[KnowledgePoint]) -> list[SuggestedExercise]:
    return [
        SuggestedExercise(title=f"{item.name} 巩固练习", chapter=item.chapter)
        for item in knowledge_points[:2]
    ]


def _build_chunk_content(request: TutoringChatRequest, focus_text: str, context: TutoringRetrievalContext) -> str:
    guidance_text = {
        "L1": "我会先拆成更小的步骤来讲。",
        "L2": "我会用关键步骤帮你串起来。",
        "L3": "我会直接给出核心思路和检查点。",
    }[request.user_profile.guidance_level]
    retrieval_text = ""
    if context.user_memory_facts or context.course_knowledge_chunks:
        retrieval_text = "结合长期记忆和课程知识，"
    summary_text = f"结合已有摘要：{request.conversation_summary}" if request.conversation_summary else "先基于你当前的问题分析。"
    return f"{retrieval_text}{guidance_text}{summary_text}这次重点看{focus_text}。"


__all__ = [
    "TutoringModelResponse",
    "TutoringGenerationResult",
    "build_tutoring_generation_result",
    "generate_tutoring_model_response",
    "parse_tutoring_model_response",
]
