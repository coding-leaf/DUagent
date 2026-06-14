"""Tutoring 规则 Guard：判断候选回答是否可采纳，纯规则、无 LLM 调用、无网络。"""

from __future__ import annotations

from dataclasses import dataclass

from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

logger = get_logger(__name__)


@dataclass(frozen=True)
class TutoringCriticResult:
    accepted: bool
    reason: str
    source: str


def evaluate_tutoring_response_by_rule(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    model_response,
    strategy,
) -> TutoringCriticResult:
    """规则审查候选 tutoring 回复，输入请求/上下文/候选回复/策略，输出是否采纳（纯规则）。"""
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
    trusted_terms.extend(getattr(retrieval_context, "knowledge_points", []) or [])
    trusted_terms.extend(
        node.get("name")
        for node in (getattr(retrieval_context, "matched_kg_nodes", []) or [])
        if isinstance(node, dict)
    )
    trusted_terms.extend(request.user_profile.knowledge_weak)
    trusted_terms.extend(request.user_profile.knowledge_mastered)
    cleaned_terms = [_term_text(item) for item in trusted_terms]
    cleaned_terms = [item for item in cleaned_terms if item]
    if not cleaned_terms:
        # 无任何可对齐术语（检索为空且画像/策略均无术语）时，相关性判据无意义，
        # 不据此判 off_topic，避免把有效回答清零；grounding 校验仅在有术语时生效。
        return True
    for item in cleaned_terms:
        if item in text:
            return True
    response_terms = {
        item.strip()
        for item in (getattr(model_response, "knowledge_point_names", []) or [])
        if isinstance(item, str) and item.strip()
    }
    if response_terms.intersection(set(cleaned_terms)):
        return True
    compact_message = request.message.strip()
    return len(compact_message) >= 2 and compact_message in text


def _term_text(item) -> str:
    if isinstance(item, str):
        return item.strip()
    name = getattr(item, "name", None)
    return name.strip() if isinstance(name, str) else ""


__all__ = ["TutoringCriticResult", "evaluate_tutoring_response_by_rule"]
