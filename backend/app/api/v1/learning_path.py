from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, LearningPath
from app.models.user import User
from app.schemas.ai_features import LearningPathRefreshRequest

router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPath)
        .where(LearningPath.user_id == current_user.id, LearningPath.course_id == course_id)
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
                "current_position": {"node_id": "", "node_name": ""},
                "generated_at": "",
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes,
            "edges": lp.edges,
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            },
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else "",
        },
    }


@router.post("/refresh")
async def refresh_learning_path(
    req: LearningPathRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == req.course_id,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    task = AsyncTask(
        task_type="learning_path",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate completion
    task.status = "completed"
    task.result = {"message": "学习路径刷新完成"}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 200, "message": "success", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(
    node_id: str,
    current_user: User = Depends(get_current_user),
):
    # In production: query resources for the specific knowledge node
    return {
        "code": 200,
        "message": "success",
        "data": {
            "node_id": node_id,
            "node_name": "示例知识点",
            "weak_point_tutorials": [
                {"title": "基础概念讲解", "content": "这个知识点主要涉及..."},
            ],
            "exercises": [
                {
                    "id": "ex1",
                    "type": "single_choice",
                    "content": "以下哪个选项是正确的？",
                },
            ],
            "chapter_materials": [
                {
                    "title": "章节教材",
                    "type": "document",
                    "url": "/files/materials/chapter1.pdf",
                },
            ],
            "full_exercise_set": [
                {
                    "id": "ex_full_1",
                    "type": "multi_choice",
                    "content": "综合练习题...",
                },
            ],
        },
    }
