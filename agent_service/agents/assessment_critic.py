"""Assessment question quality critic for ReAct-generated questions."""

from __future__ import annotations

import json
from typing import Any

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import build_question_critic_prompt
from agent_service.schemas.assessment import GeneratedQuestion, QuestionGenerateRequest

logger = get_logger(__name__)

_SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}
_CHOICE_TYPES = {"single_choice", "multi_choice"}
_GENERIC_EXPLANATIONS = {"正确", "答案正确", "解析", "见解析", "略", "无"}
_TEMPLATE_MARKERS = {"占位", "模板", "请完成", "题目内容", "待生成"}


class QuestionCriticAgent:
    """Hybrid quality gate for generated questions.

    Inputs are the original generation request, coerced questions, optional RAG
    context, and optional chat provider. Output is True when questions can be
    returned, False when caller should fall back to the existing LLM path.
    """

    def __init__(self, chat_provider=None) -> None:
        self._chat_provider = chat_provider

    async def review(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None = None,
    ) -> bool:
        rule_errors = _rule_quality_errors(request, questions)
        if rule_errors:
            logger.warning("QuestionCritic rule gate rejected questions: %s", rule_errors)
            return False
        if self._chat_provider is None:
            return True
        try:
            return await self._review_with_llm(
                request,
                questions,
                course_knowledge_context=course_knowledge_context,
            )
        except Exception:
            logger.warning("QuestionCritic LLM review failed; accepting rule-passed questions", exc_info=True)
            return True

    async def _review_with_llm(
        self,
        request: QuestionGenerateRequest,
        questions: list[GeneratedQuestion],
        course_knowledge_context: str | None = None,
    ) -> bool:
        questions_json = json.dumps(
            [_question_to_dict(question) for question in questions],
            ensure_ascii=False,
        )
        raw = await self._chat_provider.complete([
            ChatMessage(
                role="system",
                content="你是严格但稳定的出题质量审查员。只输出 JSON。",
            ),
            ChatMessage(
                role="user",
                content=build_question_critic_prompt(
                    request,
                    questions_json,
                    course_knowledge_context=course_knowledge_context,
                ),
            ),
        ])
        data = _parse_critic_payload(raw)
        accepted = data.get("accepted")
        if accepted is False:
            logger.warning("QuestionCritic LLM rejected questions: %s", data.get("reasons"))
            return False
        return True


def _rule_quality_errors(
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
    return not any(marker in text for marker in _TEMPLATE_MARKERS)


def _has_good_explanation(explanation: str) -> bool:
    text = str(explanation or "").strip().rstrip("。.")
    if len(text) < 8:
        return False
    return text not in _GENERIC_EXPLANATIONS


def _parse_critic_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("QuestionCritic output is not a JSON object")
    return data


def _question_to_dict(question: GeneratedQuestion) -> dict[str, Any]:
    if hasattr(question, "model_dump"):
        return question.model_dump()
    return question.dict()
