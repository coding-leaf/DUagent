from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from agent_service_v2.schemas.evaluation import (
    ChapterProgressItem,
    EvaluationData,
    EvaluationGenerateRequest,
    LearningInsight,
    TableColumn,
    TableData,
)

logger = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def generate_evaluation_data(request: EvaluationGenerateRequest) -> EvaluationData:
    """基于底层统计规则生成 Baseline 评估数据。"""
    return EvaluationData(
        progress_table=_build_progress_table(request),
        mastery_table=_build_mastery_table(request),
        resource_usage_table=_build_resource_usage_table(request),
        summary_text=_build_summary_text(request),
        insight=LearningInsight(facts_version=request.facts_version),
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
    # 按 knowledge_point 聚合，fallback 到 chapter
    scores_by_kp: dict[str, list[float]] = defaultdict(list)
    kp_to_chapter: dict[str, str] = {}
    personalized_by_kp: dict[str, int] = {}

    for item in request.quiz_results:
        key = item.knowledge_point or item.chapter
        scores_by_kp[key].append(item.score)
        kp_to_chapter[key] = item.chapter
        if item.personalized_count:
            personalized_by_kp[key] = personalized_by_kp.get(key, 0) + item.personalized_count

    rows = []
    for kp in sorted(scores_by_kp):
        scores = scores_by_kp[kp]
        average_score = round(sum(scores) / len(scores), 1)
        rows.append({
            "knowledge_point": kp,
            "chapter": kp_to_chapter.get(kp, ""),
            "average_score": average_score,
            "quiz_count": len(scores),
            "personalized_count": personalized_by_kp.get(kp, 0),
            "mastery_level": _mastery_level(average_score),
        })

    return TableData(
        columns=[
            TableColumn(key="knowledge_point", title="知识点"),
            TableColumn(key="chapter", title="章节"),
            TableColumn(key="average_score", title="平均正确率"),
            TableColumn(key="quiz_count", title="练习次数"),
            TableColumn(key="personalized_count", title="强化练习次数"),
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
    weak_kps = [
        (item.knowledge_point or item.chapter)
        for item in request.quiz_results if item.score < 60
    ]

    weak_text = "暂无明显薄弱知识点" if not weak_kps else f"薄弱知识点：{'、'.join(sorted(set(weak_kps)))}"
    personalized_total = sum(item.personalized_count or 0 for item in request.quiz_results)
    personalized_text = f"，已进行 {personalized_total} 次个性化强化练习" if personalized_total > 0 else ""
    return (
        f"已学习 {len(progress_items)} 个章节，"
        f"平均完成率 {average_completion:.1f}%，"
        f"平均练习正确率 {average_quiz_score:.1f}%"
        f"{personalized_text}。"
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


def build_evaluation_prompt(request: EvaluationGenerateRequest, rule_result: EvaluationData) -> str:
    system_prompt = (
        "你是 EDUagent 的学习评估助手。根据学习进度、练习结果、资源使用和系统规则评估，"
        "生成学习解释 JSON，其中只能包含 summary_text 和 insight。\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节或资源类型\n"
        "- 不要改写 KG 节点状态、完成率、正确率、资源次数等事实字段\n"
        "- summary_text 必须基于输入中的 KG、个人资料、学习画像和学习行为\n"
        "- summary_text 使用模板：学习范围；当前掌握；学习行为；下一步建议\n"
        "- 证据不足时明确说明证据不足，不要编造学习记录\n"
        "- strengths 和 weak_points 必须给出 knowledge_point 与 evidence\n"
        "- weak_points 可使用 high、medium、low priority\n"
        "- 只输出包含 summary_text 和 insight 的 JSON 对象"
    )

    parts: list[str] = [system_prompt, ""]
    parts.append(f"用户ID：{request.user_id}")
    parts.append(f"课程ID：{request.course_id}")
    parts.append("")
    parts.append("评估生成要求：只解释系统规则事实，不得重算或改写表格。")
    parts.append("")
    if request.student_profile:
        parts.append("个人资料：")
        for key, value in request.student_profile.items():
            parts.append(f"  - {key}: {value}")
        parts.append("")
    if request.profile_context:
        parts.append("课程画像上下文：")
        parts.append(f"  {request.profile_context}")
        parts.append("")
    if request.kg_context:
        parts.append("知识图谱与节点进度：")
        parts.append(f"  {request.kg_context}")
        parts.append("")
    if request.learning_activity:
        parts.append("学习行为统计：")
        parts.append(f"  {request.learning_activity}")
        parts.append("")
    parts.append("学习进度：")
    for item in request.learning_progress.chapter_progress:
        parts.append(f"  - {item.chapter}：完成率 {item.completion_rate}%，学习 {item.time_spent} 分钟")
    parts.append("")
    parts.append("练习结果（按知识点聚合，含个性化强化情况）：")
    for item in request.quiz_results:
        kp_label = item.knowledge_point or item.chapter
        trend_text = f"，近期趋势 {item.recent_trend:.1f}%" if item.recent_trend is not None else ""
        personalized_text = f"，其中个性化强化 {item.personalized_count} 次" if item.personalized_count else ""
        total_text = f"，共答 {item.total_answers} 题" if item.total_answers is not None else ""
        parts.append(
            f"  - 「{kp_label}」：正确率 {item.score:.1f}%{total_text}{personalized_text}{trend_text}"
        )
    if len(request.quiz_results) >= 2:
        scores = [i.score for i in request.quiz_results]
        parts.append(f"  （知识点覆盖 {len(request.quiz_results)} 个，平均正确率 {sum(scores)/len(scores):.1f}%）")
    parts.append("")
    parts.append("掌握度表格摘要：")
    if rule_result.mastery_table:
        for row in rule_result.mastery_table.rows:
            parts.append(f"  - {row.get('chapter', '?')}：{row.get('mastery_level', '?')}（均分 {row.get('average_score', '?')}）")
    parts.append("")
    parts.append("资源使用：")
    for resource_type, count in sorted(request.resource_usage.by_type.items()):
        parts.append(f"  - {resource_type}：{count} 次")
    parts.append("")
    parts.append(f"当前规则版总结：{rule_result.summary_text or '无'}")
    parts.append("")
    parts.append("summary_text 模板：")
    parts.append("  学习范围：结合 KG/章节说明已经覆盖的内容。")
    parts.append("  当前掌握：说明已掌握、薄弱、待练习或证据不足的重点。")
    parts.append("  学习行为：结合最近活跃、学习时长、资源偏好和练习参与。")
    parts.append("  下一步建议：给出 2-3 条与个人资料和引导级别匹配的建议。")
    parts.append("")
    parts.append(
        "请输出 JSON：{\"summary_text\": \"...\", \"insight\": "
        "{\"strengths\": [], \"weak_points\": [], "
        "\"learning_preferences\": [], \"next_actions\": []}}，不要 Markdown 包装。"
    )

    return "\n".join(parts)


async def generate_evaluation_with_llm(
    request: EvaluationGenerateRequest,
    rule_result: EvaluationData,
    model: Any,
) -> EvaluationData | None:
    """拉起大模型异步增强 Evaluation 综合总结（summary_text）。"""
    if model is None:
        return None

    prompt = build_evaluation_prompt(request, rule_result)

    try:
        # AgentScope 2.x: OpenAIChatModel 实例可以直接作为 Callable 调用
        response = await model(prompt)
        raw_text = response.text.strip()

        data = _parse_evaluation_json(raw_text)
        result = _enrich_evaluation_result(request, rule_result, data)
        logger.info("LLM evaluation enrichment succeeded: %s", "evaluation/generate")
        return result
    except Exception as exc:
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
    summary = llm_data.get("summary_text")
    if isinstance(summary, str) and summary.strip():
        enriched.summary_text = summary.strip()
    insight = llm_data.get("insight")
    if isinstance(insight, dict):
        enriched.insight = LearningInsight.model_validate(
            {**insight, "facts_version": request.facts_version}
        )
    return enriched


async def generate_quiz_diagnosis_with_llm(
    request: QuizDiagnoseRequest,
    model: Any,
) -> dict[str, Any]:
    """Generates a detailed pedagogical evaluation and remedial recommendations based on submitted C quiz answers."""
    from agent_service_v2.schemas.evaluation import QuizDiagnoseRequest

    questions_str = json.dumps(request.questions, ensure_ascii=False, indent=2)
    answers_str = json.dumps(request.answers, ensure_ascii=False, indent=2)

    prompt = f"""You are an Expert C Programming Pedagogical Diagnostic Agent.
Please evaluate and diagnose this student's C programming quiz submission:

=== QUIZ QUESTIONS ===
{questions_str}

=== STUDENT SUBMITTED ANSWERS ===
{answers_str}

Analyze their performance. Identify:
1. Conceptual blindspots and patterns in their errors.
2. Code-level issues (compilation, logic, syntax) if there are coding exercises.
3. Concrete learning suggestions tailored specifically to their performance.

Your output MUST be a strict JSON object with EXACTLY this structure:
{{
  "diagnosis": {{
    "summary": "A concise, encouraging summary of how the student did, overall score evaluation, and general sentiment.",
    "score_analysis": "A detailed breakdown of their score, performance by question types, and conceptual alignment.",
    "wrong_points_analysis": "An in-depth pedagogical analysis of their incorrect answers, diagnosing precisely why they made those mistakes and what foundational concepts they missed.",
    "suggestions": [
      "Practical recommendation 1 (e.g., read Chapter X, section Y; review topic Z)",
      "Practical recommendation 2...",
      "Practical recommendation 3..."
    ]
  }}
}}
"""
    if model is None:
        return {
            "diagnosis": {
                "summary": "本次练习已完成。建议仔细温习答错题目的解析以巩固基础知识。",
                "score_analysis": f"共完成 {len(request.questions)} 道习题。",
                "wrong_points_analysis": "已记录您的错题。您可以在个性化练习中再次强化。",
                "suggestions": [
                    "温习本章节大纲中的关键知识点。",
                    "利用智能工作台开展个性化交互强化练习。"
                ]
            }
        }

    try:
        response = await model(prompt)
        text = response.text.strip()

        match = _MARKDOWN_FENCE_PATTERN.search(text)
        if match:
            text = match.group(1).strip()

        data = json.loads(text)
        if not isinstance(data, dict) or "diagnosis" not in data:
            raise ValueError("Diagnosis field missing from LLM response")

        return data
    except Exception as exc:
        logger.error("Failed to generate quiz diagnosis with LLM: %s", exc)
        # Safe fallback baseline
        return {
            "diagnosis": {
                "summary": "本次练习已完成。建议仔细温习答错题目的解析以巩固基础知识。",
                "score_analysis": f"共完成 {len(request.questions)} 道习题。",
                "wrong_points_analysis": "已记录您的错题。您可以在个性化练习中再次强化。",
                "suggestions": [
                    "温习本章节大纲中的关键知识点。",
                    "利用智能工作台开展个性化交互强化练习。"
                ]
            }
        }
