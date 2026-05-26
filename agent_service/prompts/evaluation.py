"""evaluation/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest


def build_evaluation_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习评估助手。根据用户的学习进度、练习结果和资源使用数据，"
        "生成一份综合学习效果总结（summary_text）。\n\n"
        "学习评估的表格数据（progress_table、mastery_table、resource_usage_table）"
        "已由系统计算确定，你不需要也不能修改这些表格。只需输出 summary_text 文本。\n\n"
        "输出必须是一个 JSON 对象：{\"summary_text\": \"...\"}\n\n"
        "summary_text 要求（4-8 句话，数据驱动）：\n"
        "1. 整体概况：总章节数、平均完成率、平均正确率，一句话概括学习状态\n"
        "2. 章节对比：掌握最好和最薄弱的章节，引用具体正确率，解释差距可能的根因\n"
        "   （如\"导数章节正确率仅55%，可能是因为极限概念未牢固，导致求导运算困难\"）\n"
        "3. 趋势分析：如果 quiz_results 包含不同时间点的练习，分析正确率变化趋势\n"
        "   （上升/下降/波动），推断学习效果是否在改善\n"
        "4. 资源效果关联：分析资源使用偏好（视频/文档/代码）与学习效果的关联\n"
        "   （如\"文档使用3次但正确率偏低，建议增加视频讲解辅助理解\"）\n"
        "5. 可操作建议：给出 2-3 条具体的下一步行动，必须指定章节名和资源类型\n"
        "   （如\"优先完成导数章节剩余60%内容，配合代码练习巩固求导公式\"）\n"
        "不要泛泛而谈（如\"继续努力\"），每条建议都要引用数据、指定章节。\n\n"
        "只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字。"
    )


def build_evaluation_user_message(
    request: EvaluationGenerateRequest,
    rule_result: EvaluationData,
) -> str:
    parts: list[str] = []
    parts.append(f"用户ID：{request.user_id}")
    parts.append(f"课程ID：{request.course_id}")
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
