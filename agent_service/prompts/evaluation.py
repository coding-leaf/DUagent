"""evaluation/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest


def build_evaluation_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习评估助手。根据学习进度、练习结果、资源使用和系统规则评估，"
        "生成完整 EvaluationData JSON 对象。\n\n"
        "输出字段必须完整：progress_table、mastery_table、resource_usage_table、summary_text。\n"
        "每个表格必须包含 columns 和 rows。\n\n"
        "progress_table 固定基础列：chapter、completion_rate、time_spent；可增加 progress_insight。\n"
        "mastery_table 固定基础列：chapter、average_score、quiz_count、mastery_level；可增加 root_cause。\n"
        "resource_usage_table 固定基础列：resource_type、count；可增加 effectiveness_hint。\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节或资源类型\n"
        "- completion_rate、average_score 必须在 0-100\n"
        "- time_spent、quiz_count、count 必须为非负整数\n"
        "- mastery_level 只能是 strong/learning/weak\n"
        "- 如果证据不足，沿用系统规则表格对应行\n"
        "- summary_text 必须包含整体概况、章节对比、趋势、资源关联、可操作建议\n"
        "- 只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字"
    )


def build_evaluation_user_message(
    request: EvaluationGenerateRequest,
    rule_result: EvaluationData,
) -> str:
    parts: list[str] = []
    parts.append(f"用户ID：{request.user_id}")
    parts.append(f"课程ID：{request.course_id}")
    parts.append("")
    parts.append("评估生成要求：请输出完整 EvaluationData JSON。若某表格字段证据不足，请沿用系统规则表格。")
    parts.append("")
    parts.append("学习进度：")
    for item in request.learning_progress.chapter_progress:
        parts.append(f"  - {item.chapter}：完成率 {item.completion_rate}%，学习 {item.time_spent} 分钟")
    parts.append("")
    parts.append("练习结果（按时间排序，可用于趋势分析）：")
    sorted_quizzes = sorted(request.quiz_results, key=lambda x: x.created_at)
    for item in sorted_quizzes:
        parts.append(f"  - {item.chapter}：正确率 {item.score}%，时间 {item.created_at.isoformat()}")
    if len(sorted_quizzes) >= 2:
        first = sorted_quizzes[0]
        last = sorted_quizzes[-1]
        parts.append(f"  （首次练习：{first.chapter} {first.score}%，末次练习：{last.chapter} {last.score}%）")
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

    return "\n".join(parts)
