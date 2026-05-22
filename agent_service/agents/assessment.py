from collections import Counter

from agent_service.schemas.assessment import (
    AnswerValue,
    AssessmentEvaluateRequest,
    AssessmentResult,
    Diagnosis,
    GeneratedQuestion,
    PerQuestionResult,
    QuestionGenerateRequest,
    QuestionGenerateResult,
    QuestionOption,
    WeakPoint,
)


def evaluate_assessment_data(request: AssessmentEvaluateRequest) -> AssessmentResult:
    answers_by_question = {answer.question_id: answer.answer for answer in request.answers}
    per_question_results = []
    weak_point_counts: Counter[str] = Counter()

    for question in request.questions:
        submitted_answer = answers_by_question.get(question.id)
        is_correct = submitted_answer is not None and _answers_equal(submitted_answer, question.correct_answer)

        if not is_correct:
            weak_point_counts[question.knowledge_point] += 1

        per_question_results.append(
            PerQuestionResult(
                question_id=question.id,
                is_correct=is_correct,
                explanation=_build_explanation(submitted_answer, question.correct_answer, is_correct),
                related_knowledge_points=[question.knowledge_point],
            )
        )

    return AssessmentResult(
        per_question_results=per_question_results,
        diagnosis=_build_diagnosis(len(request.questions), per_question_results, weak_point_counts),
    )


def generate_questions_data(request: QuestionGenerateRequest) -> QuestionGenerateResult:
    question_types = request.question_types or ["single_choice"]
    knowledge_point = request.knowledge_point or _knowledge_point_from_context(request) or "综合知识点"

    questions = [
        _build_generated_question(
            question_type=question_types[index % len(question_types)],
            sequence=index + 1,
            chapter=request.chapter,
            knowledge_point=knowledge_point,
            difficulty=request.difficulty,
        )
        for index in range(request.count)
    ]
    return QuestionGenerateResult(questions=questions)


def _answers_equal(submitted_answer: AnswerValue, correct_answer: AnswerValue) -> bool:
    if isinstance(submitted_answer, list) or isinstance(correct_answer, list):
        return _normalize_list(submitted_answer) == _normalize_list(correct_answer)
    return submitted_answer.strip() == correct_answer.strip()


def _build_generated_question(
    question_type: str,
    sequence: int,
    chapter: str | None,
    knowledge_point: str,
    difficulty: str | None,
) -> GeneratedQuestion:
    if question_type == "multi_choice":
        answer: str | list[str] = ["A", "C"]
    else:
        answer = "A" if question_type == "single_choice" else f"{knowledge_point} 的核心概念"

    return GeneratedQuestion(
        type=question_type,
        content=f"第 {sequence} 题：请围绕{knowledge_point}完成一道{_question_type_label(question_type)}。",
        options=_build_options(question_type),
        answer=answer,
        explanation=f"本题用于检查对{knowledge_point}的基础理解。",
        chapter=chapter,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
    )


def _build_options(question_type: str) -> list[QuestionOption]:
    if question_type not in {"single_choice", "multi_choice"}:
        return []
    return [
        QuestionOption(key="A", text="正确表述"),
        QuestionOption(key="B", text="易混淆表述"),
        QuestionOption(key="C", text="相关补充表述"),
        QuestionOption(key="D", text="无关表述"),
    ]


def _question_type_label(question_type: str) -> str:
    labels = {
        "single_choice": "单选题",
        "multi_choice": "多选题",
        "code": "代码题",
        "short_answer": "简答题",
    }
    return labels.get(question_type, "练习题")


def _knowledge_point_from_context(request: QuestionGenerateRequest) -> str | None:
    context = request.personalization_context or {}
    wrong_points = context.get("wrong_points")
    if isinstance(wrong_points, list):
        for item in wrong_points:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                name = item.get("name") or item.get("knowledge_point")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return None


def _normalize_list(answer: AnswerValue) -> set[str]:
    if isinstance(answer, list):
        return {item.strip() for item in answer}
    return {answer.strip()}


def _build_explanation(submitted_answer: AnswerValue | None, correct_answer: AnswerValue, is_correct: bool) -> str:
    if is_correct:
        return "答案正确。"
    if submitted_answer is None:
        return f"未提交答案，标准答案为 {_format_answer(correct_answer)}。"
    return f"答案不正确，标准答案为 {_format_answer(correct_answer)}，当前答案为 {_format_answer(submitted_answer)}。"


def _format_answer(answer: AnswerValue) -> str:
    if isinstance(answer, list):
        return "、".join(sorted(item.strip() for item in answer))
    return answer.strip()


def _build_diagnosis(
    question_count: int,
    per_question_results: list[PerQuestionResult],
    weak_point_counts: Counter[str],
) -> Diagnosis:
    correct_count = sum(1 for item in per_question_results if item.is_correct)
    accuracy = round((correct_count / question_count) * 100, 1) if question_count else 0.0
    weak_points = [
        WeakPoint(name=name, error_pattern=f"该知识点相关题目答错 {count} 次")
        for name, count in sorted(weak_point_counts.items())
    ]

    return Diagnosis(
        summary=f"共 {question_count} 题，答对 {correct_count} 题，正确率 {accuracy:.1f}%。",
        weak_points=weak_points,
        suggestions=[f"建议复习{item.name}，并完成相关巩固练习。" for item in weak_points if item.name],
    )
