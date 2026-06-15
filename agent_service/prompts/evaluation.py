"""evaluation/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest


def build_evaluation_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习评估助手。根据学习进度、练习结果、资源使用和系统规则评估，"
        "生成 EvaluationData JSON 对象，其中只有 summary_text 允许由你改写。\n\n"
        "输出字段必须完整：progress_table、mastery_table、resource_usage_table、summary_text。\n"
        "progress_table、mastery_table、resource_usage_table 必须沿用系统规则结果，不要改写表格行、列或数值。\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节或资源类型\n"
        "- 不要改写 KG 节点状态、完成率、正确率、资源次数等事实字段\n"
        "- summary_text 必须基于输入中的 KG、个人资料、学习画像和学习行为\n"
        "- summary_text 使用模板：学习范围；当前掌握；学习行为；下一步建议\n"
        "- 证据不足时明确说明证据不足，不要编造学习记录\n"
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
    parts.append("注意：表格必须沿用系统规则结果；你只负责按模板改写 summary_text。")
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
    parts.append("")
    parts.append("summary_text 模板：")
    parts.append("  学习范围：结合 KG/章节说明已经覆盖的内容。")
    parts.append("  当前掌握：说明已掌握、薄弱、待练习或证据不足的重点。")
    parts.append("  学习行为：结合最近活跃、学习时长、资源偏好和练习参与。")
    parts.append("  下一步建议：给出 2-3 条与个人资料和引导级别匹配的行动建议。")

    return "\n".join(parts)
