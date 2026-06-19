from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import LearningPath
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.knowledge_progress import build_node_progress_rows


def topo_sort_kg_nodes(
    nodes: list[dict],
    edges: list[dict],
) -> list[dict]:
    """Kahn topological sort of KG nodes based on edges.

    Returns nodes ordered so that prerequisites come before dependents.
    Falls back to original array order if edges is empty.
    """
    if not nodes:
        return []
    if not edges:
        return list(nodes)

    node_ids = {n["id"] for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if from_id in node_ids and to_id in node_ids:
            adj[from_id].append(to_id)
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

    # Start with nodes that have zero in-degree, in original array order
    queue = [n["id"] for n in nodes if in_degree.get(n["id"], 0) == 0]
    sorted_ids: list[str] = []
    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        for neighbor in adj.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Append any remaining nodes not reached (cycles or missing edge refs)
    sorted_set = set(sorted_ids)
    for n in nodes:
        if n["id"] not in sorted_set:
            sorted_ids.append(n["id"])

    # Map back to node dicts preserving all fields
    node_map = {n["id"]: dict(n) for n in nodes}
    return [node_map[nid] for nid in sorted_ids if nid in node_map]


def map_assessment_to_status(assessment_state: str) -> str:
    return {
        "mastered": "completed",
        "learning": "in_progress",
        "weak": "recommended",
        "pending_practice": "pending",
        "unstarted": "pending",
    }.get(assessment_state, "pending")


def apply_progress_to_nodes(
    nodes: list[dict],
    progress_by_id: dict[str, dict],
) -> list[dict]:
    """用实时进度覆盖节点的 status 和 mastery，其余字段保留。"""
    result = []
    for node in nodes:
        node_id = node.get("id") or node.get("node_id", "")
        progress = progress_by_id.get(node_id)
        if progress is None:
            result.append(dict(node))
            continue
        updated = dict(node)
        updated["status"] = map_assessment_to_status(progress.get("assessment_state", "unstarted"))
        mastery_score = progress.get("mastery_score")
        if mastery_score is not None:
            updated["mastery"] = mastery_score
        result.append(updated)
    return result


def build_current_position_from_nodes(nodes: list[dict]) -> dict | None:
    """取第一个非 pending 节点作为 current_position；全为 pending 时取第一个节点。"""
    if not nodes:
        return None
    for node in nodes:
        if node.get("status") != "pending":
            return {"node_id": node.get("id", ""), "node_name": node.get("name", "")}
    first = nodes[0]
    return {"node_id": first.get("id", ""), "node_name": first.get("name", "")}


async def synthesize_kg_fallback_path(
    db: AsyncSession,
    course_id: str,
) -> dict | None:
    """从 active KG 合成学习路径骨架。

    查找链: CourseOffering(id=course_id) → catalog_id →
            CourseCatalog → kg_host_course_id → active KG.
    返回 KG 节点（拓扑排序）+ 边，全部 status="recommended"。
    如果任一环节查不到，返回 None。
    """
    # 1. CourseOffering → catalog_id
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        return None

    # 2. CourseCatalog → kg_host_course_id
    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None or not catalog.kg_host_course_id:
        return None

    # 3. Active KG
    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
    if kg is None:
        return None

    kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
    if not kg_nodes:
        return None

    kg_edges = kg.edges if isinstance(kg.edges, list) else []

    # 4. Topo sort
    sorted_nodes = topo_sort_kg_nodes(kg_nodes, kg_edges)

    # 5. Assemble nodes with status/mastery/order
    assembled_nodes = []
    for idx, node in enumerate(sorted_nodes):
        assembled_nodes.append({
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            "chapter": node.get("chapter", ""),
            "order": idx + 1,
            "status": "recommended",
            "mastery": 0,
        })

    first_node = assembled_nodes[0]

    return {
        "course_id": course_id,
        "nodes": assembled_nodes,
        "edges": kg_edges or [],
        "current_position": {
            "node_id": first_node["id"],
            "node_name": first_node["name"],
        },
        "source": "kg_fallback",
        "generated_at": kg.create_time.isoformat() if kg.create_time else None,
    }


class LearningPathService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_learning_path(self, user_id: str, course_id: str) -> dict:
        progress_rows = await build_node_progress_rows(user_id, course_id, self.db)
        progress_by_id: dict[str, dict] = {row["node_id"]: row for row in progress_rows}

        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted == False,
            )
            .order_by(LearningPath.generated_at.desc())
        )
        learning_path = result.scalars().first()

        if learning_path is not None:
            merged_nodes = apply_progress_to_nodes(learning_path.nodes or [], progress_by_id)
            current_position = (
                {"node_id": learning_path.current_node_id, "node_name": learning_path.current_node_name}
                if merged_nodes and learning_path.current_node_id
                else None
            )
            return {
                "course_id": learning_path.course_id,
                "nodes": merged_nodes,
                "edges": learning_path.edges or [],
                "current_position": current_position,
                "source": "realtime_merged",
                "generated_at": learning_path.generated_at.isoformat() if learning_path.generated_at else None,
            }

        fallback = await synthesize_kg_fallback_path(self.db, course_id)
        if fallback is not None:
            kg_nodes = apply_progress_to_nodes(fallback["nodes"], progress_by_id)
            return {
                "course_id": fallback["course_id"],
                "nodes": kg_nodes,
                "edges": fallback.get("edges") or [],
                "current_position": build_current_position_from_nodes(kg_nodes),
                "source": "kg_realtime",
                "generated_at": fallback.get("generated_at"),
            }

        return {
            "course_id": course_id,
            "nodes": [],
            "edges": [],
            "current_position": None,
            "source": "kg_fallback",
            "generated_at": None,
        }
