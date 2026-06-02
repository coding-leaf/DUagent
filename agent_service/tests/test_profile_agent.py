from agent_service.agents.profile import generate_profile_data
from agent_service.schemas.profile import (
    DriveIntentData,
    ProfileGenerateRequest,
    QuizHistoryItem,
    ResourceUsageStats,
)


def test_generate_profile_data_builds_modal_preference_from_resource_usage() -> None:
    result = generate_profile_data(_build_request())

    assert result.modal_preference is not None
    assert result.modal_preference.video_animation == 50.0
    assert result.modal_preference.text_analysis == 100.0
    assert result.modal_preference.code_practice == 25.0
    assert result.modal_preference.chart_logic == 0.0
    assert result.modal_preference.formula_derivation == 0.0


def test_generate_profile_data_recommends_guidance_level_from_average_score() -> None:
    result = generate_profile_data(_build_request())

    assert result.guidance_level_suggestion is not None
    assert result.guidance_level_suggestion.recommended == "L2"
    assert result.guidance_level_suggestion.reason == "最近练习平均正确率 75.0%，建议保持适中引导。"


def test_generate_profile_data_builds_knowledge_coordinates_and_blindspots() -> None:
    result = generate_profile_data(_build_request())

    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [
        ("函数", "mastered"),
        ("导数", "learning"),
    ]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [
        ("导数", 1, "medium"),
    ]


def test_generate_profile_data_builds_drive_intent_and_badge() -> None:
    result = generate_profile_data(_build_request())

    assert result.drive_intent is not None
    assert result.drive_intent.type == "daily_homework"
    assert result.drive_intent.intensity == 58.0
    assert result.discipline_badge is not None
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "steady"
    assert result.discipline_badge.streak_days == 4


# ── generate_profile_with_llm tests ─────────────────────────────────

import asyncio


