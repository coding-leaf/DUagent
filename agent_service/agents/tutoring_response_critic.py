"""Tutoring ResponseCriticAgent：内部判断候选回答是否可采纳，不改变 API 契约。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agent_service.core.ai import ChatProvider
from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.prompts.tutoring import build_response_critic_messages
from agent_service.schemas.tutoring import TutoringChatRequest

logger = get_logger(__name__)


@dataclass(frozen=True)
class TutoringCriticResult:
    accepted: bool
    reason: str
    source: str


async def evaluate_tutoring_response(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    model_response,
    strategy,
    chat_provider: ChatProvider | None,
) -> TutoringCriticResult:
    """评估候选 tutoring 回复，输入请求/上下文/候选回复/策略/模型，输出是否采纳。"""
    fallback = _evaluate_by_rule(request, retrieval_context, model_response, strategy)
    if chat_provider is None:
        return fallback
    try:
        raw = await chat_provider.complete(
            build_response_critic_messages(request, retrieval_context, model_response, strategy)
        )
        parsed = _parse_llm_critic_result(raw)
        if parsed is not None:
            return parsed
    except Exception as exc:
        logger.warning("Tutoring response critic failed: user_id=%s error=%s", request.user_id, exc)
    return fallback


def _evaluate_by_rule(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    model_response,
    strategy,
) -> TutoringCriticResult:
    text = (getattr(model_response, "model_text", None) or "").strip()
    if not text:
        return TutoringCriticResult(accepted=False, reason="empty_response", source="rule")
    if getattr(strategy, "strategy", None) == "clarifying_question" and not _contains_question(text):
        return TutoringCriticResult(accepted=False, reason="missing_clarifying_question", source="rule")
    if not _is_relevant(request, retrieval_context, model_response, strategy, text):
        return TutoringCriticResult(accepted=False, reason="off_topic", source="rule")
    return TutoringCriticResult(accepted=True, reason="accepted", source="rule")


def _contains_question(text: str) -> bool:
    return "?" in text or "？" in text or "吗" in text or "哪" in text


def _is_relevant(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    model_response,
    strategy,
    text: str,
) -> bool:
    trusted_terms = []
    trusted_terms.extend(getattr(strategy, "focus_points", []) or [])
    trusted_terms.extend(getattr(retrieval_context, "knowledge_points", []) or [])
    trusted_terms.extend(request.user_profile.knowledge_weak)
    trusted_terms.extend(request.user_profile.knowledge_mastered)
    cleaned_terms = [_term_text(item) for item in trusted_terms]
    cleaned_terms = [item for item in cleaned_terms if item]
    for item in cleaned_terms:
        if item in text:
            return True
    response_terms = {
        item.strip()
        for item in (getattr(model_response, "knowledge_point_names", []) or [])
        if isinstance(item, str) and item.strip()
    }
    if response_terms.intersection(cleaned_terms):
        return True
    compact_message = request.message.strip()
    return len(compact_message) >= 2 and compact_message in text


def _term_text(item) -> str:
    if isinstance(item, str):
        return item.strip()
    name = getattr(item, "name", None)
    return name.strip() if isinstance(name, str) else ""


def _parse_llm_critic_result(raw: str) -> TutoringCriticResult | None:
    try:
        payload = json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("accepted"), bool):
        return None
    reason = payload.get("reason")
    return TutoringCriticResult(
        accepted=payload["accepted"],
        reason=reason.strip() if isinstance(reason, str) and reason.strip() else "llm_judgement",
        source="llm",
    )


__all__ = ["TutoringCriticResult", "evaluate_tutoring_response"]
