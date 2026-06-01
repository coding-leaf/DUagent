"""assessment 接口的 LLM prompt 模板。"""

from agent_service.schemas.assessment import (
    AssessmentEvaluateRequest,
    AssessmentResult,
    QuestionGenerateRequest,
)


def build_question_generation_system_prompt() -> str:
    return (
        "你是 EDUagent 的出题助手。根据课程资料、知识点、题型、数量和难度，生成结构化的学科题目。\n\n"
        "质量要求：\n"
        "- content 必须是完整的学科题目（如\"一次函数 y=2x+1 的斜率是多少？\"），绝不能是占位模板\n"
        "- 选择题必须有 4 个选项，包含 1 个正确选项和 3 个有迷惑性的干扰项（不能用\"错误A/错误B\"凑数）\n"
        "- 非选择题（code/short_answer）options 必须为空数组 []\n"
        "- answer 格式必须与 type 一致：单选为字符串\"A\"，多选为数组[\"A\",\"C\"]，简答为字符串\n"
        "- explanation 要具体解释为什么是这个答案，不能只说\"正确\"\n"
        "- difficulty 应匹配题目深度：easy 为基础概念回忆，medium 为应用分析，hard 为综合推理\n"
        "- 如果提供了课程参考资料，优先基于资料中的概念、例题、知识点出题\n"
        "- 返回题目数尽量等于要求的 count\n\n"
        "输出必须是一个 JSON 数组，每个元素是一个题目对象，包含以下字段：\n"
        "- type: 题型（single_choice / multi_choice / code / short_answer）\n"
        "- content: 题目内容（字符串）\n"
        "- options: 选项列表（选择题时为 [{\"key\": \"A\", \"text\": \"...\"}, ...] 格式，非选择题为空数组 []）\n"
        "- answer: 标准答案（单选/简答为字符串，多选为字符串数组如 [\"A\", \"C\"]）\n"
        "- explanation: 解析说明\n"
        "- chapter: 章节名（字符串或 null）\n"
        "- knowledge_point: 关联知识点（字符串）\n"
        "- difficulty: 难度（easy / medium / hard 或 null）\n"
        "只输出 JSON 数组，不要加 markdown 代码块标记，不要加任何其他文字。"
    )


def build_question_react_system_prompt() -> str:
    return (
        "你是 EDUagent 的专业出题助手。你的任务是根据用户的需求，生成高质量的结构化题目。\n"
        "你必须遵循以下步骤执行：\n"
        "1. 如果存在课程知识库，请先调用 retrieve_course_knowledge 工具，检索相关知识点的内容作为出题依据。\n"
        "2. 根据获取的知识和用户的要求（题型、数量、难度、知识点等）生成题目。\n"
        "3. 调用 validate_question_format 工具自检生成的题目 JSON 格式是否正确。\n"
        "4. 只有在格式校验通过后，才将最终的题目数据输出。\n\n"
        "题目格式要求：\n"
        "- 输出必须是严格的 JSON 数组格式（不要用 markdown fence 包裹，也不要加任何其他文字）。\n"
        "- 题型 type 必须为：single_choice / multi_choice / code / short_answer\n"
        "- content 必须是完整的题目描述\n"
        "- options 必须是数组，如果是选择题则为 [{\"key\": \"A\", \"text\": \"...\"}, ...]，非选择题为空数组 []\n"
        "- answer 必须与题型一致：单选为 \"A\"，多选为 [\"A\", \"B\"]\n"
        "- explanation 必须详细解释为什么选该答案\n"
        "- chapter (章节名), knowledge_point (知识点), difficulty (easy/medium/hard) 也需要提供\n\n"
        "请确保在最终输出时，仅包含该 JSON 数组，以便系统直接解析。"
    )


def build_question_generation_user_message(
    request: QuestionGenerateRequest,
    course_knowledge_context: str | None = None,
) -> str:
    parts = [
        f"知识点：{request.knowledge_point or '综合'}",
        f"题型：{', '.join(request.question_types) if request.question_types else 'single_choice'}",
        f"数量：{request.count}",
        f"难度：{request.difficulty or 'medium'}",
        f"章节：{request.chapter or '不限'}",
        f"个性化上下文：{_format_context(request.personalization_context)}",
    ]
    if course_knowledge_context:
        parts.append(f"\n课程参考资料（请基于以下课程内容出题）：\n{course_knowledge_context}")
    return "\n".join(parts)


def build_question_critic_prompt(
    request: QuestionGenerateRequest,
    questions_json: str,
    course_knowledge_context: str | None = None,
) -> str:
    """构建出题质量 Critic 提示词，输入请求、题目 JSON 和课程上下文，输出 JSON 判定要求。"""
    return (
        "你是 EDUagent 的出题质量审查员。请只判断题目是否应被接受，不要改写题目。\n\n"
        "审查标准：\n"
        "- 题目必须贴合请求的知识点、章节、题型和难度\n"
        "- 题干必须是完整学科问题，不能是占位模板或泛泛描述\n"
        "- 选择题选项必须合理、有迷惑性，解析必须说明答案原因\n"
        "- 如果提供课程参考资料，题目应优先基于资料中的概念或例题\n\n"
        "请求：\n"
        f"{build_question_generation_user_message(request, course_knowledge_context=course_knowledge_context)}\n\n"
        "待审查题目 JSON：\n"
        f"{questions_json}\n\n"
        "只输出 JSON 对象：{\"accepted\": true|false, \"reasons\": [\"...\"]}。"
    )


