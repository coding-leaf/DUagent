"""Unified quality gates for assessment question generation.

The public entry point accepts the generation request and coerced questions,
then returns whether the caller can use those questions or should continue the
existing fallback chain.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import (
    build_difficulty_balancer_prompt,
    build_knowledge_point_guard_prompt,
    build_question_critic_prompt,
)
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest

logger = get_logger(__name__)

_SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}
_CHOICE_TYPES = {"single_choice", "multi_choice"}
_GENERIC_EXPLANATIONS = {"正确", "答案正确", "解析", "见解析", "略", "无"}
_QUALITY_TEMPLATE_MARKERS = {"占位", "模板", "请完成", "题目内容", "待生成"}
_DIFFICULTY_TEMPLATE_MARKERS = {"请围绕", "完成一道", "模板", "占位", "待生成"}
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


@dataclass(frozen=True)
class AssessmentQualityResult:
    accepted: bool
    reasons: list[str]
    source: str
    gate: str


async def review_generated_questions(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
    chat_provider=None,
    course_knowledge_context: str | None = None,
    *,
    include_basic_quality: bool = True,
) -> AssessmentQualityResult:
    """Review generated questions and return whether they can be used.

    Inputs are the original request, coerced questions, optional chat provider,
    and optional RAG context. Output is a structured quality result used by the
    assessment fallback chain.
    """
    if include_basic_quality:
        basic_result = await _review_basic_quality(
            request, questions, chat_provider, course_knowledge_context
        )
        if not basic_result.accepted:
            return basic_result

    knowledge_result = await _review_knowledge_point_fit(
        request, questions, chat_provider, course_knowledge_context
    )
    if not knowledge_result.accepted:
        return knowledge_result

    difficulty_result = await _review_difficulty_fit(
        request, questions, chat_provider, course_knowledge_context
    )
    if not difficulty_result.accepted:
        return difficulty_result

    return AssessmentQualityResult(True, [], "rule", "all")


async def _review_basic_quality(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
    chat_provider,
    course_knowledge_context: str | None,
) -> AssessmentQualityResult:
    rule_errors = _basic_quality_errors(request, questions)
    if rule_errors:
        logger.warning("Assessment quality basic gate rejected questions: %s", rule_errors)
        return AssessmentQualityResult(False, rule_errors, "rule", "basic_quality")
    if chat_provider is None:
        return AssessmentQualityResult(True, [], "rule", "basic_quality")
    try:
        accepted, reasons = await _review_with_llm(
            chat_provider,
            system_content="你是严格但稳定的出题质量审查员。只输出 JSON。",
            prompt=build_question_critic_prompt(
                request,
                _questions_json(questions),
                course_knowledge_context=course_knowledge_context,
            ),
            output_name="Assessment basic quality",
        )
    except Exception:
        logger.warning(
            "Assessment quality basic LLM review failed; accepting rule-passed questions",
            exc_info=True,
        )
        return AssessmentQualityResult(True, [], "rule", "basic_quality")
    if not accepted:
        logger.warning("Assessment quality basic LLM rejected questions: %s", reasons)
        return AssessmentQualityResult(False, reasons, "llm", "basic_quality")
    return AssessmentQualityResult(True, [], "llm", "basic_quality")


async def _review_knowledge_point_fit(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
    chat_provider,
    course_knowledge_context: str | None,
) -> AssessmentQualityResult:
    rule_result = _review_knowledge_by_rules(request, questions)
    if not rule_result.accepted:
        logger.warning("Assessment quality knowledge gate rejected questions: %s", rule_result.reasons)
        return rule_result
    if chat_provider is None:
        return rule_result
    try:
        accepted, reasons = await _review_with_llm(
            chat_provider,
            system_content="你是 EDUagent 的知识点贴合度审查员。只输出 JSON。",
            prompt=build_knowledge_point_guard_prompt(
                request,
                _questions_json(questions),
                course_knowledge_context=course_knowledge_context,
            ),
            output_name="Assessment knowledge point",
        )
    except Exception:
        logger.warning("Assessment quality knowledge LLM review failed; using rule result", exc_info=True)
        return rule_result
    if not accepted:
        logger.warning("Assessment quality knowledge LLM rejected questions: %s", reasons)
        return AssessmentQualityResult(False, reasons, "llm", "knowledge_point")
    return AssessmentQualityResult(True, [], "llm", "knowledge_point")


async def _review_difficulty_fit(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
    chat_provider,
    course_knowledge_context: str | None,
) -> AssessmentQualityResult:
    rule_result = _review_difficulty_by_rules(request, questions)
    if not rule_result.accepted:
        logger.warning("Assessment quality difficulty gate rejected questions: %s", rule_result.reasons)
        return rule_result
    if chat_provider is None:
        return rule_result
    try:
        accepted, reasons = await _review_with_llm(
            chat_provider,
            system_content="你是 EDUagent 的题目难度审查员。只输出 JSON。",
            prompt=build_difficulty_balancer_prompt(
                request,
                _questions_json(questions),
                course_knowledge_context=course_knowledge_context,
            ),
            output_name="Assessment difficulty",
        )
    except Exception:
        logger.warning("Assessment quality difficulty LLM review failed; using rule result", exc_info=True)
        return rule_result
    if not accepted:
        logger.warning("Assessment quality difficulty LLM rejected questions: %s", reasons)
        return AssessmentQualityResult(False, reasons, "llm", "difficulty")
    return AssessmentQualityResult(True, [], "llm", "difficulty")


async def _review_with_llm(
    chat_provider,
    *,
    system_content: str,
    prompt: str,
    output_name: str,
) -> tuple[bool, list[str]]:
    raw = await chat_provider.complete([
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user", content=prompt),
    ])
    data = _parse_json_object(raw, output_name)
    accepted = data.get("accepted")
    if not isinstance(accepted, bool):
        return True, []
    return accepted, _coerce_reasons(data.get("reasons"))


def _basic_quality_errors(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> list[str]:
    errors: list[str] = []
    if not questions:
        return ["empty_questions"]
    requested_types = set(request.question_types or [])
    for index, question in enumerate(questions, start=1):
        prefix = f"question_{index}"
        if requested_types and question.type not in requested_types:
            errors.append(f"{prefix}_type_not_requested")
        if not _has_good_content(question.content):
            errors.append(f"{prefix}_bad_content")
        if not str(question.knowledge_point or "").strip():
            errors.append(f"{prefix}_missing_knowledge_point")
        if question.difficulty is not None and question.difficulty not in _SUPPORTED_DIFFICULTIES:
            errors.append(f"{prefix}_bad_difficulty")
        if not _has_good_explanation(question.explanation):
            errors.append(f"{prefix}_bad_explanation")
        errors.extend(_option_errors(prefix, question))
    return errors


def _option_errors(prefix: str, question: GeneratedQuestion) -> list[str]:
    if question.type in _CHOICE_TYPES:
        keys = [
            str(option.key or "").strip()
            for option in question.options
            if str(option.key or "").strip()
        ]
        texts = [
            str(option.text or "").strip()
            for option in question.options
            if str(option.text or "").strip()
        ]
        if len(question.options) != 4:
            return [f"{prefix}_choice_options_count"]
        if len(set(keys)) != 4 or len(set(texts)) != 4:
            return [f"{prefix}_choice_options_not_unique"]
        if question.type == "single_choice" and str(question.answer).strip() not in set(keys):
            return [f"{prefix}_single_choice_answer_not_in_options"]
        if question.type == "multi_choice":
            answers = question.answer if isinstance(question.answer, list) else []
            normalized = {str(answer).strip() for answer in answers if str(answer).strip()}
            if not normalized or not normalized.issubset(set(keys)):
                return [f"{prefix}_multi_choice_answer_not_in_options"]
        return []
    if question.options:
        return [f"{prefix}_non_choice_has_options"]
    return []


def _has_good_content(content: str) -> bool:
    text = str(content or "").strip()
    if len(text) < 8:
        return False
    return not any(marker in text for marker in _QUALITY_TEMPLATE_MARKERS)


def _has_good_explanation(explanation: str) -> bool:
    text = str(explanation or "").strip().rstrip("。.")
    if len(text) < 8:
        return False
    return text not in _GENERIC_EXPLANATIONS


def _review_knowledge_by_rules(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> AssessmentQualityResult:
    if not questions:
        return AssessmentQualityResult(False, ["empty_questions"], "rule", "knowledge_point")

    targets = _target_knowledge_points(request)
    if not targets:
        return AssessmentQualityResult(True, [], "rule", "knowledge_point")

    reasons: list[str] = []
    for index, question in enumerate(questions, start=1):
        if not _question_matches_any_target(question, targets):
            reasons.append(f"question_{index}_target_mismatch")

    return AssessmentQualityResult(not reasons, reasons, "rule", "knowledge_point")


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


def _review_difficulty_by_rules(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> AssessmentQualityResult:
    if not questions:
        return AssessmentQualityResult(False, ["empty_questions"], "rule", "difficulty")
    if not request.difficulty:
        return AssessmentQualityResult(True, [], "rule", "difficulty")

    reasons: list[str] = []
    for index, question in enumerate(questions, start=1):
        text = _question_text(question)
        if request.difficulty == "easy" and _looks_too_hard(text):
            reasons.append(f"question_{index}_too_hard_for_easy")
        elif request.difficulty == "medium" and (_looks_too_shallow(text) or _looks_too_hard(text)):
            reasons.append(f"question_{index}_difficulty_extreme_for_medium")
        elif request.difficulty == "hard" and _looks_too_shallow(text):
            reasons.append(f"question_{index}_too_shallow_for_hard")

    return AssessmentQualityResult(not reasons, reasons, "rule", "difficulty")


def _question_text(question: GeneratedQuestion) -> str:
    option_texts = " ".join(str(opt.text or "") for opt in (question.options or []))
    return _normalize_text(" ".join([
        str(question.content or ""),
        option_texts,
        str(question.explanation or ""),
        str(question.difficulty or ""),
    ]))


def _looks_too_hard(text: str) -> bool:
    hits = sum(1 for signal in _HARD_SIGNALS if signal in text)
    return hits >= 2 or any(marker in text for marker in {"综合证明", "综合推导", "多概念联立"})


def _looks_too_shallow(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if any(marker in compact for marker in _DIFFICULTY_TEMPLATE_MARKERS):
        return True
    if len(compact) < 45:
        return True
    has_easy_signal = any(signal in compact for signal in _EASY_SIGNALS)
    has_hard_signal = any(signal in compact for signal in _HARD_SIGNALS)
    return has_easy_signal and not has_hard_signal


def _parse_json_object(raw: str, output_name: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{output_name} output is not a JSON object")
    return data


def _coerce_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _questions_json(questions: list[GeneratedQuestion]) -> str:
    return json.dumps([_question_to_dict(question) for question in questions], ensure_ascii=False)


def _question_to_dict(question: GeneratedQuestion) -> dict[str, Any]:
    if hasattr(question, "model_dump"):
        return question.model_dump()
    return question.dict()


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
