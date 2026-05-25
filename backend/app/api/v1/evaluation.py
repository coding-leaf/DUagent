from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation
from app.models.user import User

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

_empty_table = {"columns": [], "rows": []}


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Evaluation)
        .where(
            Evaluation.user_id == current_user.id,
            Evaluation.course_id == course_id,
            Evaluation.is_deleted == False,
        )
        .order_by(Evaluation.generated_at.desc())
    )
    ev = result.scalars().first()

    if ev is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "progress_table": _empty_table,
                "mastery_table": _empty_table,
                "resource_usage_table": _empty_table,
                "summary_text": "",
                "generated_at": None,
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": ev.course_id,
            "progress_table": ev.progress_table or _empty_table,
            "mastery_table": ev.mastery_table or _empty_table,
            "resource_usage_table": ev.resource_usage_table or _empty_table,
            "summary_text": ev.summary_text or "",
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        },
    }


@router.post("/refresh")
async def refresh_evaluation(
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
        task_type="evaluation_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate completion for v1
    ev = Evaluation(
        user_id=current_user.id,
        course_id=course_id,
        progress_table={
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "progress", "title": "进度"}],
            "rows": [{"chapter": "第1章", "progress": "30%"}],
        },
        mastery_table={
            "columns": [{"key": "point", "title": "知识点"}, {"key": "mastery", "title": "掌握度"}],
            "rows": [{"point": "基础概念", "mastery": "85%"}],
        },
        resource_usage_table={
            "columns": [{"key": "type", "title": "类型"}, {"key": "count", "title": "次数"}],
            "rows": [{"type": "文档", "count": 5}],
        },
        summary_text="评估已生成",
    )
    db.add(ev)
    task.status = "completed"
    task.result = {"updated_at": datetime.now(timezone.utc).isoformat()}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
