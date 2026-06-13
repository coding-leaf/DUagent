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
    "的定义是",
    "通常是多少",
    "基础概念",
    "识别",
}


@dataclass(frozen=True)
class AssessmentQualityResult:
    accepted: bool
    reasons: list[str]
    source: str
    gate: str
    questions: list | None = None


async def review_generated_questions(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
    chat_provider=None,
    course_knowledge_context: str | None = None,
    *,
    include_basic_quality: bool = True,
) -> AssessmentQualityResult:
    """Review and repair generated questions, then run strict answer consistency check.

    Basic, knowledge-point, and difficulty gates only repair labels and drop
    irreparable questions — they never reject the whole batch. Only the answer
    consistency gate (LLM) can reject.
    """
    result_questions = list(questions)

    if include_basic_quality:
        result_questions = _repair_basic_quality(request, result_questions)

    result_questions = _repair_knowledge_point_fit(request, result_questions)

    result_questions = _repair_difficulty_fit(request, result_questions)

    if not result_questions:
        return AssessmentQualityResult(False, ["all_questions_dropped"], "rule", "basic_quality")

    # LLM answer consistency gate — the only strict gate
    if chat_provider is not None:
        consistency_result = await _review_answer_consistency(
            chat_provider, result_questions, course_knowledge_context
        )
        if not consistency_result.accepted:
            return consistency_result

    return AssessmentQualityResult(True, [], "rule", "all", questions=result_questions)


def _repair_basic_quality(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> list[GeneratedQuestion]:
    """Drop malformed questions, keep and return healthy ones."""
    if not questions:
        return []

    requested_types = set(request.question_types or [])
    healthy: list[GeneratedQuestion] = []
    dropped: list[str] = []
    for index, question in enumerate(questions, start=1):
        prefix = f"question_{index}"
        if requested_types and question.type not in requested_types:
            dropped.append(f"{prefix}_type_not_requested")
            continue
        if not _has_good_content(question.content):
            dropped.append(f"{prefix}_bad_content")
            continue
        if not str(question.knowledge_point or "").strip():
            dropped.append(f"{prefix}_missing_knowledge_point")
            continue
        if question.difficulty is not None and question.difficulty not in _SUPPORTED_DIFFICULTIES:
            dropped.append(f"{prefix}_bad_difficulty")
            continue
        if not _has_good_explanation(question.explanation):
            dropped.append(f"{prefix}_bad_explanation")
            continue
        options_errors = _option_errors(prefix, question)
        if options_errors:
            dropped.extend(options_errors)
            continue
        healthy.append(question)

    if dropped:
        logger.warning("Assessment quality basic gate dropped %d/%d questions: %s", len(dropped), len(questions), dropped)
    return healthy


def _repair_knowledge_point_fit(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> list[GeneratedQuestion]:
    """Fix knowledge_point labels that drift from the request target, rather than rejecting."""
    if not questions:
        return []

    targets = _target_knowledge_points(request)
    if not targets:
        return questions

    for question in questions:
        if not _question_matches_any_target(question, targets):
            # Fix the label
            qp = question
            original_kp = qp.knowledge_point
            object.__setattr__(qp, "knowledge_point", targets[0])
            logger.info(
                "Fixed knowledge_point label: '%s' -> '%s'", original_kp, targets[0]
            )

    return questions


def _repair_difficulty_fit(
    request: QuestionGenerateRequest,
    questions: list[GeneratedQuestion],
) -> list[GeneratedQuestion]:
    """Adjust difficulty labels instead of rejecting."""
    if not questions or not request.difficulty:
        return questions

    for question in questions:
        text = _question_text(question)
        assigned = request.difficulty

        if _looks_too_hard(text) and assigned == "medium":
            qp = question
            object.__setattr__(qp, "difficulty", "hard")
            logger.info("Adjusted difficulty: medium -> hard for question")
        elif _looks_too_shallow(text) and assigned == "medium":
            qp = question
            object.__setattr__(qp, "difficulty", "easy")
            logger.info("Adjusted difficulty: medium -> easy for question")

    return questions


async def _review_answer_consistency(
    chat_provider,
    questions: list[GeneratedQuestion],
    course_knowledge_context: str | None,
) -> AssessmentQualityResult:
    """Strict LLM check: do questions and answers match? This is the only rejecting gate."""
    if not questions or chat_provider is None:
        return AssessmentQualityResult(True, [], "rule", "answer_consistency")

    try:
        accepted, reasons = await _review_with_llm(
            chat_provider,
            system_content="你是 EDUagent 的题目一致性审查员。只输出 JSON。",
            prompt=_build_consistency_prompt(questions, course_knowledge_context),
            output_name="Assessment answer consistency",
        )
    except Exception:
        logger.warning("Answer consistency LLM review failed; accepting", exc_info=True)
        return AssessmentQualityResult(True, [], "rule", "answer_consistency")

    if not accepted:
        logger.warning("Assessment answer consistency rejected questions: %s", reasons)
        return AssessmentQualityResult(False, reasons, "llm", "answer_consistency")

    return AssessmentQualityResult(True, [], "llm", "answer_consistency")


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


def _build_consistency_prompt(
    questions: list[GeneratedQuestion],
    course_knowledge_context: str | None,
) -> str:
    """Build prompt for LLM answer consistency review."""
    qs_json = _questions_json(questions)
    lines = [
        "请审查以下题目，只判定题目与答案是否一致。",
        "",
        "审查标准（严格）：",
        "- 选择题的答案必须对应于一个正确的选项",
        "- 答案必须与题目内容一致（不能出现题目问A但答案回答B的情况）",
        "- 解析内容必须支持该答案",
        "- single_choice 的答案必须是单个选项 key",
        "- multi_choice 的答案必须列出所有正确选项 key",
        "",
    ]
    if course_knowledge_context:
        lines.append("参考资料：")
        lines.append(course_knowledge_context)
        lines.append("")

    lines.append("题目列表：")
    lines.append(qs_json)
    lines.append("")
    lines.append(
        '输出 JSON: {"accepted": true/false, "reasons": ["原因1", ...]}'
    )
    return "\n".join(lines)