class FakeChatProvider:
    def __init__(self, output: str | None = None, should_raise: bool = False, fail_structured: bool = False) -> None:
        self.calls: list[tuple[list, dict]] = []
        self._output = output
        self._should_raise = should_raise
        self._fail_structured = fail_structured

    async def complete(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        if self._fail_structured and "structured_model" in kwargs:
            raise RuntimeError("structured_model failed")
        return self._output


def test_generate_profile_with_llm_enriches_full_profile_data() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    llm_output = _json.dumps({
        "modal_preference": {
            "video_animation": 60.0,
            "chart_logic": 35.0,
            "text_analysis": 90.0,
            "code_practice": 45.0,
            "formula_derivation": 20.0,
        },
        "guidance_level_suggestion": {
            "recommended": "L1",
            "reason": "导数最近只有60%，且资源使用偏文档，建议用更细的步骤和例题拆解极限到导数的过渡。",
        },
        "knowledge_coordinates": [
            {"name": "函数", "status": "mastered"},
            {"name": "导数", "status": "learning"},
        ],
        "cognitive_blindspots": [
            {"name": "导数", "error_count": 2, "severity": "high"},
        ],
        "drive_intent": {"type": "exam_sprint", "intensity": 82.0},
        "discipline_badge": {"subject": "course-1", "level": "sprint", "streak_days": 5},
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(
        generate_profile_with_llm(request, rule_result, provider)
    )

    assert result is not None
    assert "structured_model" in provider.calls[0][1]
    assert result.modal_preference.video_animation == 60.0
    assert result.modal_preference.text_analysis == 90.0
    assert result.guidance_level_suggestion.recommended == "L1"
    assert "导数最近只有60%" in (result.guidance_level_suggestion.reason or "")
    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [
        ("函数", "mastered"),
        ("导数", "learning"),
    ]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [
        ("导数", 2, "high"),
    ]
    assert result.drive_intent.type == "exam_sprint"
    assert result.drive_intent.intensity == 82.0
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "sprint"
    assert result.discipline_badge.streak_days == 5


def test_generate_profile_with_llm_structured_model_fails_and_falls_back() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    llm_output = f"```json\n{_json.dumps({'modal_preference': {'video_animation': 80.0}})}\n```"
    provider = FakeChatProvider(output=llm_output, fail_structured=True)

    result = asyncio.run(
        generate_profile_with_llm(request, rule_result, provider)
    )

    assert result is not None
    assert len(provider.calls) == 2
    assert "structured_model" in provider.calls[0][1]
    assert "structured_model" not in provider.calls[1][1]
    assert result.modal_preference.video_animation == 80.0


def test_generate_profile_with_llm_rejects_invalid_or_fabricated_fields() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    llm_output = _json.dumps({
        "modal_preference": {
            "video_animation": 999.0,
            "text_analysis": -20.0,
        },
        "guidance_level_suggestion": {
            "recommended": "L9",
            "reason": "保留这个有效理由。",
        },
        "knowledge_coordinates": [
            {"name": "fabricated", "status": "mastered"},
            {"name": "函数", "status": "invalid"},
            {"name": "导数", "status": "learning"},
        ],
        "cognitive_blindspots": [
            {"name": "fabricated", "error_count": 99, "severity": "high"},
            {"name": "导数", "error_count": -3, "severity": "invalid"},
        ],
        "drive_intent": {"type": "invalid", "intensity": 500.0},
        "discipline_badge": {"subject": "hacked", "level": "advanced", "streak_days": -1},
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(
        generate_profile_with_llm(request, rule_result, provider)
    )

    assert result is not None
    assert result.modal_preference.video_animation == 100.0
    assert result.modal_preference.text_analysis == 0.0
    assert result.guidance_level_suggestion.recommended == "L2"
    assert result.guidance_level_suggestion.reason == "保留这个有效理由。"
    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [("导数", "learning")]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [("导数", 0, "medium")]
    assert result.drive_intent == rule_result.drive_intent
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "advanced"
    assert result.discipline_badge.streak_days == rule_result.discipline_badge.streak_days


def test_generate_profile_with_llm_fills_missing_fields_from_rule_result() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    provider = FakeChatProvider(output=_json.dumps({
        "guidance_level_suggestion": {
            "reason": "只增强理由，其余字段沿用规则结果。",
        },
    }))

    result = asyncio.run(generate_profile_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.guidance_level_suggestion.reason == "只增强理由，其余字段沿用规则结果。"
    assert result.guidance_level_suggestion.recommended == rule_result.guidance_level_suggestion.recommended
    assert result.modal_preference == rule_result.modal_preference
    assert result.knowledge_coordinates == rule_result.knowledge_coordinates
    assert result.cognitive_blindspots == rule_result.cognitive_blindspots
    assert result.drive_intent == rule_result.drive_intent
    assert result.discipline_badge == rule_result.discipline_badge


def test_generate_profile_with_llm_does_not_mutate_rule_result() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    rule_result = generate_profile_data(_build_request())
    original_reason = rule_result.guidance_level_suggestion.reason

    llm_output = _json.dumps({
        "guidance_level_suggestion": {
            "reason": "新的个性化理由。",
        },
    })
    provider = FakeChatProvider(output=llm_output)

    _result = asyncio.run(
        generate_profile_with_llm(_build_request(), rule_result, provider)
    )

    assert rule_result.guidance_level_suggestion.reason == original_reason


def test_generate_profile_with_llm_returns_none_when_chat_provider_is_none() -> None:
    from agent_service.agents.profile import generate_profile_with_llm

    rule_result = generate_profile_data(_build_request())
    result = asyncio.run(
        generate_profile_with_llm(_build_request(), rule_result, None)
    )
    assert result is None


def test_generate_profile_with_llm_returns_none_on_invalid_json() -> None:
    from agent_service.agents.profile import generate_profile_with_llm

    rule_result = generate_profile_data(_build_request())
    provider = FakeChatProvider(output="not valid json at all")
    result = asyncio.run(
        generate_profile_with_llm(_build_request(), rule_result, provider)
    )
    assert result is None


def test_generate_profile_with_llm_returns_none_on_exception(caplog) -> None:
    from agent_service.agents.profile import generate_profile_with_llm

    rule_result = generate_profile_data(_build_request())
    with caplog.at_level("WARNING", logger="agent_service.agents.profile"):
        result = asyncio.run(
            generate_profile_with_llm(_build_request(), rule_result, FakeChatProvider(should_raise=True))
        )
    assert result is None
    assert "LLM profile enrichment failed" in caplog.text


def test_generate_profile_with_llm_handles_markdown_wrapped_json() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    rule_result = generate_profile_data(_build_request())
    payload = _json.dumps({
        "guidance_level_suggestion": {
            "reason": "markdown 包裹的个性化理由。",
        },
    })
    provider = FakeChatProvider(output=f"```json\n{payload}\n```")

    result = asyncio.run(
        generate_profile_with_llm(_build_request(), rule_result, provider)
    )

    assert result is not None
    assert result.guidance_level_suggestion.reason == "markdown 包裹的个性化理由。"
    assert result.guidance_level_suggestion.recommended == "L2"


def test_profile_api_endpoint_falls_back_to_rule_on_llm_none() -> None:
    from unittest.mock import patch

    from agent_service.api.v1.profile import generate_profile

    rule_result = generate_profile_data(_build_request())

    async def _fake_llm(_request, _rule_result, _chat_provider):
        return None

    with patch("agent_service.api.v1.profile.generate_profile_with_llm", _fake_llm):
        response = asyncio.run(generate_profile(_build_request()))

    assert response.code == 200
    assert response.data is not None
    assert response.data.guidance_level_suggestion == rule_result.guidance_level_suggestion
    assert response.data.modal_preference == rule_result.modal_preference


def _build_request() -> ProfileGenerateRequest:
    return ProfileGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        quiz_history=[
            QuizHistoryItem(score=90, chapter="函数", created_at="2026-05-20T10:00:00Z"),
            QuizHistoryItem(score=60, chapter="导数", created_at="2026-05-21T10:00:00Z"),
        ],
        resource_usage_stats=ResourceUsageStats(
            video_count=2,
            document_count=4,
            code_count=1,
            quiz_count=3,
        ),
        drive_intent_data=DriveIntentData(recent_7d_sessions=4, recent_7d_duration=180),
    )
