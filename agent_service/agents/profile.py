import json
import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.profile import (
    build_profile_system_prompt,
    build_profile_user_message,
)
from agent_service.schemas.profile import (
    CognitiveBlindspot,
    DisciplineBadge,
    DriveIntent,
    GuidanceLevelSuggestion,
    KnowledgeCoordinate,
    ModalPreference,
    ProfileData,
    ProfileGenerateRequest,
)


def generate_profile_data(request: ProfileGenerateRequest) -> ProfileData:
    return ProfileData(
        modal_preference=_build_modal_preference(request),
        guidance_level_suggestion=_build_guidance_level(request),
        knowledge_coordinates=_build_knowledge_coordinates(request),
        cognitive_blindspots=_build_cognitive_blindspots(request),
        drive_intent=_build_drive_intent(request),
        discipline_badge=_build_discipline_badge(request),
    )


class _ProfileStructuredOutput(BaseModel):
    modal_preference: dict[str, Any] = Field(default_factory=dict)
    guidance_level_suggestion: dict[str, Any] = Field(default_factory=dict)
    knowledge_coordinates: list[dict[str, Any]] = Field(default_factory=list)
    cognitive_blindspots: list[dict[str, Any]] = Field(default_factory=list)
    drive_intent: dict[str, Any] = Field(default_factory=dict)
    discipline_badge: dict[str, Any] = Field(default_factory=dict)


async def generate_profile_with_llm(
    request: ProfileGenerateRequest,
    rule_result: ProfileData,
    chat_provider,
) -> ProfileData | None:
    """尝试用 LLM 增强规则版画像，输入请求、规则结果和 chat provider，输出增强后的 ProfileData 或 None（降级）。

    以 rule_result 为基底，只允许 LLM 增强 guidance_level_suggestion.reason。
    使用 model_copy 构造新对象，不原地修改 rule_result。
    """
    if chat_provider is None:
        return None
    messages = [
        ChatMessage(role="system", content=build_profile_system_prompt()),
        ChatMessage(role="user", content=build_profile_user_message(request, rule_result)),
    ]
    # Phase 1C: 优先尝试 AgentScope structured_model
    try:
        raw = await chat_provider.complete(messages, structured_model=_ProfileStructuredOutput, disable_thinking=True)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                result = _enrich_profile_result(request, rule_result, data)
                logger.info("LLM structured_model succeeded: %s", "profile/generate")
                return result
    except Exception:
        logger.debug("structured_model path failed, falling back to JSON parsing", exc_info=True)
    # Fallback: 原有 markdown fence JSON 解析
    try:
        raw = await chat_provider.complete(messages)
        data = _parse_profile_json(raw)
        result = _enrich_profile_result(request, rule_result, data)
        logger.info("LLM enrichment succeeded: %s", "profile/generate")
        return result
    except Exception:
        logger.warning("LLM profile enrichment failed, falling back to rule-based", exc_info=True)
        return None


def _parse_profile_json(raw: str) -> dict:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _enrich_profile_result(request: ProfileGenerateRequest, rule_result: ProfileData, llm_data: dict) -> ProfileData:
    enriched = rule_result.model_copy(deep=True)
    observed_names = _observed_profile_names(request, rule_result)

    enriched.modal_preference = _coerce_modal_preference(
        llm_data.get("modal_preference"),
        rule_result.modal_preference,
    )
    enriched.guidance_level_suggestion = _coerce_guidance_level(
        llm_data.get("guidance_level_suggestion"),
        rule_result.guidance_level_suggestion,
    )
    enriched.knowledge_coordinates = _coerce_knowledge_coordinates(
        llm_data.get("knowledge_coordinates"),
        rule_result.knowledge_coordinates,
        observed_names,
    )
    enriched.cognitive_blindspots = _coerce_cognitive_blindspots(
        llm_data.get("cognitive_blindspots"),
        rule_result.cognitive_blindspots,
        observed_names,
    )
    enriched.drive_intent = _coerce_drive_intent(
        llm_data.get("drive_intent"),
        rule_result.drive_intent,
    )
    enriched.discipline_badge = _coerce_discipline_badge(
        llm_data.get("discipline_badge"),
        rule_result.discipline_badge,
        request.course_id,
    )

    return enriched


