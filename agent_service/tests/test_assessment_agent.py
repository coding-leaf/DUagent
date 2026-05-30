from agent_service.agents import assessment
from agent_service.agents.assessment import evaluate_assessment_data
from agent_service.schemas.assessment import (
    AssessmentAnswer,
    AssessmentEvaluateRequest,
    AssessmentQuestion,
    QuestionGenerateRequest,
)


def test_evaluate_assessment_marks_string_answer_correct() -> None:
    result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(
                    id="q1",
                    type="single_choice",
                    content="1 + 1 = ?",
                    correct_answer="A",
                    knowledge_point="加法",
                )
            ],
            answers=[AssessmentAnswer(question_id="q1", answer=" A ")],
        )
    )

    assert result.per_question_results[0].question_id == "q1"
    assert result.per_question_results[0].is_correct is True
    assert result.per_question_results[0].explanation == "答案正确。"
    assert result.per_question_results[0].related_knowledge_points == ["加法"]


def test_evaluate_assessment_marks_list_answer_correct_ignoring_order() -> None:
    result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(
                    id="q1",
                    type="multi_choice",
                    content="选择正确选项",
                    correct_answer=["A", "C"],
                    knowledge_point="集合",
                )
            ],
            answers=[AssessmentAnswer(question_id="q1", answer=["C", "A"])],
        )
    )

    assert result.per_question_results[0].is_correct is True


def test_evaluate_assessment_marks_missing_answer_incorrect() -> None:
    result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(
                    id="q1",
                    type="single_choice",
                    content="1 + 1 = ?",
                    correct_answer="A",
                    knowledge_point="加法",
                )
            ],
            answers=[],
        )
    )

    assert result.per_question_results[0].is_correct is False
    assert result.per_question_results[0].explanation == "未提交答案，标准答案为 A。"


def test_evaluate_assessment_builds_diagnosis_from_wrong_answers() -> None:
    result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(
                    id="q1",
                    type="single_choice",
                    content="1 + 1 = ?",
                    correct_answer="A",
                    knowledge_point="加法",
                ),
                AssessmentQuestion(
                    id="q2",
                    type="short_answer",
                    content="导数定义",
                    correct_answer="极限",
                    knowledge_point="导数",
                ),
            ],
            answers=[
                AssessmentAnswer(question_id="q1", answer="B"),
                AssessmentAnswer(question_id="q2", answer="极限"),
            ],
        )
    )

    assert result.diagnosis is not None
    assert result.diagnosis.summary == "共 2 题，答对 1 题，正确率 50.0%。"
    assert [(item.name, item.error_pattern) for item in result.diagnosis.weak_points] == [
        ("加法", "该知识点相关题目答错 1 次")
    ]
    assert result.diagnosis.suggestions == ["建议复习加法，并完成相关巩固练习。"]


def test_generate_questions_uses_requested_count_and_question_types() -> None:
    result = assessment.generate_questions_data(
        QuestionGenerateRequest(
            user_id="user-1",
            course_id="course-1",
            chapter="函数",
            knowledge_point="一次函数",
            question_types=["single_choice", "short_answer"],
            count=3,
            difficulty="medium",
        )
    )

    assert [question.type for question in result.questions] == [
        "single_choice",
        "short_answer",
        "single_choice",
    ]
    assert [question.knowledge_point for question in result.questions] == ["一次函数", "一次函数", "一次函数"]
    assert [question.chapter for question in result.questions] == ["函数", "函数", "函数"]
    assert [question.difficulty for question in result.questions] == ["medium", "medium", "medium"]
    assert len(result.questions[0].options) == 4
    assert result.questions[1].options == []


def test_generate_questions_uses_wrong_points_when_knowledge_point_missing() -> None:
    result = assessment.generate_questions_data(
        QuestionGenerateRequest(
            user_id="user-1",
            course_id="course-1",
            personalization_context={"wrong_points": ["导数", "极限"]},
            count=1,
        )
    )

    assert result.questions[0].knowledge_point == "导数"
    assert result.questions[0].type == "single_choice"


# ── generate_questions_with_llm tests ─────────────────────────────

import asyncio


class FakeChatProvider:
    def __init__(self, output: str | None = None, should_raise: bool = False) -> None:
        self.calls: list[list] = []
        self._output = output
        self._should_raise = should_raise

    async def complete(self, messages):
        self.calls.append(messages)
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        return self._output


