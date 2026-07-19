from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph


def _not_deleted() -> Any:
    return CourseKnowledgeGraph.is_deleted.is_(False)


async def get_active_knowledge_graph(
    db: AsyncSession,
    course_id: str,
) -> CourseKnowledgeGraph | None:
    """Return the active, non-deleted KG for a course, preferring newest version on dirty data."""
    result = await db.execute(
        select(CourseKnowledgeGraph)
        .where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_active.is_(True),
            _not_deleted(),
        )
        .order_by(CourseKnowledgeGraph.version.desc(), CourseKnowledgeGraph.update_time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_effective_knowledge_graph(
    db: AsyncSession,
    course_id: str,
) -> CourseKnowledgeGraph | None:
    """Teaching classes inherit the catalog host KG so all learning tools share node IDs."""
    graph = await get_active_knowledge_graph(db, course_id)
    if graph is not None:
        return graph

    host_result = await db.execute(
        select(CourseCatalog.kg_host_course_id)
        .join(CourseOffering, CourseOffering.catalog_id == CourseCatalog.id)
        .where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted.is_(False),
            CourseCatalog.is_deleted.is_(False),
        )
        .limit(1)
    )
    host_course_id = host_result.scalar_one_or_none()
    if not host_course_id:
        return None
    return await get_active_knowledge_graph(db, host_course_id)


async def next_knowledge_graph_version(db: AsyncSession, course_id: str) -> int:
    """Return max non-deleted KG version + 1 for the given course."""
    result = await db.execute(
        select(func.max(CourseKnowledgeGraph.version)).where(
            CourseKnowledgeGraph.course_id == course_id,
            _not_deleted(),
        )
    )
    current_max = result.scalar_one_or_none()
    return int(current_max or 0) + 1


async def create_knowledge_graph_version(
    db: AsyncSession,
    *,
    course_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    source_type: str,
    generation_strategy: str,
    metrics: dict | None = None,
    activate: bool = True,
    parent_graph_id: str | None = None,
) -> CourseKnowledgeGraph:
    """Create a KG version and optionally make it the only active non-deleted graph."""
    version = await next_knowledge_graph_version(db, course_id)
    if activate:
        await db.execute(
            update(CourseKnowledgeGraph)
            .where(CourseKnowledgeGraph.course_id == course_id, _not_deleted())
            .values(is_active=False)
        )

    graph = CourseKnowledgeGraph(
        course_id=course_id,
        version=version,
        is_active=activate,
        source_type=source_type,
        generation_strategy=generation_strategy,
        nodes=nodes,
        edges=edges,
        metrics=metrics,
        parent_graph_id=parent_graph_id,
    )
    db.add(graph)
    await db.flush()
    return graph


async def activate_knowledge_graph_version(
    db: AsyncSession,
    course_id: str,
    *,
    graph_id: str | None = None,
    version: int | None = None,
) -> CourseKnowledgeGraph:
    """Activate an existing KG version by id or version and return the activated graph."""
    if graph_id is None and version is None:
        raise ValueError("graph_id or version is required")

    filters = [
        CourseKnowledgeGraph.course_id == course_id,
        _not_deleted(),
    ]
    if graph_id is not None:
        filters.append(CourseKnowledgeGraph.id == graph_id)
    if version is not None:
        filters.append(CourseKnowledgeGraph.version == version)

    result = await db.execute(select(CourseKnowledgeGraph).where(*filters).limit(1))
    target = result.scalar_one_or_none()
    if target is None:
        raise ValueError("knowledge graph version not found")

    await db.execute(
        update(CourseKnowledgeGraph)
        .where(CourseKnowledgeGraph.course_id == course_id, _not_deleted())
        .values(is_active=False)
    )
    target.is_active = True
    await db.flush()
    return target
