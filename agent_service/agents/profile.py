from collections import defaultdict

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