def test_generate_questions_with_llm_parses_valid_json_array() -> None:
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProvider(
        output=(
            '[{"type":"single_choice","content":"一次函数 y=2x+1 的斜率是？",'
            '"options":[{"key":"A","text":"2"},{"key":"B","text":"1"}],'
            '"answer":"A","explanation":"一次函数 y=kx+b 中 k 是斜率。",'
            '"knowledge_point":"一次函数","difficulty":"easy"}]'
        )
    )
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1",
                knowledge_point="一次函数", count=1,
            ),
            provider,
        )
    )
    assert result is not None
    assert len(result) == 1
    q = result[0]
    assert q.type == "single_choice"
    assert q.content == "一次函数 y=2x+1 的斜率是？"
    assert q.answer == "A"
    assert q.options[0].text == "2"


def test_generate_questions_with_llm_strips_markdown_fences() -> None:
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProvider(
        output=(
            '```json\n'
            '[{"type":"short_answer","content":"什么是导数？",'
            '"answer":"函数在某点的变化率","explanation":"导数定义。",'
            '"knowledge_point":"导数","difficulty":"medium"}]\n'
            '```'
        )
    )
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1",
                knowledge_point="导数", count=1,
            ),
            provider,
        )
    )
    assert result is not None
    assert result[0].type == "short_answer"


def test_generate_questions_with_llm_returns_none_on_invalid_json() -> None:
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProvider(output="not valid json at all")
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1", count=1,
            ),
            provider,
        )
    )
    assert result is None


def test_generate_questions_with_llm_returns_none_when_provider_is_none() -> None:
    from agent_service.agents.assessment import generate_questions_with_llm

    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1", count=1,
            ),
            None,
        )
    )
    assert result is None


# ── Phase 0: structured_model spike tests ─────────────────────────


class FakeChatProviderV2:
    """支持 structured_model 参数的 FakeChatProvider。

    structured_output 若为 list 则自动包装为 {"questions": [...]}（适配 generate_questions）；
    若为 dict 则直接序列化（适配 evaluate 等接口）。
    """

    def __init__(
        self,
        output: str | None = None,
        should_raise: bool = False,
        structured_output: list[dict] | dict | None = None,
    ) -> None:
        self.calls: list[dict] = []
        self._output = output
        self._should_raise = should_raise
        self._structured_output = structured_output

    async def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        if self._structured_output is not None and "structured_model" in kwargs:
            import json as _json
            if isinstance(self._structured_output, list):
                return _json.dumps({"questions": self._structured_output})
            return _json.dumps(self._structured_output)
        return self._output


def test_structured_model_is_attempted_before_json_fallback() -> None:
    """structured_model 优先于 markdown fence JSON 解析被调用。"""
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProviderV2(
        structured_output=[
            {
                "type": "single_choice",
                "content": "测试题",
                "options": [{"key": "A", "text": "选项A"}],
                "answer": "A",
                "explanation": "解析",
                "knowledge_point": "测试知识点",
                "difficulty": "easy",
            }
        ],
    )
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1",
                knowledge_point="测试知识点", count=1,
            ),
            provider,
        )
    )
    assert result is not None
    assert len(result) == 1
    assert result[0].content == "测试题"
    # 验证 structured_model 被传入了
    assert len(provider.calls) == 1
    assert "structured_model" in provider.calls[0]["kwargs"]


def test_structured_model_failure_falls_back_to_json_parsing() -> None:
    """structured_model 路径失败时回落到现有 markdown fence JSON 解析。"""
    from agent_service.agents.assessment import generate_questions_with_llm

    # 不提供 structured_output → structured_model 路径返回空或无效
    # 但提供有效的 JSON 字符串作为原始输出 → fallback 应生效
    provider = FakeChatProviderV2(
        output=(
            '[{"type":"single_choice","content":"fallback 题",'
            '"options":[{"key":"A","text":"x"}],'
            '"answer":"A","explanation":"fallback 解析",'
            '"knowledge_point":"fallback","difficulty":"medium"}]'
        ),
    )
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1",
                knowledge_point="fallback", count=1,
            ),
            provider,
        )
    )
    assert result is not None
    assert len(result) == 1
    assert result[0].content == "fallback 题"