def _extract_llm_reason(llm_data: dict) -> str | None:
    guidance = llm_data.get("guidance_level_suggestion")
    if not isinstance(guidance, dict):
        return None
    reason = guidance.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def _coerce_modal_preference(raw, fallback: ModalPreference | None) -> ModalPreference | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or ModalPreference()
    return ModalPreference(
        video_animation=_coerce_score(raw.get("video_animation"), base.video_animation),
        chart_logic=_coerce_score(raw.get("chart_logic"), base.chart_logic),
        text_analysis=_coerce_score(raw.get("text_analysis"), base.text_analysis),
        code_practice=_coerce_score(raw.get("code_practice"), base.code_practice),
        formula_derivation=_coerce_score(raw.get("formula_derivation"), base.formula_derivation),
    )


def _coerce_guidance_level(raw, fallback: GuidanceLevelSuggestion | None) -> GuidanceLevelSuggestion | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or GuidanceLevelSuggestion()
    recommended = raw.get("recommended")
    if recommended not in _VALID_GUIDANCE_LEVELS:
        recommended = base.recommended
    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = base.reason
    return GuidanceLevelSuggestion(recommended=recommended, reason=reason)


def _coerce_knowledge_coordinates(
    raw,
    fallback: list[KnowledgeCoordinate],
    observed_names: set[str],
) -> list[KnowledgeCoordinate]:
    if not isinstance(raw, list):
        return fallback
    result: list[KnowledgeCoordinate] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if not isinstance(name, str) or name not in observed_names or name in seen:
            continue
        if status not in _VALID_KNOWLEDGE_STATUSES:
            continue
        result.append(KnowledgeCoordinate(name=name, status=status))
        seen.add(name)
    return result or fallback


def _coerce_cognitive_blindspots(
    raw,
    fallback: list[CognitiveBlindspot],
    observed_names: set[str],
) -> list[CognitiveBlindspot]:
    if not isinstance(raw, list):
        return fallback
    result: list[CognitiveBlindspot] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name not in observed_names or name in seen:
            continue
        severity = item.get("severity")
        if severity not in _VALID_BLINDSPOT_SEVERITIES:
            severity = "medium"
        result.append(CognitiveBlindspot(
            name=name,
            error_count=_coerce_non_negative_int(item.get("error_count"), 0),
            severity=severity,
        ))
        seen.add(name)
    return result or fallback


def _coerce_drive_intent(raw, fallback: DriveIntent | None) -> DriveIntent | None:
    if not isinstance(raw, dict):
        return fallback
    intent_type = raw.get("type")
    if intent_type not in _VALID_DRIVE_INTENTS:
        return fallback
    return DriveIntent(
        type=intent_type,
        intensity=_coerce_score(raw.get("intensity"), fallback.intensity if fallback else None),
    )


def _coerce_discipline_badge(
    raw,
    fallback: DisciplineBadge | None,
    course_id: str,
) -> DisciplineBadge | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or DisciplineBadge(subject=course_id, level=None, streak_days=0)
    level = raw.get("level")
    if not isinstance(level, str) or not level.strip():
        level = base.level
    return DisciplineBadge(
        subject=course_id,
        level=level,
        streak_days=_coerce_non_negative_int(raw.get("streak_days"), base.streak_days or 0),
    )


def _observed_profile_names(request: ProfileGenerateRequest, rule_result: ProfileData) -> set[str]:
    names = {item.chapter for item in request.quiz_history if item.chapter}
    names.update(item.name for item in rule_result.knowledge_coordinates)
    names.update(item.name for item in rule_result.cognitive_blindspots)
    return {name for name in names if name}


def _coerce_score(value, fallback: float | None) -> float | None:
    if isinstance(value, int | float):
        return max(0.0, min(100.0, float(value)))
    return fallback


def _coerce_non_negative_int(value, fallback: int) -> int:
    if isinstance(value, int | float):
        coerced = int(value)
        if coerced >= 0:
            return coerced
    return fallback


