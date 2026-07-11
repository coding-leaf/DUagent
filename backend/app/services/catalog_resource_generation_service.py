from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import AsyncTask, Resource
from app.schemas.operations import CatalogResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.kg_resource_targets import select_valid_resource_targets
from app.services.resource_scope import resource_scope_clause

RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_explicit_resource_target(req: CatalogResourceGenerateRequest) -> bool:
    return bool((req.chapter or "").strip() or (req.knowledge_point or "").strip())


def course_material_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40913, "message": "课程资料尚未完成入库", "data": None},
    )


def knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40914, "message": "课程知识库为空", "data": None},
    )


def course_offering_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40915, "message": "课程资源库尚未绑定教学班", "data": None},
    )


class CatalogResourceGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_catalog_resources(
        self,
        catalog_id: str,
        *,
        resource_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        offering_result = await self.db.execute(
            select(CourseOffering.id).where(
                CourseOffering.catalog_id == catalog_id,
                CourseOffering.is_deleted == False,
            )
        )
        course_ids = list(offering_result.scalars().all())

        query = select(Resource).where(Resource.is_deleted == False)
        if course_ids:
            query = query.where(
                or_(*(resource_scope_clause(course_id, catalog_id) for course_id in course_ids))
            )
        else:
            query = query.where(Resource.catalog_id == catalog_id)
        if resource_type:
            query = query.where(Resource.type == resource_type)

        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(Resource.create_time.desc(), Resource.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        resources = result.scalars().all()
        return {
            "resources": [
                {
                    "id": r.id,
                    "course_id": r.course_id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "tags": r.tags or [],
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                    "view_count": r.view_count,
                    "created_at": r.create_time.isoformat() if r.create_time else "",
                }
                for r in resources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def delete_resource(self, resource_id: str, *, actor_user_id: str) -> Resource:
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id, Resource.is_deleted == False)
        )
        resource = result.scalar_one_or_none()
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40412, "message": "资源不存在", "data": None},
            )

        resource.is_deleted = True
        resource.update_by = actor_user_id
        await self.db.commit()
        return resource

    async def start_resource_generation(
        self,
        catalog: CourseCatalog,
        req: CatalogResourceGenerateRequest,
        *,
        actor_user_id: str,
        webhook_url: str,
    ) -> AsyncTask:
        if catalog.status != "ready":
            raise course_material_missing()
        if catalog.knowledge_status not in {"ready", "partial"}:
            raise course_material_missing()
        if (catalog.chunk_count or 0) <= 0:
            raise knowledge_base_empty()

        if not req.resource_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": 42210, "message": "至少选择一种资源类型", "data": None},
            )
        invalid_types = [item for item in req.resource_types if item not in RESOURCE_TYPES]
        if invalid_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": 42210,
                    "message": "资源类型不合法",
                    "data": {"invalid_types": invalid_types},
                },
            )

        offerings_result = await self.db.execute(
            select(CourseOffering)
            .where(
                CourseOffering.catalog_id == catalog.id,
                CourseOffering.is_deleted == False,
            )
            .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
        )
        offerings = offerings_result.scalars().all()
        fanout_course_ids = [offering.id for offering in offerings]
        if not fanout_course_ids and catalog.kg_host_course_id:
            fanout_course_ids = [catalog.kg_host_course_id]
        if not fanout_course_ids:
            raise course_offering_missing()

        resource_types = req.resource_types

        if not is_explicit_resource_target(req):
            return await self._start_kg_node_resource_generation(
                catalog,
                resource_types,
                fanout_course_ids,
                actor_user_id=actor_user_id,
                webhook_url=webhook_url,
            )

        task_result = {
            "catalog_id": catalog.id,
            "catalog_title": catalog.title,
            "fanout_course_ids": fanout_course_ids,
            "knowledge_status": catalog.knowledge_status,
            "degraded": catalog.knowledge_status == "partial",
            "chunk_count": catalog.chunk_count or 0,
            "resource_types": resource_types,
        }
        if req.chapter:
            task_result["chapter"] = req.chapter
        if req.knowledge_point:
            task_result["knowledge_point"] = req.knowledge_point

        task = AsyncTask(
            task_type="resource_generation",
            status="processing",
            progress=10,
            user_id=actor_user_id,
            course_id=None,
            result=task_result,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        payload = {
            "task_id": task.id,
            "user_id": actor_user_id,
            "course_id": catalog.id,
            "resource_types": resource_types,
            "webhook_url": webhook_url,
        }
        if req.chapter:
            payload["chapter"] = req.chapter
        if req.knowledge_point:
            payload["knowledge_point"] = req.knowledge_point

        try:
            await agent_client.post_json("/agent/v2/knowledge/resources/generations", payload)
        except AgentServiceError as e:
            task.status = "failed"
            task.error_code = str(e.agent_code or "agent_error")
            task.error_message = e.message
            task.progress = 100
            task.completed_at = now_utc()
            await self.db.commit()
            return task

        await self.db.commit()
        return task

    async def _start_kg_node_resource_generation(
        self,
        catalog: CourseCatalog,
        resource_types: list[str],
        fanout_course_ids: list[str],
        *,
        actor_user_id: str,
        webhook_url: str,
    ) -> AsyncTask:
        kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id or "")
        if kg is None:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=actor_user_id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                },
                error_code="kg_not_ready",
                error_message="课程知识图谱未就绪",
                completed_at=now_utc(),
            )
            self.db.add(task)
            await self.db.commit()
            return task

        selection = select_valid_resource_targets(
            kg.nodes if isinstance(kg.nodes, list) else []
        )
        target_nodes = selection["targets"]
        if not target_nodes:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=actor_user_id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                    "target_node_count": 0,
                    "total_child_count": 0,
                    "selection_degraded": selection["selection_degraded"],
                    "selection_degraded_reason": selection["degraded_reason"],
                },
                error_code="kg_target_empty",
                error_message="没有可用于资源挂载的 KG 节点",
                completed_at=now_utc(),
            )
            self.db.add(task)
            await self.db.commit()
            return task

        parent = AsyncTask(
            task_type="resource_generation",
            status="processing",
            progress=10,
            user_id=actor_user_id,
            course_id=None,
            result={
                "catalog_id": catalog.id,
                "catalog_title": catalog.title,
                "fanout_course_ids": fanout_course_ids,
                "mode": "kg_node_targets",
                "knowledge_status": catalog.knowledge_status,
                "degraded": catalog.knowledge_status == "partial",
                "chunk_count": catalog.chunk_count or 0,
                "resource_types": resource_types,
                "target_node_count": len(target_nodes),
                "total_child_count": len(target_nodes),
                "target_nodes": target_nodes,
                "skipped_nodes": selection["skipped"],
                "selection_degraded": selection["selection_degraded"],
                "selection_degraded_reason": selection["degraded_reason"],
                "completed_child_count": 0,
                "failed_child_count": 0,
                "successful_node_count": 0,
                "failed_node_count": 0,
            },
        )
        self.db.add(parent)
        await self.db.flush()
        await self.db.refresh(parent)

        children: list[AsyncTask] = []
        for target_node in target_nodes:
            child = AsyncTask(
                task_type="resource_generation",
                status="processing",
                progress=10,
                user_id=actor_user_id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "parent_task_id": parent.id,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_target",
                    "target_node": target_node,
                    "resource_types": resource_types,
                },
            )
            self.db.add(child)
            children.append(child)
        await self.db.flush()

        for child in children:
            target_node = child.result["target_node"]
            payload = {
                "task_id": child.id,
                "user_id": actor_user_id,
                "course_id": catalog.id,
                "chapter": target_node["chapter"],
                "knowledge_point": target_node["node_name"],
                "resource_types": resource_types,
                "webhook_url": webhook_url,
            }
            try:
                await agent_client.post_json("/agent/v2/knowledge/resources/generations", payload)
            except AgentServiceError as e:
                child.status = "failed"
                child.error_code = str(e.agent_code or "agent_error")
                child.error_message = e.message
                child.progress = 100
                child.completed_at = now_utc()

        await self.db.commit()
        return parent
