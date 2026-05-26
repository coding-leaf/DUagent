"""profile/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest


def build_profile_system_prompt() -> str:
    return (
        "你是 EDUagent 的画像分析助手。根据用户的练习历史、资源使用统计、学习频率和系统已计算的画像数据，"
        "为引导级别建议生成个性化的理由（reason）文本。\n\n"
        "画像的结构字段（recommended 引导级别、modal_preference 模态偏好、knowledge_coordinates 知识坐标、"
        "cognitive_blindspots 认知盲区、drive_intent 驱动意图、discipline_badge 学科徽章）已由系统计算确定，"
        "你不需要也不能修改这些字段。\n\n"
        "输出必须是一个 JSON 对象，包含完整的 ProfileData 结构，但除 guidance_level_suggestion.reason 外的"
        "所有字段应原样复制输入值。只需重写 reason 文本。\n\n"
        "reason 要求：\n"
        "- 基于用户的实际练习数据（正确率、薄弱章节、错误分布）给出具体理由\n"
        "- 避免泛泛而谈，要引用具体章节名和分数\n"
        "- 风格亲切、有建设性\n"
        "- 1-3 句话\n\n"
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
    parts.append("练习历史：")
    for item in request.quiz_history:
        parts.append(
            f"  - 章节：{item.chapter or '未知'}，正确率：{item.score}%，"
            f"时间：{item.created_at.isoformat()}"
        )
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
