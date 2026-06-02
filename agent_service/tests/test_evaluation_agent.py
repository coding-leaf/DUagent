from agent_service.agents.evaluation import generate_evaluation_data
from agent_service.schemas.evaluation import (
    ChapterProgressItem,
    EvaluationGenerateRequest,
    LearningProgress,
    QuizResultItem,
    ResourceUsage,
)


def test_generate_evaluation_data_builds_progress_table() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.progress_table is not None
    assert [column.key for column in result.progress_table.columns] == [
        "chapter",
        "completion_rate",
        "time_spent",
    ]
    assert result.progress_table.rows == [
        {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120},
        {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60},
    ]


def test_generate_evaluation_data_builds_mastery_table_from_quizzes() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.mastery_table is not None
    assert [column.key for column in result.mastery_table.columns] == [
        "chapter",
        "average_score",
        "quiz_count",
        "mastery_level",
    ]
    assert result.mastery_table.rows == [
        {"chapter": "函数", "average_score": 90.0, "quiz_count": 1, "mastery_level": "strong"},
        {"chapter": "导数", "average_score": 55.0, "quiz_count": 1, "mastery_level": "weak"},
    ]


def test_generate_evaluation_data_builds_resource_usage_table() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.resource_usage_table is not None
    assert [column.key for column in result.resource_usage_table.columns] == [
        "resource_type",
        "count",
    ]
    assert result.resource_usage_table.rows == [
        {"resource_type": "document", "count": 3},
        {"resource_type": "video", "count": 1},
    ]


def test_generate_evaluation_data_builds_summary_text() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.summary_text == "已学习 2 个章节，平均完成率 60.0%，平均练习正确率 72.5%。薄弱章节：导数。"


# ── generate_evaluation_with_llm tests ─────────────────────────────

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


