import json
import re
from collections import defaultdict

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.evaluation import (
    build_evaluation_system_prompt,
    build_evaluation_user_message,
)
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


async def generate_evaluation_with_llm(
    request: EvaluationGenerateRequest,
    rule_result: EvaluationData,
    chat_provider,
) -> EvaluationData | None:
    """尝试用 LLM 增强规则版评估结果，输入请求、规则结果和 chat provider，输出增强后的 EvaluationData 或 None（降级）。

    以 rule_result 为基底，只允许 LLM 替换 summary_text。使用 model_copy 构造新对象，不原地修改 rule_result。
    """
    if chat_provider is None:
        return None
    try:
        messages = [
            ChatMessage(role="system", content=build_evaluation_system_prompt()),
            ChatMessage(role="user", content=build_evaluation_user_message(request, rule_result)),
        ]
        raw = await chat_provider.complete(messages)
        data = _parse_evaluation_json(raw)
        result = _enrich_evaluation_result(request, rule_result, data)
        logger.info("LLM enrichment succeeded: %s", "evaluation/generate")
        return result
    except Exception:
        logger.warning("LLM evaluation enrichment failed, falling back to rule-based", exc_info=True)
        return None


def _parse_evaluation_json(raw: str) -> dict:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _enrich_evaluation_result(
    request: EvaluationGenerateRequest,
    rule_result: EvaluationData,
    llm_data: dict,
) -> EvaluationData:
    enriched = rule_result.model_copy(deep=True)
    observed_chapters = _observed_chapters(request)
    observed_resources = set(request.resource_usage.by_type.keys())
    enriched.progress_table = _coerce_progress_table(
        llm_data.get("progress_table"), rule_result.progress_table, observed_chapters
    )
    enriched.mastery_table = _coerce_mastery_table(
        llm_data.get("mastery_table"), rule_result.mastery_table, observed_chapters
    )
    enriched.resource_usage_table = _coerce_resource_usage_table(
        llm_data.get("resource_usage_table"), rule_result.resource_usage_table, observed_resources
    )
    summary = llm_data.get("summary_text")
    if isinstance(summary, str) and summary.strip():
        enriched.summary_text = summary.strip()
    return enriched


def _observed_chapters(request: EvaluationGenerateRequest) -> set[str]:
    chapters: set[str] = set()
    for item in request.learning_progress.chapter_progress:
        chapters.add(item.chapter)
    for item in request.quiz_results:
        chapters.add(item.chapter)
    return chapters


_ALLOWED_EXTRA_COLUMNS: dict[str, set[str]] = {
    "progress_table": {"progress_insight"},
    "mastery_table": {"root_cause"},
    "resource_usage_table": {"effectiveness_hint"},
}


def _coerce_columns(
    llm_columns: list | None,
    fallback_columns: list[TableColumn],
    allowed_extra_keys: set[str],
) -> list[TableColumn]:
    if not isinstance(llm_columns, list) or not llm_columns:
        return fallback_columns
    base_keys = {col.key for col in fallback_columns}
    result: list[TableColumn] = []
    seen: set[str] = set()
    for item in llm_columns:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        if key in seen:
            continue
        if key not in base_keys and key not in allowed_extra_keys:
            continue
        seen.add(key)
        title = item.get("title", key)
        result.append(TableColumn(key=key, title=str(title) if isinstance(title, str) else key))
    # ensure all base keys present
    for col in fallback_columns:
        if col.key not in seen:
            result.append(TableColumn(key=col.key, title=col.title))
    return result


def _coerce_progress_table(
    raw: dict | None, fallback: TableData | None, observed_chapters: set[str]
) -> TableData | None:
    if not isinstance(raw, dict) or fallback is None:
        return fallback
    columns = _coerce_columns(
        raw.get("columns"), fallback.columns, _ALLOWED_EXTRA_COLUMNS["progress_table"]
    )
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list):
        return fallback
    rows = []
    for row in rows_raw:
        if not isinstance(row, dict):
            continue
        chapter = row.get("chapter")
        if not isinstance(chapter, str) or chapter not in observed_chapters:
            continue
        completion_rate = _coerce_score(row.get("completion_rate"), fallback_completion_rate(row, chapter, fallback))
        time_spent = _coerce_non_negative_int(row.get("time_spent"), fallback_time_spent(row, chapter, fallback))
        coerced: dict = {"chapter": chapter, "completion_rate": completion_rate, "time_spent": time_spent}
        # copy allowed extra columns
        progress_insight = row.get("progress_insight")
        if isinstance(progress_insight, str) and progress_insight.strip():
            coerced["progress_insight"] = progress_insight.strip()
        rows.append(coerced)
    if not rows:
        return fallback
    return TableData(columns=columns, rows=rows)


