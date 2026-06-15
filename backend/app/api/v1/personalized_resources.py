from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.others import AsyncTask, Resource, UserPersonalizedResource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.personalized import PersonalizedResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services import quiz_service

router = APIRouter(prefix="/api/v1/personalized-resources", tags=["personalized-resources"])


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


@router.get("")
async def list_personalized_resources(
    course_id: str = Query(...),
    source_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserPersonalizedResource).where(
        UserPersonalizedResource.user_id == current_user.id,
        UserPersonalizedResource.course_id == course_id,
        UserPersonalizedResource.is_deleted == False,
    )
    if source_type:
        query = query.where(UserPersonalizedResource.source_type == source_type)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(UserPersonalizedResource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    uprs = result.scalars().all()

    # Preload related resources and questions
    resource_ids = [u.resource_id for u in uprs if u.resource_id]
    question_ids = [u.question_id for u in uprs if u.question_id]
    task_ids = [u.task_id for u in uprs if u.task_id]

    resources_map: dict = {}
    if resource_ids:
        res_r = await db.execute(
            select(Resource).where(Resource.id.in_(resource_ids), Resource.is_deleted == False)
        )
        resources_map = {r.id: r for r in res_r.scalars().all()}

    questions_map: dict = {}
    if question_ids:
        q_r = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id.in_(question_ids), QuizQuestion.is_deleted == False)
        )
        questions_map = {q.id: q for q in q_r.scalars().all()}

    tasks_map: dict = {}
    if task_ids:
        t_r = await db.execute(
            select(AsyncTask).where(AsyncTask.id.in_(task_ids), AsyncTask.is_deleted == False)
        )
        tasks_map = {t.id: t for t in t_r.scalars().all()}

    # processing_count: 全量统计（不限当前页），前端据此决定是否继续轮询
    pc_r = await db.execute(
        select(func.count()).select_from(
            select(UserPersonalizedResource.id)
            .join(AsyncTask, AsyncTask.id == UserPersonalizedResource.task_id)
            .where(
                UserPersonalizedResource.user_id == current_user.id,
                UserPersonalizedResource.course_id == course_id,
                UserPersonalizedResource.is_deleted == False,
                AsyncTask.status == "processing",
            )
            .subquery()
        )
    )
    processing_count = pc_r.scalar() or 0

    items = []
    for u in uprs:
        task = tasks_map.get(u.task_id) if u.task_id else None
        task_status = task.status if task else None

        resource_data = None
        if u.resource_id:
            r = resources_map.get(u.resource_id)
            if r:
                resource_data = {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                }

        question_data = None
        if u.question_id:
            q = questions_map.get(u.question_id)
            if q:
                question_data = {
                    "id": q.id,
                    "type": q.type,
                    "content": q.content,
                    "options": q.options or [],
                    "knowledge_point": q.knowledge_point,
                    "chapter": q.chapter,
                    "difficulty": q.difficulty,
                }

        items.append({
            "id": u.id,
            "source_type": u.source_type,
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "task_id": u.task_id,
            "task_status": task_status,
            "resource": resource_data,
            "question": question_data,
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "processing_count": processing_count,
        },
    }
