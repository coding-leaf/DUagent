from typing import Any

from agent_service.schemas.learning_path import (
    CurrentPosition,
    LearningPathData,
    LearningPathEdge,
    LearningPathGenerateRequest,
    LearningPathNode,
)


def generate_learning_path_data(request: LearningPathGenerateRequest) -> LearningPathData:
    """根据静态知识图谱、画像和评估数据生成规则版学习路径，返回结构化路径结果。"""
    weak_points = _extract_weak_points(request.profile)
    mastery_by_name = _extract_mastery_by_name(request.profile, request.evaluation)

    nodes = [
        _build_path_node(
            node_id=node.id,
            name=node.name,
            order=index + 1,
            weak_points=weak_points,
            mastery_by_name=mastery_by_name,
        )
        for index, node in enumerate(request.knowledge_graph.nodes)
    ]
    edges = [LearningPathEdge.model_validate({"from": edge.from_, "to": edge.to}) for edge in request.knowledge_graph.edges]

    return LearningPathData(
        nodes=nodes,
        edges=edges,
        current_position=_build_current_position(nodes),
    )


def _build_path_node(
    node_id: str | None,
    name: str | None,
    order: int,
    weak_points: set[str],
    mastery_by_name: dict[str, float],
) -> LearningPathNode:
    mastery = mastery_by_name.get(name or "")
    status = _node_status(name=name, mastery=mastery, weak_points=weak_points)

    return LearningPathNode(
        id=node_id,
        name=name,
        status=status,
        mastery=mastery,
        order=order,
        reason=_node_reason(status=status, name=name),
    )


def _node_status(name: str | None, mastery: float | None, weak_points: set[str]) -> str:
    if name and name in weak_points:
        return "recommended"
    if mastery is not None and mastery >= 80:
        return "completed"
    if mastery is not None and mastery > 0:
        return "in_progress"
    return "pending"


def _build_current_position(nodes: list[LearningPathNode]) -> CurrentPosition | None:
    for status in ("recommended", "in_progress", "pending"):
        for node in nodes:
            if node.status == status:
                return CurrentPosition(node_id=node.id, node_name=node.name)
    return None


def _node_reason(status: str, name: str | None) -> str:
    point_name = name or "该知识点"
    reasons = {
        "recommended": f"{point_name}属于当前薄弱点，建议优先学习。",
        "completed": f"{point_name}掌握度较高，可作为已完成节点。",
        "in_progress": f"{point_name}已有一定掌握度，建议继续巩固。",
        "pending": f"{point_name}尚未体现明确掌握度，暂列为待学习节点。",
    }
    return reasons[status]


def _extract_weak_points(profile: dict[str, Any]) -> set[str]:
    weak_points: set[str] = set()
    for key in ("cognitive_blindspots", "knowledge_weak"):
        value = profile.get(key)
        if isinstance(value, list):
            weak_points.update(_extract_names(value))
    return weak_points


def _extract_mastery_by_name(profile: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, float]:
    mastery_by_name: dict[str, float] = {}
    for source in (
        profile.get("knowledge_coordinates"),
        evaluation.get("mastery"),
        evaluation.get("knowledge_coordinates"),
    ):
        if isinstance(source, list):
            mastery_by_name.update(_extract_mastery_items(source))
    return mastery_by_name


def _extract_names(items: list[Any]) -> set[str]:
    names: set[str] = set()
    for item in items:
        if isinstance(item, str) and item.strip():
            names.add(item.strip())
        if isinstance(item, dict):
            name = item.get("name") or item.get("knowledge_point")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
    return names


def _extract_mastery_items(items: list[Any]) -> dict[str, float]:
    mastery_by_name: dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("knowledge_point")
        mastery = item.get("mastery")
        if isinstance(name, str) and isinstance(mastery, int | float):
            mastery_by_name[name] = float(mastery)
    return mastery_by_name