def test_structured_model_raises_falls_back_to_json() -> None:
    """structured_model 调用抛出异常时回落到 JSON 解析。"""
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProviderV2(should_raise=True)
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1",
                knowledge_point="x", count=1,
            ),
            provider,
        )
    )
    assert result is None


def test_generate_questions_with_llm_returns_none_when_llm_raises() -> None:
    from agent_service.agents.assessment import generate_questions_with_llm

    provider = FakeChatProvider(should_raise=True)
    result = asyncio.run(
        generate_questions_with_llm(
            QuestionGenerateRequest(
                user_id="u1", course_id="c1", count=1,
            ),
            provider,
        )
    )
    assert result is None


# ── evaluate_assessment_with_llm tests ─────────────────────────────


def test_evaluate_with_llm_enriches_explanation_and_diagnosis() -> None:
    import json as _json
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    llm_output = _json.dumps({
        "per_question_results": [
            {"question_id": "q1", "explanation": "正确答案是B，你选了A，混淆了加法和乘法的概念。", "related_knowledge_points": ["加法", "算术基础"]},
        ],
        "diagnosis": {
            "summary": "你在加法基础概念上存在混淆，建议从加法定义开始复习。",
            "weak_points": [{"name": "加法", "error_pattern": "混淆了加法和乘法的运算规则"}],
            "suggestions": ["完成加法章节前3道练习题", "区分加法与乘法的定义"],
        },
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is not None
    assert result.per_question_results[0].is_correct is False
    assert "混淆了加法" in (result.per_question_results[0].explanation or "")
    assert "算术基础" in result.per_question_results[0].related_knowledge_points
    assert result.diagnosis is not None
    assert "加法基础概念" in (result.diagnosis.summary or "")
    assert result.diagnosis.weak_points[0].error_pattern == "混淆了加法和乘法的运算规则"
    assert "完成加法章节前3道练习题" in result.diagnosis.suggestions


def test_evaluate_with_llm_preserves_rule_result_on_missing_question() -> None:
    import json as _json
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                AssessmentQuestion(id="q2", type="short_answer", content="什么是导数？", correct_answer="变化率", knowledge_point="导数"),
            ],
            answers=[
                AssessmentAnswer(question_id="q1", answer="A"),
                AssessmentAnswer(question_id="q2", answer="变化率"),
            ],
        )
    )

    llm_output = _json.dumps({
        "per_question_results": [
            {"question_id": "q1", "explanation": "你选了A，正确答案是B。", "related_knowledge_points": ["加法"]},
        ],
        "diagnosis": {
            "summary": "加法概念需要加强。",
            "weak_points": [],
            "suggestions": ["复习加法"],
        },
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                    AssessmentQuestion(id="q2", type="short_answer", content="什么是导数？", correct_answer="变化率", knowledge_point="导数"),
                ],
                answers=[
                    AssessmentAnswer(question_id="q1", answer="A"),
                    AssessmentAnswer(question_id="q2", answer="变化率"),
                ],
            ),
            rule_result,
            provider,
        )
    )

    assert result is not None
    assert result.per_question_results[0].is_correct is False
    assert "你选了A" in (result.per_question_results[0].explanation or "")
    assert result.per_question_results[1].is_correct is True
    assert result.per_question_results[1].explanation == "答案正确。"
    assert len(result.per_question_results) == 2


def test_evaluate_with_llm_returns_none_when_chat_provider_is_none() -> None:
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            None,
        )
    )

    assert result is None


def test_evaluate_with_llm_returns_none_on_invalid_json() -> None:
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    provider = FakeChatProvider(output="not valid json at all")
    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is None


def test_evaluate_with_llm_returns_none_on_exception(caplog) -> None:
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    with caplog.at_level("WARNING", logger="agent_service.agents.assessment"):
        result = asyncio.run(
            evaluate_assessment_with_llm(
                _build_request(
                    questions=[
                        AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                    ],
                    answers=[AssessmentAnswer(question_id="q1", answer="A")],
                ),
                rule_result,
                FakeChatProvider(should_raise=True),
            )
        )

    assert result is None
    assert "LLM evaluation enrichment failed" in caplog.text


