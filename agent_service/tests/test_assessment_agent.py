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