def _coerce_mastery_table(
    raw: dict | None, fallback: TableData | None, observed_chapters: set[str]
) -> TableData | None:
    if not isinstance(raw, dict) or fallback is None:
        return fallback
    columns = _coerce_columns(
        raw.get("columns"), fallback.columns, _ALLOWED_EXTRA_COLUMNS["mastery_table"]
    )
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list):
        return fallback
    rows = []
    for row in rows_raw:
        if not isinstance(row, dict):
            continue
        chapter = row.get("chapter")
        if not isinstance(chapter, str) or chapter not in observed_chapters:
            continue
        score = _coerce_score(row.get("average_score"), fallback_mastery_score(row, chapter, fallback))
        quiz_count = _coerce_non_negative_int(row.get("quiz_count"), fallback_quiz_count(row, chapter, fallback))
        mastery_level = _coerce_mastery_level(row.get("mastery_level"), score)
        coerced: dict = {"chapter": chapter, "average_score": score, "quiz_count": quiz_count, "mastery_level": mastery_level}
        root_cause = row.get("root_cause")
        if isinstance(root_cause, str) and root_cause.strip():
            coerced["root_cause"] = root_cause.strip()
        rows.append(coerced)
    if not rows:
        return fallback
    return TableData(columns=columns, rows=rows)


def _coerce_resource_usage_table(
    raw: dict | None, fallback: TableData | None, observed_resources: set[str]
) -> TableData | None:
    if not isinstance(raw, dict) or fallback is None:
        return fallback
    columns = _coerce_columns(
        raw.get("columns"), fallback.columns, _ALLOWED_EXTRA_COLUMNS["resource_usage_table"]
    )
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list):
        return fallback
    rows = []
    for row in rows_raw:
        if not isinstance(row, dict):
            continue
        resource_type = row.get("resource_type")
        if not isinstance(resource_type, str) or resource_type not in observed_resources:
            continue
        count = _coerce_non_negative_int(row.get("count"), fallback_resource_count(row, resource_type, fallback))
        coerced: dict = {"resource_type": resource_type, "count": count}
        hint = row.get("effectiveness_hint")
        if isinstance(hint, str) and hint.strip():
            coerced["effectiveness_hint"] = hint.strip()
        rows.append(coerced)
    if not rows:
        return fallback
    return TableData(columns=columns, rows=rows)


def _coerce_score(value, fallback: float) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(100.0, float(value)))
    return fallback


def _coerce_non_negative_int(value, fallback: int) -> int:
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    return fallback


def _coerce_mastery_level(value, score: float) -> str:
    if isinstance(value, str) and value.strip() in {"strong", "learning", "weak"}:
        return value.strip()
    return _mastery_level(score)


def _fallback_row(chapter: str, fallback: TableData) -> dict:
    if fallback is None:
        return {}
    for row in fallback.rows:
        if row.get("chapter") == chapter or row.get("resource_type") == chapter:
            return row
    return {}


def fallback_completion_rate(_row: dict, chapter: str, fallback: TableData) -> float:
    fb = _fallback_row(chapter, fallback)
    return float(fb.get("completion_rate", 0.0))


def fallback_time_spent(_row: dict, chapter: str, fallback: TableData) -> int:
    fb = _fallback_row(chapter, fallback)
    return int(fb.get("time_spent", 0))


def fallback_mastery_score(_row: dict, chapter: str, fallback: TableData) -> float:
    fb = _fallback_row(chapter, fallback)
    return float(fb.get("average_score", 0.0))


def fallback_quiz_count(_row: dict, chapter: str, fallback: TableData) -> int:
    fb = _fallback_row(chapter, fallback)
    return int(fb.get("quiz_count", 0))


def fallback_resource_count(_row: dict, resource_type: str, fallback: TableData) -> int:
    fb = _fallback_row(resource_type, fallback)
    return int(fb.get("count", 0))


logger = get_logger(__name__)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