def test_evaluate_with_llm_handles_markdown_wrapped_json() -> None:
    import json as _json
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    payload = _json.dumps({
        "per_question_results": [
            {"question_id": "q1", "explanation": "正确答案是B，不是A。", "related_knowledge_points": ["加法"]},
        ],
        "diagnosis": {
            "summary": "需加强加法练习。",
            "weak_points": [{"name": "加法", "error_pattern": "基础概念错误"}],
            "suggestions": ["多练习"],
        },
    })
    provider = FakeChatProvider(output=f"```json\n{payload}\n```")

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is not None
    assert result.per_question_results[0].is_correct is False
    assert "正确答案是B" in (result.per_question_results[0].explanation or "")


# ── Phase 1B: evaluate structured_model spike tests ────────────────


def test_evaluate_structured_model_is_attempted_before_json_fallback() -> None:
    """evaluate 路径优先使用 structured_model。"""
    import json as _json
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    structured_data = {
        "per_question_results": [
            {"question_id": "q1", "explanation": "structured 解析", "related_knowledge_points": ["加法"]},
        ],
        "diagnosis": {
            "summary": "structured 诊断",
            "weak_points": [{"name": "加法", "error_pattern": "基础概念混淆"}],
            "suggestions": ["做练习题"],
        },
    }
    provider = FakeChatProviderV2(structured_output=structured_data)

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is not None
    assert "structured 解析" in (result.per_question_results[0].explanation or "")
    assert "structured 诊断" in (result.diagnosis.summary or "")
    # 验证 structured_model 被传入
    assert len(provider.calls) == 1
    assert "structured_model" in provider.calls[0]["kwargs"]


def test_evaluate_structured_model_failure_falls_back_to_json() -> None:
    """evaluate structured_model 失败时回落到 markdown fence JSON 解析。"""
    import json as _json
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    json_output = _json.dumps({
        "per_question_results": [
            {"question_id": "q1", "explanation": "fallback 解析", "related_knowledge_points": ["加法"]},
        ],
        "diagnosis": {
            "summary": "fallback 诊断",
            "weak_points": [],
            "suggestions": ["复习"],
        },
    })
    # 不设 structured_output → structured_model 路径失败，回落 JSON
    provider = FakeChatProviderV2(output=json_output)

    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is not None
    assert "fallback 解析" in (result.per_question_results[0].explanation or "")


def test_evaluate_structured_model_exception_falls_back_to_none() -> None:
    """evaluate structured_model 抛异常时返回 None（无 JSON fallback 数据）。"""
    from agent_service.agents.assessment import evaluate_assessment_with_llm

    rule_result = evaluate_assessment_data(
        _build_request(
            questions=[
                AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
            ],
            answers=[AssessmentAnswer(question_id="q1", answer="A")],
        )
    )

    provider = FakeChatProviderV2(should_raise=True)
    result = asyncio.run(
        evaluate_assessment_with_llm(
            _build_request(
                questions=[
                    AssessmentQuestion(id="q1", type="single_choice", content="1+1=?", correct_answer="B", knowledge_point="加法"),
                ],
                answers=[AssessmentAnswer(question_id="q1", answer="A")],
            ),
            rule_result,
            provider,
        )
    )

    assert result is None


# ── generate-questions RAG tests ───────────────────────────────────


