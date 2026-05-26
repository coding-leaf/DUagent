"""evaluation/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest


def build_evaluation_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习评估助手。根据用户的学习进度、练习结果和资源使用数据，"
        "生成一份综合学习效果总结（summary_text）。\n\n"
        "学习评估的表格数据（progress_table、mastery_table、resource_usage_table）"
        "已由系统计算确定，你不需要也不能修改这些表格。只需输出 summary_text 文本。\n\n"
        "输出必须是一个 JSON 对象：{\"summary_text\": \"...\"}\n\n"
        "summary_text 要求：\n"
        "- 概述整体学习进度和完成情况\n"
        "- 指出掌握较好和薄弱的章节，引用具体数据\n"
        "- 分析资源使用偏好（如视频 vs 文档 vs 代码）\n"
        "- 给出学习建议和下一步方向\n"
        "- 风格简洁、数据驱动、有建设性\n"
        "- 3-5 句话\n\n"
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
    parts.append("练习结果：")
    for item in request.quiz_results:
        parts.append(f"  - {item.chapter}：正确率 {item.score}%，时间 {item.created_at.isoformat()}")
    parts.append("")
    parts.append("资源使用：")
    for resource_type, count in sorted(request.resource_usage.by_type.items()):
        parts.append(f"  - {resource_type}：{count} 次")
    parts.append("")
    parts.append(f"当前规则版总结：{rule_result.summary_text or '无'}")

    return "\n".join(parts)