def _build_modal_preference(request: ProfileGenerateRequest) -> ModalPreference:
    stats = request.resource_usage_stats
    if stats is None:
        return ModalPreference(
            video_animation=0.0,
            chart_logic=0.0,
            text_analysis=0.0,
            code_practice=0.0,
            formula_derivation=0.0,
        )

    counts = [
        stats.video_count or 0,
        stats.document_count or 0,
        stats.code_count or 0,
        stats.quiz_count or 0,
    ]
    max_count = max(counts) if counts else 0

    return ModalPreference(
        video_animation=_score_from_count(stats.video_count, max_count),
        chart_logic=_score_from_count(0, max_count),
        text_analysis=_score_from_count(stats.document_count, max_count),
        code_practice=_score_from_count(stats.code_count, max_count),
        formula_derivation=_score_from_count(0, max_count),
    )


def _build_guidance_level(request: ProfileGenerateRequest) -> GuidanceLevelSuggestion:
    average_score = _average([item.score for item in request.quiz_history])
    if average_score >= 85:
        return GuidanceLevelSuggestion(recommended="L3", reason=f"最近练习平均正确率 {average_score:.1f}%，可减少引导。")
    if average_score >= 60:
        return GuidanceLevelSuggestion(recommended="L2", reason=f"最近练习平均正确率 {average_score:.1f}%，建议保持适中引导。")
    return GuidanceLevelSuggestion(recommended="L1", reason=f"最近练习平均正确率 {average_score:.1f}%，建议加强分步引导。")


def _build_knowledge_coordinates(request: ProfileGenerateRequest) -> list[KnowledgeCoordinate]:
    scores_by_chapter = _scores_by_chapter(request)
    coordinates = []
    for chapter in sorted(scores_by_chapter):
        average_score = _average(scores_by_chapter[chapter])
        status = "mastered" if average_score >= 80 else "learning"
        coordinates.append(KnowledgeCoordinate(name=chapter, status=status))
    return coordinates


def _build_cognitive_blindspots(request: ProfileGenerateRequest) -> list[CognitiveBlindspot]:
    scores_by_chapter = _scores_by_chapter(request)
    blindspots = []
    for chapter in sorted(scores_by_chapter):
        weak_scores = [score for score in scores_by_chapter[chapter] if score < 70]
        if not weak_scores:
            continue
        average_weak_score = _average(weak_scores)
        blindspots.append(
            CognitiveBlindspot(
                name=chapter,
                error_count=len(weak_scores),
                severity=_blindspot_severity(average_weak_score),
            )
        )
    return blindspots


def _build_drive_intent(request: ProfileGenerateRequest) -> DriveIntent:
    data = request.drive_intent_data
    sessions = data.recent_7d_sessions if data else 0
    duration = data.recent_7d_duration if data else 0
    intensity = min(100.0, round((sessions or 0) * 10 + (duration or 0) / 10, 1))

    if intensity >= 80:
        intent_type = "exam_sprint"
    elif intensity >= 30:
        intent_type = "daily_homework"
    else:
        intent_type = "casual"
    return DriveIntent(type=intent_type, intensity=intensity)


def _build_discipline_badge(request: ProfileGenerateRequest) -> DisciplineBadge:
    sessions = request.drive_intent_data.recent_7d_sessions if request.drive_intent_data else 0
    average_score = _average([item.score for item in request.quiz_history])
    if average_score >= 85:
        level = "advanced"
    elif average_score >= 60:
        level = "steady"
    else:
        level = "starter"
    return DisciplineBadge(subject=request.course_id, level=level, streak_days=sessions or 0)


def _scores_by_chapter(request: ProfileGenerateRequest) -> dict[str, list[float]]:
    scores_by_chapter: dict[str, list[float]] = defaultdict(list)
    for item in request.quiz_history:
        if item.chapter:
            scores_by_chapter[item.chapter].append(item.score)
    return scores_by_chapter


def _score_from_count(count: int | None, max_count: int) -> float:
    if max_count <= 0:
        return 0.0
    return round(((count or 0) / max_count) * 100, 1)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def _blindspot_severity(score: float) -> str:
    if score < 50:
        return "high"
    if score < 70:
        return "medium"
    return "low"


logger = get_logger(__name__)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
_VALID_GUIDANCE_LEVELS = {"L1", "L2", "L3"}
_VALID_KNOWLEDGE_STATUSES = {"mastered", "learning"}
_VALID_BLINDSPOT_SEVERITIES = {"high", "medium", "low"}
_VALID_DRIVE_INTENTS = {"exam_sprint", "daily_homework", "casual"}