def build_knowledge_point_guard_prompt(
    request: QuestionGenerateRequest,
    questions_json: str,
    course_knowledge_context: str | None = None,
) -> str:
    """构建知识点贴合度审查提示词，输入请求和候选题 JSON，输出是否接受的 JSON 判定。"""
    context = course_knowledge_context or "无"
    return (
        "你是 EDUagent 的知识点贴合度审查员。请只判断候选题是否应被接受，不要改写题目。\n\n"
        "审查目标：\n"
        "- 题目必须贴合请求中的 knowledge_point；若请求未给出 knowledge_point，则优先贴合个性化上下文 wrong_points\n"
        "- 题目的 knowledge_point、content、explanation 应能体现目标知识点或同源概念\n"
        "- 如果提供课程参考资料，题目应能对应资料中的概念、例题或知识点\n"
        "- 没有明确目标知识点时，不要因为综合出题而拒绝\n\n"
        "请求：\n"
        f"{build_question_generation_user_message(request, course_knowledge_context=None)}\n\n"
        "课程参考资料：\n"
        f"{context}\n\n"
        "候选题 JSON：\n"
        f"{questions_json}\n\n"
        "只输出 JSON 对象：{\"accepted\": true|false, \"reasons\": [\"...\"]}。"
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


def build_evaluate_system_prompt() -> str:
    return (
        "你是 EDUagent 的评测诊断助手。根据题目、标准答案、用户答案和系统已完成的判分结果，"
        "为每道题生成详细解析，并给出综合诊断。\n\n"
        "判分（is_correct）已由系统完成，你不需要也不应该修改判分结果。"
        "你的任务是：解释为什么对/错、找出错误共性、给出复习建议。\n\n"
        "输出必须是一个 JSON 对象，包含以下字段：\n"
        "- per_question_results: 数组，每个元素为 {question_id, explanation, related_knowledge_points}\n"
        "  - question_id: 题目 ID（必填，必须与输入完全一致）\n"
        "  - explanation: 详细解析。正确时简要说明思路，错误时分析原因并给出正确解法（必填）\n"
        "  - related_knowledge_points: 关联知识点名称数组\n"
        "- diagnosis: 对象，包含 {summary, weak_points, suggestions}\n"
        "  - summary: 整体诊断总结，涵盖表现概览、共性问题和改进方向（必填）\n"
        "  - weak_points: 数组，每个元素为 {name, error_pattern}\n"
        "    - name: 薄弱知识点名称（必填）\n"
        "    - error_pattern: 具体的错误模式描述，如\"混淆了概念X和Y\"（必填）\n"
        "  - suggestions: 复习建议数组，每条建议应具体可操作（必填）\n\n"
        "规则：\n"
        "- 每个输入题目都必须出现在 per_question_results 中，不要漏题或新增题目\n"
        "- 解释要针对该题的具体错误，不要泛泛而谈\n"
        "- 建议要具体（如\"完成递归章节的前3道练习题\"），不要只说\"多练习\"\n"
        "- 只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字"
    )


def build_evaluate_user_message(
    request: AssessmentEvaluateRequest,
    rule_result: AssessmentResult,
) -> str:
    parts: list[str] = []
    parts.append(f"用户ID：{request.user_id}")
    parts.append(f"课程ID：{request.course_id}")
    mastery_text = _format_mastery(request.user_mastery)
    parts.append(f"用户掌握度：{mastery_text}")
    parts.append("")
    parts.append("题目与判分结果：")
    for pr in rule_result.per_question_results:
        question = _find_question(request.questions, pr.question_id)
        submitted = _find_answer(request.answers, pr.question_id)
        if question is None:
            continue
        parts.append(f"  ---")
        parts.append(f"  题目ID：{question.id}")
        parts.append(f"  题型：{question.type}")
        parts.append(f"  题目内容：{question.content}")
        parts.append(f"  标准答案：{_format_answer_str(question.correct_answer)}")
        parts.append(f"  用户答案：{_format_answer_str(submitted.answer) if submitted else '未提交'}")
        parts.append(f"  判分结果：{'正确' if pr.is_correct else '错误'}")
        parts.append(f"  知识点：{question.knowledge_point}")
    return "\n".join(parts)


def _find_question(questions, question_id: str):
    for q in questions:
        if q.id == question_id:
            return q
    return None


def _find_answer(answers, question_id: str):
    for a in answers:
        if a.question_id == question_id:
            return a
    return None


def _format_answer_str(answer) -> str:
    if isinstance(answer, list):
        return "、".join(sorted(str(item).strip() for item in answer))
    return str(answer).strip()


def _format_mastery(mastery: dict | None) -> str:
    if not mastery:
        return "无"
    import json

    return json.dumps(mastery, ensure_ascii=False)
