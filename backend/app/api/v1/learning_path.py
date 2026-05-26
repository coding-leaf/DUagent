from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, LearningPath
from app.models.user import User

router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
    )
    lp = result.scalar_one_or_none()

    if lp is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "nodes": [],
                "edges": [],
                "current_position": None,
                "generated_at": None,
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes or [],
            "edges": lp.edges or [],
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            } if lp.current_node_id else None,
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
        },
    }


@router.post("/refresh")
async def refresh_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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

    task = AsyncTask(
        task_type="learning_path_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    task.status = "completed"
    task.result = {"updated_at": datetime.now(timezone.utc).isoformat()}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(node_id: str, current_user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "node_id": node_id,
            "node_name": "示例知识点",
            "weak_point_tutorials": [],
            "exercises": [],
            "chapter_materials": [],
            "full_exercise_set": [],
        },
    }
