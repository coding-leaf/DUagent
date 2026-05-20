import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation
from app.models.user import User
from app.schemas.ai_features import EvaluationRefreshRequest

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

_empty_eval = {
    "course_id": "",
    "progress_table": {"columns": [], "rows": []},
    "mastery_table": {"columns": [], "rows": []},
    "resource_usage_table": {"columns": [], "rows": []},
    "summary_text": "",
    "generated_at": "",
}


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == current_user.id, Evaluation.course_id == course_id)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = result.scalars().first()

    if ev is None:
        data = dict(_empty_eval)
        data["course_id"] = course_id
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return {"code": 200, "message": "success", "data": data}

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": ev.course_id,
            "progress_table": ev.progress_table,
            "mastery_table": ev.mastery_table,
            "resource_usage_table": ev.resource_usage_table,
            "summary_text": ev.summary_text,
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else "",
        },
    }


@router.post("/refresh")
async def refresh_evaluation(
    req: EvaluationRefreshRequest,
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
        task_type="evaluation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate async: create placeholder with correct TableData format
    ev = Evaluation(
        user_id=current_user.id,
        course_id=req.course_id,
        progress_table={
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "progress", "title": "进度"}],
            "rows": [{"chapter": "第1章", "progress": "30%"}, {"chapter": "第2章", "progress": "10%"}],
        },
        mastery_table={
            "columns": [{"key": "point", "title": "知识点"}, {"key": "mastery", "title": "掌握度"}],
            "rows": [{"point": "基础概念", "mastery": "85%"}, {"point": "进阶应用", "mastery": "40%"}],
        },
        resource_usage_table={
            "columns": [{"key": "type", "title": "类型"}, {"key": "count", "title": "次数"}],
            "rows": [{"type": "文档", "count": 5}, {"type": "视频", "count": 3}],
        },
        summary_text="评估已生成（示例数据）",
    )
    db.add(ev)

    task.status = "completed"
    task.result = {"evaluation_id": ev.id}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 200, "message": "success", "data": {"task_id": task.id}},
    )