def test_generate_evaluation_with_llm_enriches_full_evaluation_data() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    request = _build_request()
    rule_result = generate_evaluation_data(request)
    llm_output = _json.dumps({
        "progress_table": {
            "columns": [
                {"key": "chapter", "title": "章节"},
                {"key": "completion_rate", "title": "完成率"},
                {"key": "time_spent", "title": "学习时长（分钟）"},
                {"key": "progress_insight", "title": "进度分析"},
            ],
            "rows": [
                {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120, "progress_insight": "进度稳定"},
                {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60, "progress_insight": "进度偏慢"},
            ],
        },
        "mastery_table": {
            "columns": [
                {"key": "chapter", "title": "章节"},
                {"key": "average_score", "title": "平均正确率"},
                {"key": "quiz_count", "title": "练习次数"},
                {"key": "mastery_level", "title": "掌握水平"},
                {"key": "root_cause", "title": "薄弱根因"},
            ],
            "rows": [
                {"chapter": "函数", "average_score": 90.0, "quiz_count": 1, "mastery_level": "strong", "root_cause": "基础稳定"},
                {"chapter": "导数", "average_score": 55.0, "quiz_count": 1, "mastery_level": "weak", "root_cause": "极限概念不牢"},
            ],
        },
        "resource_usage_table": {
            "columns": [
                {"key": "resource_type", "title": "资源类型"},
                {"key": "count", "title": "使用次数"},
                {"key": "effectiveness_hint", "title": "效果提示"},
            ],
            "rows": [
                {"resource_type": "document", "count": 3, "effectiveness_hint": "文档偏多但导数仍弱"},
                {"resource_type": "video", "count": 1, "effectiveness_hint": "可增加视频辅助理解"},
            ],
        },
        "summary_text": "导数正确率55%，较函数90%明显偏低，建议增加视频讲解和代码练习。",
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(generate_evaluation_with_llm(request, rule_result, provider))

    assert result is not None
    assert "structured_model" in provider.calls[0][1]
    assert result.progress_table.rows[1]["progress_insight"] == "进度偏慢"
    assert result.mastery_table.rows[1]["root_cause"] == "极限概念不牢"
    assert result.resource_usage_table.rows[1]["effectiveness_hint"] == "可增加视频辅助理解"
    assert "导数正确率55%" in (result.summary_text or "")


def test_generate_evaluation_with_llm_structured_model_fails_and_falls_back() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    request = _build_request()
    rule_result = generate_evaluation_data(request)
    llm_output = f"```json\n{_json.dumps({'summary_text': '回落后总结'})}\n```"
    provider = FakeChatProvider(output=llm_output, fail_structured=True)

    result = asyncio.run(generate_evaluation_with_llm(request, rule_result, provider))

    assert result is not None
    assert len(provider.calls) == 2
    assert "structured_model" in provider.calls[0][1]
    assert "structured_model" not in provider.calls[1][1]
    assert result.summary_text == "回落后总结"


def test_generate_evaluation_with_llm_rejects_invalid_or_fabricated_rows() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    request = _build_request()
    rule_result = generate_evaluation_data(request)
    provider = FakeChatProvider(output=_json.dumps({
        "progress_table": {
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "completion_rate", "title": "完成率"}],
            "rows": [
                {"chapter": "fabricated", "completion_rate": 99},
                {"chapter": "导数", "completion_rate": 180, "time_spent": -1, "progress_insight": "保留有效章节"},
            ],
        },
        "mastery_table": {
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "average_score", "title": "平均正确率"}],
            "rows": [
                {"chapter": "fabricated", "average_score": 100},
                {"chapter": "导数", "average_score": -5, "quiz_count": -2, "mastery_level": "invalid"},
            ],
        },
        "resource_usage_table": {
            "columns": [{"key": "resource_type", "title": "资源类型"}, {"key": "count", "title": "使用次数"}],
            "rows": [
                {"resource_type": "unknown", "count": 9},
                {"resource_type": "video", "count": -3, "effectiveness_hint": "保留有效资源"},
            ],
        },
        "summary_text": "有效总结。",
    }))

    result = asyncio.run(generate_evaluation_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.progress_table.rows == [{"chapter": "导数", "completion_rate": 100.0, "time_spent": 0, "progress_insight": "保留有效章节"}]
    assert result.mastery_table.rows == [{"chapter": "导数", "average_score": 0.0, "quiz_count": 0, "mastery_level": "weak"}]
    assert result.resource_usage_table.rows == [{"resource_type": "video", "count": 0, "effectiveness_hint": "保留有效资源"}]
    assert result.summary_text == "有效总结。"


def test_generate_evaluation_with_llm_does_not_mutate_rule_result() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    rule_result = generate_evaluation_data(_build_request())
    original_summary = rule_result.summary_text

    llm_output = _json.dumps({"summary_text": "新的总结。"})
    provider = FakeChatProvider(output=llm_output)

    _result = asyncio.run(
        generate_evaluation_with_llm(_build_request(), rule_result, provider)
    )

    assert rule_result.summary_text == original_summary


def test_generate_evaluation_with_llm_returns_none_when_chat_provider_is_none() -> None:
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    rule_result = generate_evaluation_data(_build_request())
    result = asyncio.run(
        generate_evaluation_with_llm(_build_request(), rule_result, None)
    )
    assert result is None


def test_generate_evaluation_with_llm_returns_none_on_invalid_json() -> None:
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    rule_result = generate_evaluation_data(_build_request())
    provider = FakeChatProvider(output="not valid json")
    result = asyncio.run(
        generate_evaluation_with_llm(_build_request(), rule_result, provider)
    )
    assert result is None


def test_generate_evaluation_with_llm_returns_none_on_exception(caplog) -> None:
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    rule_result = generate_evaluation_data(_build_request())
    with caplog.at_level("WARNING", logger="agent_service.agents.evaluation"):
        result = asyncio.run(
            generate_evaluation_with_llm(_build_request(), rule_result, FakeChatProvider(should_raise=True))
        )
    assert result is None
    assert "LLM evaluation enrichment failed" in caplog.text


def test_generate_evaluation_with_llm_handles_markdown_wrapped_json() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    rule_result = generate_evaluation_data(_build_request())
    payload = _json.dumps({"summary_text": "markdown 包裹的总结。"})
    provider = FakeChatProvider(output=f"```json\n{payload}\n```")

    result = asyncio.run(
        generate_evaluation_with_llm(_build_request(), rule_result, provider)
    )

    assert result is not None
    assert result.summary_text == "markdown 包裹的总结。"


def test_evaluation_api_endpoint_falls_back_to_rule_on_llm_none() -> None:
    from unittest.mock import patch

    from agent_service.api.v1.evaluation import generate_evaluation

    rule_result = generate_evaluation_data(_build_request())

    async def _fake_llm(_request, _rule_result, _chat_provider):
        return None

    with patch("agent_service.api.v1.evaluation.generate_evaluation_with_llm", _fake_llm):
        response = asyncio.run(generate_evaluation(_build_request()))

    assert response.code == 200
    assert response.data is not None
    assert response.data.summary_text == rule_result.summary_text
    assert response.data.progress_table == rule_result.progress_table


def _build_request() -> EvaluationGenerateRequest:
    return EvaluationGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        learning_progress=LearningProgress(
            chapter_progress=[
                ChapterProgressItem(chapter="函数", completion_rate=80, time_spent=120),
                ChapterProgressItem(chapter="导数", completion_rate=40, time_spent=60),
            ]
        ),
        quiz_results=[
            QuizResultItem(chapter="函数", score=90, created_at="2026-05-20T10:00:00Z"),
            QuizResultItem(chapter="导数", score=55, created_at="2026-05-21T10:00:00Z"),
        ],
        resource_usage=ResourceUsage(by_type={"document": 3, "video": 1}),
    )