class TestQuestionRAG:
    def _request(self, **kwargs) -> QuestionGenerateRequest:
        defaults = dict(
            user_id="u1", course_id="data-structures",
            chapter="线性表", knowledge_point="顺序存储结构",
            count=2, question_types=["single_choice"],
        )
        defaults.update(kwargs)
        return QuestionGenerateRequest(**defaults)

    def test_rag_context_injected_into_llm_user_message(self) -> None:
        import json as _json
        from unittest.mock import patch
        from agent_service.agents.assessment import generate_questions_with_llm

        class FakeChatProvider:
            async def complete(self, messages):
                user_msg = messages[1].content
                assert "线性表是相同类型" in user_msg
                return _json.dumps([
                    {"type": "single_choice", "content": "线性表是什么？", "answer": "A",
                     "explanation": "线性表定义为...", "knowledge_point": "线性表", "difficulty": "easy",
                     "options": [{"key": "A", "text": "相同类型元素的有限序列"}, {"key": "B", "text": "不同类型"}]}
                ])

        context = "线性表是相同类型数据元素的有限序列。\n---\n顺序存储用一组连续地址存放元素。"
        provider = FakeChatProvider()

        result = asyncio.run(
            generate_questions_with_llm(
                self._request(), provider, course_knowledge_context=context
            )
        )
        assert result is not None
        assert len(result) == 1

    def test_generate_questions_with_llm_accepts_none_context(self) -> None:
        import json as _json
        from agent_service.agents.assessment import generate_questions_with_llm

        class FakeChatProvider:
            async def complete(self, messages):
                return _json.dumps([
                    {"type": "short_answer", "content": "什么是导数？", "answer": "变化率",
                     "explanation": "导数定义为...", "knowledge_point": "导数", "difficulty": "medium"}
                ])

        provider = FakeChatProvider()
        result = asyncio.run(
            generate_questions_with_llm(
                self._request(), provider, course_knowledge_context=None
            )
        )
        assert result is not None
        assert result[0].type == "short_answer"

    def test_retrieval_returns_empty_when_embedding_is_none(self) -> None:
        from agent_service.agents.assessment import build_question_generation_knowledge_context

        context = asyncio.run(
            build_question_generation_knowledge_context(self._request(), None)
        )
        assert context == ""

    def test_retrieval_returns_empty_on_qdrant_failure(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.assessment import build_question_generation_knowledge_context

        class FakeEmbedding:
            async def embed_texts(self, texts):
                return [[0.1, 0.2, 0.3]]

        class FailingVectorStore:
            async def search_course_knowledge(self, course_id, vector, limit=5):
                raise RuntimeError("Qdrant unavailable")

        with patch(
            "agent_service.memory.vector_store.QdrantVectorStore",
            return_value=FailingVectorStore(),
        ):
            context = asyncio.run(
                build_question_generation_knowledge_context(
                    self._request(), FakeEmbedding()
                )
            )
        assert context == ""

    def test_generate_questions_with_agent_falls_back_when_llm_returns_none(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.assessment import generate_questions_with_agent

        async def _fake_llm(*args, **kwargs):
            return None

        with patch("agent_service.agents.assessment.generate_questions_with_llm", _fake_llm):
            questions = asyncio.run(generate_questions_with_agent(self._request(), providers=None))

        assert len(questions) == 2
        assert "完成一道单选题" in questions[0].content

    def test_generate_questions_with_agent_returns_llm_result(self) -> None:
        from unittest.mock import patch
        from agent_service.agents.assessment import generate_questions_with_agent
        from agent_service.schemas.assessment import GeneratedQuestion

        async def _fake_llm(*args, **kwargs):
            return [GeneratedQuestion(type="single_choice", content="LLM题目", options=[], answer="A", knowledge_point="K", explanation="E")]

        with patch("agent_service.agents.assessment.generate_questions_with_llm", _fake_llm):
            questions = asyncio.run(generate_questions_with_agent(self._request(), providers=None))

        assert len(questions) == 1
        assert questions[0].content == "LLM题目"


def test_parse_question_payload_handles_array() -> None:
    from agent_service.agents.assessment import _parse_question_payload
    payload = '[{"content": "Q1"}]'
    result = _parse_question_payload(payload)
    assert len(result) == 1
    assert result[0]["content"] == "Q1"


def test_parse_question_payload_handles_object_with_questions() -> None:
    from agent_service.agents.assessment import _parse_question_payload
    payload = '{"questions": [{"content": "Q1"}]}'
    result = _parse_question_payload(payload)
    assert len(result) == 1
    assert result[0]["content"] == "Q1"


def test_parse_question_payload_handles_markdown() -> None:
    from agent_service.agents.assessment import _parse_question_payload
    payload = '```json\n{"questions": [{"content": "Q1"}]}\n```'
    result = _parse_question_payload(payload)
    assert len(result) == 1
    assert result[0]["content"] == "Q1"


def _build_request(
    questions: list[AssessmentQuestion],
    answers: list[AssessmentAnswer],
) -> AssessmentEvaluateRequest:
    return AssessmentEvaluateRequest(
        user_id="user-1",
        course_id="course-1",
        quiz_id="quiz-1",
        questions=questions,
        answers=answers,
    )
