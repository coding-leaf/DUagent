import json
import re
from collections import defaultdict

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
    try:
        messages = [
            ChatMessage(role="system", content=build_profile_system_prompt()),
            ChatMessage(role="user", content=build_profile_user_message(request, rule_result)),
        ]
        raw = await chat_provider.complete(messages)
        data = _parse_profile_json(raw)
        return _enrich_profile_result(rule_result, data)
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


def _enrich_profile_result(rule_result: ProfileData, llm_data: dict) -> ProfileData:
    enriched = rule_result.model_copy(deep=True)

    llm_reason = _extract_llm_reason(llm_data)
    if llm_reason and enriched.guidance_level_suggestion:
        enriched.guidance_level_suggestion = GuidanceLevelSuggestion(
            recommended=enriched.guidance_level_suggestion.recommended,
            reason=llm_reason,
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
