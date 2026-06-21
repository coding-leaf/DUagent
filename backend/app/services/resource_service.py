from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import AsyncTask, Resource
from app.models.user import User
from app.schemas.operations import ResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services.resource_scope import (
    ensure_course_resource_access,
    resolve_course_resource_scope,
    resource_scope_clause,
    user_can_access_catalog_resources,
)


class ResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_resources(
        self,
        course_id: str,
        current_user: User,
        type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Resource], int]:
        await ensure_course_resource_access(self.db, current_user, course_id)
        scope = await resolve_course_resource_scope(self.db, course_id)

        query = select(Resource).where(
            resource_scope_clause(course_id, scope.catalog_id),
            Resource.is_deleted == False,
        )
        if type:
            query = query.where(Resource.type == type)
        if keyword:
            query = query.where(Resource.title.contains(keyword))

        count_r = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_r.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Resource.create_time.desc()).offset(offset).limit(page_size)
        )
        resources = result.scalars().all()
        return list(resources), total

    async def get_resource_detail(
        self,
        id: str,
        current_user: User,
    ) -> tuple[Resource, str | None]:
        result = await self.db.execute(
            select(Resource).where(Resource.id == id, Resource.is_deleted == False)
        )
        resource = result.scalar_one_or_none()
        if resource is None:
            raise HTTPException(status_code=404, detail="Resource not found")

        if resource.catalog_id:
            if not await user_can_access_catalog_resources(self.db, current_user, resource.catalog_id):
                raise HTTPException(status_code=403, detail="No access to this resource")
        else:
            await ensure_course_resource_access(self.db, current_user, resource.course_id)

        preview = None
        if resource.type in ("document", "reading") and resource.content:
            preview = resource.content[:500]

        return resource, preview

    async def generate_resources(
        self,
        req: ResourceGenerateRequest,
        current_user: User,
        webhook_url: str,
    ) -> AsyncTask:
        catalog_context = await resolve_generation_catalog(self.db, req.course_id)

        # 创建任务
        task = AsyncTask(
            task_type="resource_generation",
            status="processing",
            user_id=current_user.id,
            course_id=req.course_id,
            result=catalog_context.model_dump(),
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        # 组装 Agent payload — task_id 由 Backend 生成并原样传入
        payload: dict = {
            "task_id": task.id,
            "user_id": current_user.id,
            "course_id": catalog_context.catalog_id,
            "webhook_url": webhook_url,
        }
        if req.chapter:
            payload["chapter"] = req.chapter
        if req.knowledge_point:
            payload["knowledge_point"] = req.knowledge_point
        if req.resource_types:
            payload["resource_types"] = req.resource_types

        try:
            # 调用 Agent（异步，立即返回 202）
            await agent_client.post_json("/agent/v1/resources/generate", payload)
        except AgentServiceError as e:
            task.status = "failed"
            task.error_code = str(e.agent_code or "agent_error")
            task.error_message = e.message
            task.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            return task

        await self.db.flush()
        return task
