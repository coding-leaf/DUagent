from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.services.course_knowledge_graphs import get_active_knowledge_graph


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


async def _latest_learning_path(
    db: AsyncSession,
    course_id: str,
    user_id: str | None,
) -> LearningPath | None:
    query = select(LearningPath).where(
        LearningPath.course_id == course_id,
        LearningPath.is_deleted == False,
    )
    if user_id:
        query = query.where(LearningPath.user_id == user_id)
    query = query.order_by(
        LearningPath.generated_at.desc(),
        LearningPath.update_time.desc(),
        LearningPath.create_time.desc(),
    )
    result = await db.execute(query)
    return result.scalars().first()


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or node.get("node_id") or node.get("name") or "").strip()


def _node_name(node: dict[str, Any], fallback: str) -> str:
    return str(node.get("name") or node.get("label") or fallback).strip()


def _resource_ids(resources: list[Resource]) -> list[str]:
    return sorted({resource.id for resource in resources})


async def _resources_by_knowledge_point(
    db: AsyncSession,
    course_id: str,
    node_name: str,
) -> list[Resource]:
    result = await db.execute(
        select(Resource).where(
            Resource.course_id == course_id,
            Resource.knowledge_point == node_name,
            Resource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def _resources_by_chapter(
    db: AsyncSession,
    course_id: str,
    chapter: str,
) -> list[Resource]:
    if not chapter:
        return []
    result = await db.execute(
        select(Resource).where(
            Resource.course_id == course_id,
            Resource.chapter == chapter,
            Resource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def _quizzes_by_knowledge_point(
    db: AsyncSession,
    course_id: str,
    node_name: str,
) -> list[QuizQuestion]:
    result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point == node_name,
            QuizQuestion.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def _all_resources(db: AsyncSession, course_id: str) -> list[Resource]:
    result = await db.execute(
        select(Resource).where(
            Resource.course_id == course_id,
            Resource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


def _kg_node_map(kg: CourseKnowledgeGraph | None) -> dict[str, dict[str, Any]]:
    nodes = _as_dict_list(kg.nodes if kg else [])
    return {node_id: node for node in nodes if (node_id := _node_id(node))}


def _has_kg_node_tag(resource: Resource) -> bool:
    tags = resource.tags or []
    if not isinstance(tags, list):
        return False
    return any(isinstance(tag, str) and tag.startswith("kg_node:") for tag in tags)


async def build_learning_path_resource_report(
    db: AsyncSession,
    *,
    catalog_id: str,
    course_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    learning_path = await _latest_learning_path(db, course_id, user_id)
    active_kg = await get_active_knowledge_graph(db, course_id)
    kg_nodes = _kg_node_map(active_kg)
    path_nodes = _as_dict_list(learning_path.nodes if learning_path else [])
    resources = await _all_resources(db, course_id)
    kg_tagged_resource_count = sum(1 for resource in resources if _has_kg_node_tag(resource))

    rows: list[dict[str, Any]] = []
    for node in path_nodes:
        node_id = _node_id(node)
        if not node_id:
            continue
        node_name = _node_name(node, node_id)
        kg_node = kg_nodes.get(node_id)
        chapter = str((kg_node or {}).get("chapter") or "").strip()

        weak_resources = await _resources_by_knowledge_point(db, course_id, node_name)
        chapter_resources = await _resources_by_chapter(db, course_id, chapter)
        quizzes = await _quizzes_by_knowledge_point(db, course_id, node_name)

        weak_resource_ids = _resource_ids(weak_resources)
        chapter_resource_ids = _resource_ids(chapter_resources)
        exercise_ids = sorted({quiz.id for quiz in quizzes})
        candidate_ids = set(weak_resource_ids) | set(chapter_resource_ids) | set(exercise_ids)

        rows.append(
            {
                "node_id": node_id,
                "node_name": node_name,
                "chapter": chapter,
                "matched_active_kg": kg_node is not None,
                "weak_point_resource_ids": weak_resource_ids,
                "chapter_resource_ids": chapter_resource_ids,
                "exercise_ids": exercise_ids,
                "candidate_count": len(candidate_ids),
                "resource_count": len(set(weak_resource_ids) | set(chapter_resource_ids)),
                "exercise_count": len(exercise_ids),
            }
        )

    path_node_count = len(rows)
    matched_kg_count = sum(1 for row in rows if row["matched_active_kg"])
    nodes_with_resources_count = sum(1 for row in rows if row["candidate_count"] > 0)
    empty_node_count = path_node_count - nodes_with_resources_count

    return {
        "catalog_id": catalog_id,
        "course_id": course_id,
        "user_id": learning_path.user_id if learning_path else user_id,
        "learning_path_id": learning_path.id if learning_path else None,
        "active_kg_id": active_kg.id if active_kg else None,
        "summary": {
            "learning_path_node_count": path_node_count,
            "active_kg_node_count": len(kg_nodes),
            "matched_active_kg_node_count": matched_kg_count,
            "nodes_with_any_resource_count": nodes_with_resources_count,
            "empty_node_count": empty_node_count,
            "node_resource_coverage_ratio": (
                nodes_with_resources_count / path_node_count if path_node_count else 0.0
            ),
            "kg_match_ratio": matched_kg_count / path_node_count if path_node_count else 0.0,
            "resource_count": len(resources),
            "kg_tagged_resource_count": kg_tagged_resource_count,
        },
        "nodes": rows,
    }
