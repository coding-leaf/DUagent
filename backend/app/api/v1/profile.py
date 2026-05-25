from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, UserProfile
from app.models.user import User
from app.schemas.ai_features import ProfileInitializeRequest

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

_default_profile = {
    "modal_preference": {
        "video_animation": 50, "chart_logic": 50, "text_analysis": 50,
        "code_practice": 50, "formula_derivation": 50,
    },
    "guidance_level": {"current": "L2", "updated_at": ""},
    "knowledge_coordinates": [],
    "cognitive_blindspots": [],
    "drive_intent": {"type": "casual", "intensity": 30},
    "discipline_badge": {"subject": "", "level": "", "streak_days": 0},
    "generated_at": None,
}


def _profile_data(pf: UserProfile | None, course_id: str) -> dict:
    if pf is None:
        data = dict(_default_profile)
        data["course_id"] = course_id
        return data
    return {
        "course_id": pf.course_id,
        "modal_preference": pf.modal_preference or _default_profile["modal_preference"],
        "guidance_level": {
            "current": pf.guidance_level_current,
            "updated_at": pf.guidance_level_updated_at.isoformat() if pf.guidance_level_updated_at else "",
        },
        "knowledge_coordinates": pf.knowledge_coordinates or [],
        "cognitive_blindspots": pf.cognitive_blindspots or [],
        "drive_intent": pf.drive_intent or _default_profile["drive_intent"],
        "discipline_badge": pf.discipline_badge or _default_profile["discipline_badge"],
        "generated_at": pf.generated_at.isoformat() if pf.generated_at else None,
    }


@router.post("/initialize")
async def initialize_profile(
    req: ProfileInitializeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answers = req.answers or {}
    profile = UserProfile(
        user_id=current_user.id,
        course_id=req.course_id,
        guidance_level_current=answers.get("guidance_level", "L2"),
        guidance_level_updated_at=datetime.now(timezone.utc),
        modal_preference={k: 60 for k in (answers.get("modal_preference") or ["text"])},
        drive_intent={"type": answers.get("learning_goal", "casual"), "intensity": 50},
        knowledge_coordinates=[{"name": "入门", "status": "learning", "mastered_at": None}],
        generated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    return {"code": 200, "message": "success", "data": _profile_data(profile, req.course_id)}


@router.get("")
async def get_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProfile)
        .where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted == False,
        )
    )
    pf = result.scalar_one_or_none()
    return {"code": 200, "message": "success", "data": _profile_data(pf, course_id)}


@router.post("/refresh")
async def refresh_profile(
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
        task_type="profile_refresh",
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
