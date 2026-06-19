import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.user import User
from app.schemas.ai_features import RefreshRequest
from app.services.learning_path_refresh_service import (
    LearningPathRefreshService,
    run_learning_path_refresh_background,
)
from app.services.learning_path_service import (
    LearningPathService,
)
from app.services.node_resource_service import NodeResourceService

router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await LearningPathService(db).get_learning_path(current_user.id, course_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


@router.post("/refresh")
async def refresh_learning_path(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习路径（真异步）。

    请求内：权限校验 → payload 组装 → 创建 AsyncTask → commit → 返回 202。
    后台 run_learning_path_refresh_background：Agent 调用 → 锁 → 写库 → task 完成/失败。
    """
    course_id = req.course_id
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    refresh_service = LearningPathRefreshService(db)
    payload = await refresh_service.assemble_payload(current_user.id, course_id)
    task = await refresh_service.create_refresh_task(current_user.id, course_id)
    # commit point: task persisted before background dispatch
    await db.commit()

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(run_learning_path_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(
    node_id: str,
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await NodeResourceService(db).get_node_resources(current_user, course_id, node_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }
