import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, UserProfile
from app.models.user import User
from app.schemas.ai_features import ProfileInitializeRequest, ProfileRefreshRequest
from app.schemas.common import TaskIdResponse

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.post("/initialize")
async def initialize_profile(req: ProfileInitializeRequest, current_user: User = Depends(get_current_user)):
    """冷启动引导对话 (SSE)"""

    async def event_generator():
        # Simulated SSE flow
        questions = [
            "你好！让我们来了解一下你的学习偏好。你更喜欢通过哪种方式学习新知识？",
            "你平时看视频学习时，是喜欢动画演示还是真人讲解？",
            "遇到难题时，你希望得到什么样的帮助？",
        ]
        for q in questions:
            yield {"event": "message", "data": json.dumps({"type": "message", "content": q})}
            await asyncio.sleep(0.5)

        initial_profile = {
            "modal_preference": {
                "video_animation": 60,
                "chart_logic": 45,
                "text_analysis": 55,
                "code_practice": 70,
                "formula_derivation": 40,
            },
            "guidance_level": "L2",
            "knowledge_coordinates": [
                {"name": req.course_id, "status": "learning", "mastered_at": None}
            ],
            "cognitive_blindspots": [],
            "drive_intent": {"type": "daily_homework", "intensity": 50},
            "discipline_badge": {"subject": "通用", "level": "beginner", "streak_days": 1},
        }
        yield {
            "event": "done",
            "data": json.dumps({"type": "done", "profile": initial_profile}),
        }

    return EventSourceResponse(event_generator())


@router.get("")
async def get_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == current_user.id, UserProfile.course_id == course_id)
    )
    pf = result.scalar_one_or_none()

    if pf is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "modal_preference": {
                    "video_animation": 50,
                    "chart_logic": 50,
                    "text_analysis": 50,
                    "code_practice": 50,
                    "formula_derivation": 50,
                },
                "guidance_level": {"current": "L2", "updated_at": ""},
                "knowledge_coordinates": [],
                "cognitive_blindspots": [],
                "drive_intent": {"type": "casual", "intensity": 30},
                "discipline_badge": {"subject": "", "level": "", "streak_days": 0},
                "generated_at": "",
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": pf.course_id,
            "modal_preference": pf.modal_preference,
            "guidance_level": {
                "current": pf.guidance_level_current,
                "updated_at": pf.guidance_level_updated_at.isoformat() if pf.guidance_level_updated_at else "",
            },
            "knowledge_coordinates": pf.knowledge_coordinates,
            "cognitive_blindspots": pf.cognitive_blindspots,
            "drive_intent": pf.drive_intent,
            "discipline_badge": pf.discipline_badge,
            "generated_at": pf.generated_at.isoformat() if pf.generated_at else "",
        },
    }


@router.post("/refresh")
async def refresh_profile(
    req: ProfileRefreshRequest,
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
        task_type="profile",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate completion
    task.status = "completed"
    task.result = {"message": "画像刷新完成"}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 200, "message": "success", "data": {"task_id": task.id}},
    )
