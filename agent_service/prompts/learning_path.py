"""learning-path 接口的 LLM prompt 模板。"""

from agent_service.schemas.learning_path import LearningPathGenerateRequest


def build_learning_path_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习路径规划助手。根据给定的知识图谱、用户画像和学习评估数据，"
        "为每个知识点节点标注学习状态和排序。\n\n"
        "输出必须是一个 JSON 对象，包含两个字段：\n"
        "- nodes: 数组，每个元素为 {id, status, mastery, order, reason}\n"
        "  - id: 必须使用输入图谱中的节点 ID，不要编造\n"
        "  - status: completed / in_progress / pending / recommended 之一\n"
        "  - mastery: 0-100 的整数，表示掌握度估计\n"
        "  - order: 学习顺序序号，从 1 开始\n"
        "  - reason: 简短说明排序和状态的理由\n"
        "- current_position: 当前推荐开始学习的节点，格式为 {node_id}，node_id 必须在 nodes 中\n\n"
        "不要输出 name 字段，节点名称会由系统自动补充。"
        "只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字。"
    )


def build_learning_path_user_message(request: LearningPathGenerateRequest) -> str:
    nodes_text = "\n".join(
        f"- id={n.id}, name={n.name}, chapter={n.chapter or '无'}"
        for n in request.knowledge_graph.nodes
        if n.id
    )
    edges_text = "\n".join(
        f"- {e.from_} -> {e.to}"
        for e in request.knowledge_graph.edges
        if e.from_ and e.to
    )
    return (
        f"知识图谱节点：\n{nodes_text}\n\n"
        f"依赖边（前置 -> 后置）：\n{edges_text or '无'}\n\n"
        f"用户画像：{_format_json(request.profile)}\n"
        f"学习评估：{_format_json(request.evaluation)}\n"
    )


def _format_json(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2) if data else "{}"
