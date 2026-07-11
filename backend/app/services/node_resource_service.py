from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import (
    ensure_course_resource_access,
    resolve_course_resource_scope,
    resource_scope_clause,
)


class NodeResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_node_resources(self, current_user: User, course_id: str, node_id: str) -> dict:
        await ensure_course_resource_access(self.db, current_user, course_id)
        resource_scope = await resolve_course_resource_scope(self.db, course_id)

        node_name = node_id
        chapter = ""

        kg = await self._resolve_active_kg(course_id)
        if kg and kg.nodes:
            kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
            for kg_node in kg_nodes:
                if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                    node_name = kg_node.get("name", node_id)
                    chapter = kg_node.get("chapter", "")
                    break

        latest_path = await self._latest_learning_path(current_user.id, course_id)
        if latest_path and latest_path.nodes:
            nodes = latest_path.nodes if isinstance(latest_path.nodes, list) else []
            for node in nodes:
                if isinstance(node, dict) and node.get("id") == node_id:
                    node_name = node.get("name", node_name)
                    break

        catalog_id, host_course_id = await self._resolve_catalog_context(course_id)

        return {
            "node_id": node_id,
            "node_name": node_name,
            "weak_point_tutorials": await self._weak_point_tutorials(
                course_id,
                resource_scope.catalog_id,
                node_name,
            ),
            "exercises": await self._node_exercises(course_id, catalog_id, host_course_id, node_name),
            "chapter_materials": await self._chapter_materials(
                course_id,
                resource_scope.catalog_id,
                chapter,
            ),
            "full_exercise_count": await self._full_exercise_count(course_id, catalog_id, host_course_id),
            "full_exercise_set": await self._full_exercise_set(course_id, catalog_id, host_course_id),
        }

    async def _resolve_catalog_context(self, course_id: str) -> tuple[str | None, str | None]:
        """查询课程与班级（Offering）级联关系，返回确定归属的 (catalog_id, host_course_id)"""
        offering_result = await self.db.execute(
            select(CourseOffering).where(
                CourseOffering.id == course_id,
                CourseOffering.is_deleted == False,
            )
        )
        offering = offering_result.scalar_one_or_none()
        if offering is not None:
            catalog_id = offering.catalog_id
            catalog_result = await self.db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            host_course_id = catalog.kg_host_course_id if catalog else None
            return catalog_id, host_course_id

        # 如果不是 Offering，尝试把 course_id 视为 host_course_id
        catalog_result = await self.db.execute(
            select(CourseCatalog).where(
                CourseCatalog.kg_host_course_id == course_id,
                CourseCatalog.is_deleted == False,
            )
        )
        catalog = catalog_result.scalar_one_or_none()
        return (catalog.id if catalog else None), course_id

    async def _resolve_active_kg(self, course_id: str):
        kg = None
        offering_result = await self.db.execute(
            select(CourseOffering).where(
                CourseOffering.id == course_id,
                CourseOffering.is_deleted == False,
            )
        )
        offering = offering_result.scalar_one_or_none()
        if offering is not None:
            catalog_result = await self.db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == offering.catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            if catalog is not None and catalog.kg_host_course_id:
                kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id)

        if kg is None:
            kg = await get_active_knowledge_graph(self.db, course_id)
        return kg

    async def _latest_learning_path(self, user_id: str, course_id: str) -> LearningPath | None:
        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted == False,
            )
            .order_by(LearningPath.generated_at.desc())
        )
        return result.scalars().first()

    async def _weak_point_tutorials(self, course_id: str, catalog_id: str | None, node_name: str) -> list[dict]:
        result = await self.db.execute(
            select(Resource).where(
                resource_scope_clause(course_id, catalog_id),
                Resource.knowledge_point == node_name,
                Resource.is_deleted == False,
            )
        )
        return [
            {"id": resource.id, "title": resource.title, "content": (resource.content or "")[:160]}
            for resource in result.scalars().all()
        ]

    async def _node_exercises(self, course_id: str, catalog_id: str | None, host_course_id: str | None, node_name: str) -> list[dict]:
        course_ids = {course_id}
        if host_course_id:
            course_ids.add(host_course_id)

        conditions = [QuizQuestion.course_id.in_(list(course_ids))]
        if catalog_id:
            conditions.append(QuizQuestion.catalog_id == catalog_id)

        result = await self.db.execute(
            select(QuizQuestion).where(
                or_(*conditions),
                QuizQuestion.knowledge_point == node_name,
                QuizQuestion.is_deleted == False,
                QuizQuestion.source.in_(["common", "baseline"]),
            )
        )
        return [
            {"id": question.id, "type": question.type, "content": question.content}
            for question in result.scalars().all()
        ]

    async def _chapter_materials(self, course_id: str, catalog_id: str | None, chapter: str) -> list[dict]:
        if not chapter:
            return []
        result = await self.db.execute(
            select(Resource).where(
                resource_scope_clause(course_id, catalog_id),
                Resource.chapter == chapter,
                Resource.is_deleted == False,
            )
        )
        return [
            {"id": resource.id, "title": resource.title, "type": resource.type, "url": resource.url or ""}
            for resource in result.scalars().all()
        ]

    async def _full_exercise_count(self, course_id: str, catalog_id: str | None, host_course_id: str | None) -> int:
        course_ids = {course_id}
        if host_course_id:
            course_ids.add(host_course_id)

        conditions = [QuizQuestion.course_id.in_(list(course_ids))]
        if catalog_id:
            conditions.append(QuizQuestion.catalog_id == catalog_id)

        result = await self.db.execute(
            select(func.count(QuizQuestion.id)).where(
                or_(*conditions),
                QuizQuestion.is_deleted == False,
                QuizQuestion.source.in_(["common", "baseline"]),
            )
        )
        return result.scalar() or 0

    async def _full_exercise_set(self, course_id: str, catalog_id: str | None, host_course_id: str | None) -> list[dict]:
        course_ids = {course_id}
        if host_course_id:
            course_ids.add(host_course_id)

        conditions = [QuizQuestion.course_id.in_(list(course_ids))]
        if catalog_id:
            conditions.append(QuizQuestion.catalog_id == catalog_id)

        result = await self.db.execute(
            select(QuizQuestion)
            .where(
                or_(*conditions),
                QuizQuestion.is_deleted == False,
                QuizQuestion.source.in_(["common", "baseline"]),
            )
            .limit(10)
        )
        return [
            {"id": question.id, "type": question.type, "content": question.content}
            for question in result.scalars().all()
        ]
