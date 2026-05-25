"""assessment 接口的 LLM prompt 模板。"""

from agent_service.schemas.assessment import QuestionGenerateRequest


def build_question_generation_system_prompt() -> str:
    return (
        "你是 EDUagent 的出题助手。根据给定的知识点、题型、数量和难度，生成结构化的题目。"
        "输出必须是一个 JSON 数组，每个元素是一个题目对象，包含以下字段：\n"
        "- type: 题型（single_choice / multi_choice / code / short_answer）\n"
        "- content: 题目内容（字符串）\n"
        "- options: 选项列表（选择题时为 [{\"key\": \"A\", \"text\": \"...\"}, ...] 格式，非选择题为空数组 []）\n"
        "- answer: 标准答案（单选/简答为字符串，多选为字符串数组如 [\"A\", \"C\"]）\n"
        "- explanation: 解析说明\n"
        "- chapter: 章节名（字符串或 null）\n"
        "- knowledge_point: 关联知识点（字符串）\n"
        "- difficulty: 难度（easy / medium / hard 或 null）\n"
        "选择题的选项应有 4 个，包含 1 个正确选项和 3 个有迷惑性的干扰项。"
        "只输出 JSON 数组，不要加 markdown 代码块标记，不要加任何其他文字。"
    )


def build_question_generation_user_message(request: QuestionGenerateRequest) -> str:
    return (
        f"知识点：{request.knowledge_point or '综合'}\n"
        f"题型：{', '.join(request.question_types) if request.question_types else 'single_choice'}\n"
        f"数量：{request.count}\n"
        f"难度：{request.difficulty or 'medium'}\n"
        f"章节：{request.chapter or '不限'}\n"
        f"个性化上下文：{_format_context(request.personalization_context)}"
    )


def _format_context(context: dict | None) -> str:
    if not context:
        return "无"
    parts = []
    wrong_points = context.get("wrong_points")
    if isinstance(wrong_points, list):
        names = [
            item if isinstance(item, str) else item.get("name", "")
            for item in wrong_points
        ]
        parts.append(f"薄弱知识点：{', '.join(n for n in names if n)}")
    return "; ".join(parts) if parts else "无"
