# backend/app/api/v1/profile.py
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.course import CourseEnrollment
from app.services.agent_client import AgentServiceError, agent_client
from app.services.profile_presenters import profile_data
from app.services.profile_service import ProfileService
from app.services.profile_dialogue_service import ProfileDialogueService
from app.services.profile_refresh_service import ProfileRefreshService, run_profile_refresh_background
from app.schemas.profile import (
    ProfileInitializeRequest,
    ProfileDialogueUpdateRequest,
    ProfileGoalUpdateRequest,
    ProfileInstructionUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

async def _verify_course_enrollment(user: User, course_id: str, db: AsyncSession):
    if user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

@router.post("/initialize")
async def initialize_profile(
    req: ProfileInitializeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.initialize_profile(current_user.id, req.course_id, req.answers or {})
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except Exception as e:
        await db.rollback()
        raise e

@router.get("")
async def get_profile(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, course_id, db)
    service = ProfileService(db)
    pf = await service.get_or_create_profile(current_user.id, course_id)
    return {"code": 200, "message": "success", "data": profile_data(pf, course_id, current_user)}

@router.post("/dialogue-update")
async def dialogue_update_profile(
    req: ProfileDialogueUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)

    payload = {
        "user_id": current_user.id,
        "course_id": req.course_id,
        "message": req.message,
    }
    try:
        data = await agent_client.post_json("/agent/v1/profile/dialogue-update", payload)
    except AgentServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.agent_code or e.status_code, "message": e.message, "data": None},
        ) from e

    extracted = data.get("profile") if isinstance(data, dict) and isinstance(data.get("profile"), dict) else data
    if not isinstance(extracted, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": 50200, "message": "画像解析结果格式错误", "data": None},
        )

    try:
        dialogue_service = ProfileDialogueService(db)
        pf = await dialogue_service.update_from_dialogue(current_user.id, req.course_id, extracted)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except Exception as e:
        await db.rollback()
        raise e

@router.post("/update-goal")
async def update_learning_goal(
    req: ProfileGoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.update_learning_goal(current_user.id, req.course_id, req.learning_goal)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except Exception as e:
        await db.rollback()
        raise e

@router.post("/update-instruction")
async def update_custom_instruction(
    req: ProfileInstructionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.update_custom_instruction(current_user.id, req.course_id, req.custom_instruction)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except Exception as e:
        await db.rollback()
        raise e

@router.post("/refresh")
async def refresh_profile(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, course_id, db)
    
    refresh_service = ProfileRefreshService(db)
    active_task = await refresh_service.get_processing_refresh_task(current_user.id, course_id)
    if active_task:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "task_id": active_task.id,
                "status": active_task.status,
                "created_at": active_task.create_time.isoformat(),
            },
        }

    task = await refresh_service.create_refresh_task(current_user.id, course_id)
    await db.commit()

    asyncio.create_task(
        run_profile_refresh_background(task.id, current_user.id, course_id)
    )

    return {
        "code": 202,
        "message": "accepted",
        "data": {
            "task_id": task.id,
            "status": task.status,
            "created_at": task.create_time.isoformat(),
        },
    }
