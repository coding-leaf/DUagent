from collections import defaultdict

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest, TableColumn, TableData


def generate_evaluation_data(request: EvaluationGenerateRequest) -> EvaluationData:
    return EvaluationData(
        progress_table=_build_progress_table(request),
        mastery_table=_build_mastery_table(request),
        resource_usage_table=_build_resource_usage_table(request),
        summary_text=_build_summary_text(request),
    )


def _build_progress_table(request: EvaluationGenerateRequest) -> TableData:
    return TableData(
        columns=[
            TableColumn(key="chapter", title="章节"),
            TableColumn(key="completion_rate", title="完成率"),
            TableColumn(key="time_spent", title="学习时长（分钟）"),
        ],
        rows=[
            {
                "chapter": item.chapter,
                "completion_rate": item.completion_rate,
                "time_spent": item.time_spent,
            }
            for item in request.learning_progress.chapter_progress
        ],
    )


def _build_mastery_table(request: EvaluationGenerateRequest) -> TableData:
    scores_by_chapter: dict[str, list[float]] = defaultdict(list)
    for item in request.quiz_results:
        scores_by_chapter[item.chapter].append(item.score)

    rows = []
    for chapter in sorted(scores_by_chapter):
        scores = scores_by_chapter[chapter]
        average_score = round(sum(scores) / len(scores), 1)
        rows.append(
            {
                "chapter": chapter,
                "average_score": average_score,
                "quiz_count": len(scores),
                "mastery_level": _mastery_level(average_score),
            }
        )

    return TableData(
        columns=[
            TableColumn(key="chapter", title="章节"),
            TableColumn(key="average_score", title="平均正确率"),
            TableColumn(key="quiz_count", title="练习次数"),
            TableColumn(key="mastery_level", title="掌握水平"),
        ],
        rows=rows,
    )


def _build_resource_usage_table(request: EvaluationGenerateRequest) -> TableData:
    return TableData(
        columns=[
            TableColumn(key="resource_type", title="资源类型"),
            TableColumn(key="count", title="使用次数"),
        ],
        rows=[
            {"resource_type": resource_type, "count": count}
            for resource_type, count in sorted(request.resource_usage.by_type.items())
        ],
    )


def _build_summary_text(request: EvaluationGenerateRequest) -> str:
    progress_items = request.learning_progress.chapter_progress
    average_completion = _average([item.completion_rate for item in progress_items])
    average_quiz_score = _average([item.score for item in request.quiz_results])
    weak_chapters = [item.chapter for item in request.quiz_results if item.score < 60]

    weak_text = "暂无明显薄弱章节" if not weak_chapters else f"薄弱章节：{'、'.join(sorted(set(weak_chapters)))}"
    return (
        f"已学习 {len(progress_items)} 个章节，"
        f"平均完成率 {average_completion:.1f}%，"
        f"平均练习正确率 {average_quiz_score:.1f}%。"
        f"{weak_text}。"
    )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def _mastery_level(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 60:
        return "learning"
    return "weak"
