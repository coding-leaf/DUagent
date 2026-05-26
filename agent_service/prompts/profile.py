"""profile/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest


def build_profile_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习画像分析助手。你需要根据用户练习历史、资源使用、近期学习强度和系统规则画像，"
        "生成完整 ProfileData JSON 对象。\n\n"
        "输出字段必须完整：\n"
        "- modal_preference: {video_animation, chart_logic, text_analysis, code_practice, formula_derivation}，每项 0-100\n"
        "- guidance_level_suggestion: {recommended, reason}，recommended 只能是 L1/L2/L3\n"
        "- knowledge_coordinates: [{name, status}]，status 只能是 mastered/learning\n"
        "- cognitive_blindspots: [{name, error_count, severity}]，severity 只能是 high/medium/low\n"
        "- drive_intent: {type, intensity}，type 只能是 exam_sprint/daily_homework/casual，intensity 为 0-100\n"
        "- discipline_badge: {subject, level, streak_days}\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节、知识点或课程 ID\n"
        "- 结构字段可以基于证据修正，但必须与输入数据一致\n"
        "- 分数、强度和偏好值必须在 0-100 范围内\n"
        "- reason 要引用具体章节、正确率、资源使用或学习频率，避免泛泛而谈\n"
        "- 如果证据不足，沿用系统规则画像中的对应字段\n"
        "只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字。"
    )


def build_profile_user_message(
    request: ProfileGenerateRequest,
    rule_result: ProfileData,
) -> str:
    parts: list[str] = []
    parts.append(f"用户ID：{request.user_id}")
    parts.append(f"课程ID：{request.course_id}")
    parts.append("")
    parts.append("画像生成要求：请输出完整 ProfileData JSON。若某字段证据不足，请沿用系统已计算画像。")
    parts.append("")
    parts.append("练习历史：")
    for item in request.quiz_history:
        parts.append(
            f"  - 章节：{item.chapter or '未知'}，正确率：{item.score}%，"
            f"时间：{item.created_at.isoformat()}"
        )
    if request.quiz_history:
        scores = [item.score for item in request.quiz_history]
        first = request.quiz_history[0]
        last = request.quiz_history[-1]
        weak = [item for item in request.quiz_history if item.score < 70]
        parts.append(
            f"练习摘要：平均正确率 {sum(scores) / len(scores):.1f}%，"
            f"首次 {first.chapter or '未知'} {first.score}%，"
            f"最近 {last.chapter or '未知'} {last.score}%，"
            f"低于70%的记录 {len(weak)} 条"
        )
    else:
        parts.append("练习摘要：无练习历史")
    parts.append("")
    if request.resource_usage_stats:
        stats = request.resource_usage_stats
        parts.append(f"资源使用：视频 {stats.video_count or 0} 次，文档 {stats.document_count or 0} 次，"
                     f"代码 {stats.code_count or 0} 次，做题 {stats.quiz_count or 0} 次")
    else:
        parts.append("资源使用：无数据")
    parts.append("")
    if request.drive_intent_data:
        di = request.drive_intent_data
        parts.append(f"近7天学习次数：{di.recent_7d_sessions or 0}，学习时长：{di.recent_7d_duration or 0} 分钟")
    else:
        parts.append("近7天学习数据：无")
    parts.append("")
    parts.append("系统已计算的画像：")
    if rule_result.guidance_level_suggestion:
        parts.append(f"  推荐引导级别：{rule_result.guidance_level_suggestion.recommended or '未知'}")
        parts.append(f"  当前理由：{rule_result.guidance_level_suggestion.reason or '无'}")
    if rule_result.knowledge_coordinates:
        coords = ", ".join(f"{c.name}({c.status})" for c in rule_result.knowledge_coordinates)
        parts.append(f"  知识坐标：{coords}")
    if rule_result.cognitive_blindspots:
        blinds = ", ".join(f"{b.name}(严重度:{b.severity}, 错误:{b.error_count}次)"
                          for b in rule_result.cognitive_blindspots)
        parts.append(f"  认知盲区：{blinds}")
    if rule_result.drive_intent:
        parts.append(f"  驱动意图：{rule_result.drive_intent.type}，强度：{rule_result.drive_intent.intensity or 0}")
    if rule_result.discipline_badge:
        parts.append(f"  学科徽章：{rule_result.discipline_badge.subject or '未知'}，"
                     f"等级：{rule_result.discipline_badge.level or '未知'}，"
                     f"连续天数：{rule_result.discipline_badge.streak_days or 0}")

    return "\n".join(parts)
