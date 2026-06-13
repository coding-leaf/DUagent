"""Tutoring StrategyAgent：纯规则选择内部辅导策略，不改变 API 契约，无 LLM 调用。"""

from __future__ import annotations

from dataclasses import dataclass

from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

logger = get_logger(__name__)

SUPPORTED_STRATEGIES = {
    "guided_hint": "分步骤给提示，避免直接给最终答案。",
    "direct_explanation": "直接解释核心概念，保持简洁，并给出关键检查点。",
    "clarifying_question": "只问一个澄清问题，先确认学生具体卡点。",
    "worked_example": "用相似例题或完整过程解释，再回到学生当前问题。",
}


@dataclass(frozen=True)
class TutoringStrategy:
    strategy: str
    instruction: str
    focus_points: list[str]
    source: str


def select_tutoring_strategy_by_rule(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
) -> TutoringStrategy:
    """纯规则选择 tutoring 内部策略，输入请求/检索上下文，输出下游 prompt 使用的策略对象。"""
    strategy = _rule_strategy_name(request)
    return TutoringStrategy(
        strategy=strategy,
        instruction=SUPPORTED_STRATEGIES[strategy],
        focus_points=_build_focus_points(request, retrieval_context),
        source="rule",
    )


def _rule_strategy_name(request: TutoringChatRequest) -> str:
    if _is_ambiguous_short_message(request.message):
        return "clarifying_question"
    return {
        "L1": "guided_hint",
        "L2": "worked_example",
        "L3": "direct_explanation",
    }[request.user_profile.guidance_level]


def _is_ambiguous_short_message(message: str) -> bool:
    normalized = message.strip()
    ambiguous_terms = {"这个", "不会", "不懂", "怎么做", "讲讲", "解释下"}
    return normalized in ambiguous_terms


def _build_focus_points(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
) -> list[str]:
    candidates = (
        request.user_profile.knowledge_weak
        or retrieval_context.knowledge_points
        or request.user_profile.knowledge_mastered
        or [request.message[:20]]
    )
    return [item.strip() for item in candidates if isinstance(item, str) and item.strip()][:3]


__all__ = ["TutoringStrategy", "select_tutoring_strategy_by_rule"]
