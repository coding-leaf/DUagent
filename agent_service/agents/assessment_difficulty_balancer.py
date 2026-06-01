"""Difficulty guard for generated assessment questions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import build_difficulty_balancer_prompt
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest

logger = get_logger(__name__)

_HARD_SIGNALS = {
    "综合",
    "证明",
    "推导",
    "复杂",
    "多概念",
    "联立",
    "均摊",
    "边界",
    "策略",
    "分析",
}
_EASY_SIGNALS = {
    "什么是",
    "定义",
    "通常是多少",
    "基础",
    "识别",
    "概念",
}
_TEMPLATE_MARKERS = {"请围绕", "完成一道", "模板", "占位", "待生成"}


@dataclass(frozen=True)
class DifficultyBalancerResult:
    accepted: bool
    reasons: list[str]
    source: str


class DifficultyBalancer:
    """审查生成题是否贴合请求难度，输入请求和题目列表，输出是否接受及原因。"""

    def __init__(self, chat_provider=None) -> None:
        self._chat_provider = chat_provider

    async def review(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None = None,
    ) -> DifficultyBalancerResult:
        rule_result = _review_by_rules(request, questions)
        if not rule_result.accepted:
            logger.warning("DifficultyBalancer rule gate rejected questions: %s", rule_result.reasons)
            return rule_result
        if self._chat_provider is None:
            return rule_result
        try:
            return await self._review_with_llm(
                request,
                questions,
                course_knowledge_context=course_knowledge_context,
                fallback=rule_result,
            )
        except Exception:
            logger.warning("DifficultyBalancer LLM review failed; using rule result", exc_info=True)
            return rule_result

    async def _review_with_llm(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None,
        fallback: DifficultyBalancerResult,
    ) -> DifficultyBalancerResult:
        questions_json = json.dumps(
            [_question_to_dict(question) for question in questions],
            ensure_ascii=False,
        )
        raw = await self._chat_provider.complete([
            ChatMessage(role="system", content="你是 EDUagent 的题目难度审查员。只输出 JSON。"),
            ChatMessage(
                role="user",
                content=build_difficulty_balancer_prompt(
                    request,
                    questions_json,
                    course_knowledge_context=course_knowledge_context,
                ),
            ),
        ])
        data = _parse_balancer_payload(raw)
        accepted = data.get("accepted")
        if not isinstance(accepted, bool):
            return fallback
        reasons = _coerce_reasons(data.get("reasons"))
        if not accepted:
            logger.warning("DifficultyBalancer LLM rejected questions: %s", reasons)
        return DifficultyBalancerResult(accepted=accepted, reasons=reasons, source="llm")


def _review_by_rules(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> DifficultyBalancerResult:
    if not questions:
        return DifficultyBalancerResult(False, ["empty_questions"], "rule")
    if not request.difficulty:
        return DifficultyBalancerResult(True, [], "rule")

    reasons: list[str] = []
    for index, question in enumerate(questions, start=1):
        text = _question_text(question)
        if request.difficulty == "easy" and _looks_too_hard(text):
            reasons.append(f"question_{index}_too_hard_for_easy")
        elif request.difficulty == "medium" and (_looks_too_shallow(text) or _looks_too_hard(text)):
            reasons.append(f"question_{index}_difficulty_extreme_for_medium")
        elif request.difficulty == "hard" and _looks_too_shallow(text):
            reasons.append(f"question_{index}_too_shallow_for_hard")

    return DifficultyBalancerResult(not reasons, reasons, "rule")


def _question_text(question: GeneratedQuestion) -> str:
    return _normalize_text(" ".join([
        str(question.content or ""),
        str(question.explanation or ""),
        str(question.difficulty or ""),
    ]))


def _looks_too_hard(text: str) -> bool:
    hits = sum(1 for signal in _HARD_SIGNALS if signal in text)
    return hits >= 2 or any(marker in text for marker in {"综合证明", "综合推导", "多概念联立"})


def _looks_too_shallow(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if any(marker in compact for marker in _TEMPLATE_MARKERS):
        return True
    if len(compact) < 45:
        return True
    has_easy_signal = any(signal in compact for signal in _EASY_SIGNALS)
    has_hard_signal = any(signal in compact for signal in _HARD_SIGNALS)
    return has_easy_signal and not has_hard_signal


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _parse_balancer_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("DifficultyBalancer output is not a JSON object")
    return data


def _coerce_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _question_to_dict(question: GeneratedQuestion) -> dict[str, Any]:
    if hasattr(question, "model_dump"):
        return question.model_dump()
    return question.dict()
