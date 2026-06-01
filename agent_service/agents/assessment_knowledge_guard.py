"""Knowledge point guard for generated assessment questions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import build_knowledge_point_guard_prompt
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest

logger = get_logger(__name__)


@dataclass(frozen=True)
class KnowledgePointGuardResult:
    accepted: bool
    reasons: list[str]
    source: str


class KnowledgePointGuard:
    """审查生成题是否贴合请求知识点，输入请求和题目列表，输出是否接受及原因。"""

    def __init__(self, chat_provider=None) -> None:
        self._chat_provider = chat_provider

    async def review(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None = None,
    ) -> KnowledgePointGuardResult:
        rule_result = _review_by_rules(request, questions)
        if not rule_result.accepted:
            logger.warning("KnowledgePointGuard rule gate rejected questions: %s", rule_result.reasons)
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
            logger.warning("KnowledgePointGuard LLM review failed; using rule result", exc_info=True)
            return rule_result

    async def _review_with_llm(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None,
        fallback: KnowledgePointGuardResult,
    ) -> KnowledgePointGuardResult:
        questions_json = json.dumps(
            [_question_to_dict(question) for question in questions],
            ensure_ascii=False,
        )
        raw = await self._chat_provider.complete([
            ChatMessage(role="system", content="你是 EDUagent 的知识点贴合度审查员。只输出 JSON。"),
            ChatMessage(
                role="user",
                content=build_knowledge_point_guard_prompt(
                    request,
                    questions_json,
                    course_knowledge_context=course_knowledge_context,
                ),
            ),
        ])
        data = _parse_guard_payload(raw)
        accepted = data.get("accepted")
        if not isinstance(accepted, bool):
            return fallback
        reasons = _coerce_reasons(data.get("reasons"))
        if not accepted:
            logger.warning("KnowledgePointGuard LLM rejected questions: %s", reasons)
        return KnowledgePointGuardResult(accepted=accepted, reasons=reasons, source="llm")


def _review_by_rules(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> KnowledgePointGuardResult:
    if not questions:
        return KnowledgePointGuardResult(False, ["empty_questions"], "rule")

    targets = _target_knowledge_points(request)
    if not targets:
        return KnowledgePointGuardResult(True, [], "rule")

    reasons: list[str] = []
    for index, question in enumerate(questions, start=1):
        if not _question_matches_any_target(question, targets):
            reasons.append(f"question_{index}_target_mismatch")

    return KnowledgePointGuardResult(not reasons, reasons, "rule")


def _target_knowledge_points(request: QuestionGenerateRequest) -> list[str]:
    if request.knowledge_point and request.knowledge_point.strip():
        return [request.knowledge_point.strip()]

    context = request.personalization_context or {}
    wrong_points = context.get("wrong_points")
    targets: list[str] = []
    if isinstance(wrong_points, list):
        for item in wrong_points:
            if isinstance(item, str) and item.strip():
                targets.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("knowledge_point")
                if isinstance(name, str) and name.strip():
                    targets.append(name.strip())
    return _dedupe_preserving_order(targets)


def _question_matches_any_target(question: GeneratedQuestion, targets: list[str]) -> bool:
    fields = [
        question.knowledge_point,
        question.content,
        question.explanation,
    ]
    haystacks = [_normalize_text(field) for field in fields if field]
    for target in targets:
        normalized_target = _normalize_text(target)
        if normalized_target and any(_is_related_text(normalized_target, haystack) for haystack in haystacks):
            return True
    return False


def _is_related_text(target: str, haystack: str) -> bool:
    if target in haystack:
        return True
    if len(target) <= 2:
        return False
    bigrams = {target[index : index + 2] for index in range(len(target) - 1)}
    if not bigrams:
        return False
    hits = sum(1 for token in bigrams if token in haystack)
    return hits / len(bigrams) >= 0.67


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = _normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _parse_guard_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("KnowledgePointGuard output is not a JSON object")
    return data


def _coerce_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _question_to_dict(question: GeneratedQuestion) -> dict[str, Any]:
    if hasattr(question, "model_dump"):
        return question.model_dump()
    return question.dict()
