import json
import re
from typing import Any

from pydantic import BaseModel, Field

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.learning_path import (
    build_learning_path_system_prompt,
    build_learning_path_user_message,
)
from agent_service.schemas.learning_path import (
    CurrentPosition,
    KnowledgeGraphNode,
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


logger = get_logger(__name__)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
_VALID_STATUSES = {"completed", "in_progress", "pending", "recommended"}


class _LearningPathStructuredOutput(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    current_position: dict[str, Any] = Field(default_factory=dict)


async def generate_learning_path_with_llm(
    request: LearningPathGenerateRequest,
    chat_provider,
) -> LearningPathData | None:
    """尝试用 LLM 增强学习路径规划，输入请求和 chat provider，输出 LearningPathData 或 None（降级）。"""
    if chat_provider is None:
        return None
    try:
        nodes_by_id = {
            node.id: node
            for node in request.knowledge_graph.nodes
            if node.id
        }
        messages = [
            ChatMessage(role="system", content=build_learning_path_system_prompt()),
            ChatMessage(role="user", content=build_learning_path_user_message(request)),
        ]
        
        # Phase 1D: 优先尝试 AgentScope structured_model
        try:
            raw = await chat_provider.complete(messages, structured_model=_LearningPathStructuredOutput, disable_thinking=True)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    llm_nodes = data.get("nodes")
                    if not isinstance(llm_nodes, list):
                        raise ValueError("LLM output missing nodes array")
                    coerced_nodes = _coerce_path_nodes(llm_nodes, nodes_by_id)
                    edges = [
                        LearningPathEdge.model_validate({"from": e.from_, "to": e.to})
                        for e in request.knowledge_graph.edges
                    ]
                    current_position = _coerce_current_position(
                        data.get("current_position"),
                        {n.id for n in coerced_nodes if n.id},
                        nodes_by_id,
                        coerced_nodes,
                    )
                    logger.info("LLM structured_model succeeded: %s", "learning-path/generate")
                    return LearningPathData(
                        nodes=coerced_nodes, edges=edges, current_position=current_position
                    )
        except Exception:
            logger.debug("structured_model path failed, falling back to JSON parsing", exc_info=True)

        # Fallback: 原有 markdown fence JSON 解析
        raw = await chat_provider.complete(messages)
        data = _parse_learning_path_json(raw)
        llm_nodes = data.get("nodes")
        if not isinstance(llm_nodes, list):
            raise ValueError("LLM output missing nodes array")
        coerced_nodes = _coerce_path_nodes(llm_nodes, nodes_by_id)
        edges = [
            LearningPathEdge.model_validate({"from": e.from_, "to": e.to})
            for e in request.knowledge_graph.edges
        ]
        current_position = _coerce_current_position(
            data.get("current_position"),
            {n.id for n in coerced_nodes if n.id},
            nodes_by_id,
            coerced_nodes,
        )
        logger.info("LLM generation succeeded: %s", "learning-path/generate")
        return LearningPathData(
            nodes=coerced_nodes, edges=edges, current_position=current_position
        )
    except Exception:
        logger.warning(
            "LLM learning path generation failed, falling back to rule-based",
            exc_info=True,
        )
        return None


def _parse_learning_path_json(raw: str) -> dict:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _coerce_path_nodes(
    llm_nodes: list[dict],
    nodes_by_id: dict[str, KnowledgeGraphNode],
) -> list[LearningPathNode]:
    valid_ids = set(nodes_by_id.keys())
    result: list[LearningPathNode] = []
    for item in llm_nodes:
        if not isinstance(item, dict):
            continue
        node_id = item.get("id")
        if not isinstance(node_id, str) or node_id not in valid_ids:
            continue
        input_node = nodes_by_id[node_id]
        status = item.get("status")
        if status not in _VALID_STATUSES:
            status = "pending"
        mastery = item.get("mastery")
        if isinstance(mastery, int | float):
            mastery = max(0.0, min(100.0, float(mastery)))
        else:
            mastery = None
        order = item.get("order")
        if isinstance(order, int | float):
            order = int(order)
        else:
            order = len(result) + 1
        reason = item.get("reason")
        if not isinstance(reason, str):
            reason = ""
        result.append(
            LearningPathNode(
                id=node_id,
                name=input_node.name,
                status=status,
                mastery=mastery,
                order=order,
                reason=reason,
            )
        )
    return result


def _coerce_current_position(
    llm_cp,
    valid_ids: set[str],
    nodes_by_id: dict[str, KnowledgeGraphNode],
    nodes: list[LearningPathNode],
) -> CurrentPosition | None:
    if isinstance(llm_cp, dict):
        node_id = llm_cp.get("node_id")
        if isinstance(node_id, str) and node_id in valid_ids:
            return CurrentPosition(
                node_id=node_id, node_name=nodes_by_id[node_id].name
            )
    for status in ("recommended", "in_progress", "pending"):
        for node in nodes:
            if node.status == status:
                return CurrentPosition(
                    node_id=node.id, node_name=nodes_by_id[node.id].name
                )
    return None
